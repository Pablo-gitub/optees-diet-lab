"""Local multi-profile planner. Personal configurations are never served as static files."""

import asyncio
import datetime as dt
import hashlib
import hmac
import json
import os
import secrets
import sqlite3
import sys
import time
from pathlib import Path
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from plan_diet_day import NUTRIENTS, load_foods, formulate, solve_problem, decode_result, optimize_day
from plan_recipe import templates as recipe_templates, formulate_recipe, optimize_recipe
from recipe_diet_compatibility import meal_options
from optees_command import optees_command
from daily_meals import defaults as daily_defaults, validate as validate_daily
from target_validation import profile_target_warnings
from multiobjective_day import solve_strategy, nondominated, choose_arm, STRATEGIES
import diary_service as diary
import workout_service as workouts
import workout_configuration as workout_settings
import joint_orchestration as joint
import progress_recalibration as recalibration
import contextual_bandit as bandit
from day_orchestration import orchestrate_day, context_key
from health_inputs import load_report as load_health_report, algorithm_inputs as health_algorithm_inputs
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

DB = Path(os.environ.get('DIET_WEB_DB', ROOT / 'data/personal/web.sqlite'))
app = FastAPI()
app.mount('/static', StaticFiles(directory=ROOT / 'web/static'), name='static')
solver_lock = asyncio.Lock()
health_lock = asyncio.Lock()
health_job = {}
health_task = None


def connect():
    db = sqlite3.connect(DB)
    db.row_factory = sqlite3.Row
    return db


def profile_defaults(profile):
    profile.setdefault('preferred_cuisines', [])
    profile.setdefault('daily_meals',daily_defaults(bool(profile.get('food_preferences'))))
    return profile


def owner_profile(user):
    profile=profile_defaults(json.loads(user['profile']))
    with connect() as db:
        profile['_workout_settings']=workout_settings.read(db,user['id'])
        import progress_analysis
        weight=progress_analysis.weight_series(measurement_values(db,user['id']),diary.local_today())
        if weight['status']=='available':profile['_filtered_weight_kg']=weight['daily_points'][-1]['filtered_kg']
        profile['_recipe_runs']={'run:'+str(r['id']):json.loads(r['payload']) for r in db.execute('SELECT id,payload FROM recipe_runs WHERE user_id=?',(user['id'],))}
    return profile


def password_hash(password, salt):
    return hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1).hex()


def defaults():
    config = json.loads((ROOT / 'config/demo-diet-day.json').read_text())
    return dict(
        display_name='',
        mode='free',
        targets=config['main_meals_targets'],
        meal_targets={},
        excluded_crea_ids=[],
        personal_diets=False,
        preference_note='',
        targets_demo=True,
        preferred_cuisines=[],
    )


def load_recipe_images():
    path = ROOT / 'config/recipe-images.json'
    if path.exists():
        try:
            return json.loads(path.read_text()).get('images', {})
        except Exception:
            return {}
    return {}


def load_recipe_titles_it():
    path = ROOT / 'config/recipe-titles-it.json'
    try:
        return json.loads(path.read_text()).get('titles', {})
    except (OSError, ValueError):
        return {}


def initialize():
    DB.parent.mkdir(parents=True, exist_ok=True)
    with connect() as db:
        db.executescript('''CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, username TEXT UNIQUE, salt TEXT, password TEXT, profile TEXT);
        CREATE TABLE IF NOT EXISTS sessions(token TEXT PRIMARY KEY, user_id INTEGER, expires REAL, csrf TEXT);
        CREATE TABLE IF NOT EXISTS plans(id INTEGER PRIMARY KEY, user_id INTEGER, created REAL, payload TEXT, selected INTEGER DEFAULT 0);
        CREATE TABLE IF NOT EXISTS plan_feedback(user_id INTEGER, plan_id INTEGER, rating INTEGER, tried_at REAL, PRIMARY KEY(user_id,plan_id));
        CREATE TABLE IF NOT EXISTS plan_set(id INTEGER PRIMARY KEY, user_id INTEGER, created REAL, payload TEXT, input TEXT);
        CREATE TABLE IF NOT EXISTS recipe_runs(id INTEGER PRIMARY KEY, user_id INTEGER, created REAL, payload TEXT);''')
        if not db.execute('SELECT 1 FROM users').fetchone():
            password = secrets.token_urlsafe(16)
            salt = secrets.token_hex(16)
            profile = defaults()
            profile.update(display_name='Paolo', mode='sedentary', personal_diets=True)
            pref = ROOT / 'data/personal/current_food_preferences.json'
            if pref.exists():
                profile['food_preferences'] = json.loads(pref.read_text())
                profile['preference_note'] = str(profile['food_preferences'].get('note', ''))
            db.execute(
                'INSERT INTO users(username,salt,password,profile) VALUES(?,?,?,?)',
                ('paolo', salt, password_hash(password, salt), json.dumps(profile)),
            )
            access = DB.parent / 'web_access.txt'
            access.write_text('Accesso personale locale\nUtente: paolo\nPassword: ' + password + '\n')
            access.chmod(0o600)
    with connect() as db:
        diary.migrate(db)
        recalibration.migrate(db)
        import activity_targets
        activity_targets.migrate(db)
        legacy=db.execute("SELECT id,profile FROM users WHERE username='paolo'").fetchone()
        if legacy and json.loads(legacy['profile']).get('personal_diets'):
            workout_settings.seed_legacy_equipment(db,legacy['id'],ROOT/'data/personal/equipment.json')
        db.execute("UPDATE job SET state='failed',error=? WHERE state IN ('queued','running')",(json.dumps(dict(code='interrupted',detail='Calcolo interrotto dal riavvio; riprova.')),))
    DB.chmod(0o600)


initialize()


def identity(request, mutation=False):
    token = request.cookies.get('diet_session', '')
    with connect() as db:
        row = db.execute(
            'SELECT users.*, sessions.csrf FROM sessions JOIN users ON users.id=sessions.user_id WHERE token=? AND expires>?',
            (hashlib.sha256(token.encode()).hexdigest(), time.time()),
        ).fetchone()
    if not row:
        raise HTTPException(401, 'Accedi al tuo profilo')
    if mutation and not hmac.compare_digest(request.headers.get('x-csrf-token', ''), row['csrf']):
        raise HTTPException(403, 'Richiesta non autorizzata')
    return row


@app.middleware('http')
async def protect_origin(request, next_call):
    if request.method in ['POST', 'PUT', 'PATCH', 'DELETE']:
        from urllib.parse import urlsplit

        origin = request.headers.get('origin')
        if origin and urlsplit(origin).netloc != request.headers.get('host'):
            return JSONResponse({'detail': 'Origine non consentita'}, status_code=403)
    response = await next_call(request)
    response.headers['Cache-Control'] = 'no-store'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['Content-Security-Policy'] = (
        "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' https://upload.wikimedia.org https://thumb.wikimedia.org; frame-ancestors 'none'"
    )
    return response


@app.get('/')
def index():
    return FileResponse(ROOT / 'web/static/index.html')


@app.post('/api/register')
async def register(request: Request):
    if os.environ.get('DIET_WEB_ALLOW_REGISTER', '1') == '0':
        raise HTTPException(403, 'Creazione di nuovi profili disattivata')
    data = await request.json()
    username = str(data.get('username', '')).strip().lower()
    password = str(data.get('password', ''))
    if (
        not username.isascii()
        or not username.replace('_', '').isalnum()
        or not 3 <= len(username) <= 40
        or not 10 <= len(password) <= 200
    ):
        raise HTTPException(400, 'Nome: 3–40 lettere/numeri; password: almeno 10 caratteri')
    profile = defaults()
    profile['display_name'] = username
    salt = secrets.token_hex(16)
    try:
        with connect() as db:
            db.execute(
                'INSERT INTO users(username,salt,password,profile) VALUES(?,?,?,?)',
                (username, salt, password_hash(password, salt), json.dumps(profile)),
            )
    except sqlite3.IntegrityError:
        raise HTTPException(409, 'Nome già utilizzato')
    return {'ok': True}


attempts = {}


@app.post('/api/login')
async def login(request: Request):
    peer = request.client.host
    recent = [x for x in attempts.get(peer, []) if x > time.time() - 60]
    if len(recent) >= 10:
        raise HTTPException(429, 'Attendi un minuto prima di riprovare')
    attempts[peer] = recent + [time.time()]
    data = await request.json()
    password = str(data.get('password', ''))
    if len(password) > 200:
        raise HTTPException(400, 'Password troppo lunga')
    with connect() as db:
        user = db.execute(
            'SELECT * FROM users WHERE username=?', (str(data.get('username', '')).strip().lower(),)
        ).fetchone()
        salt = user['salt'] if user else '00' * 16
        candidate = password_hash(password, salt)
        if not user or not hmac.compare_digest(candidate, user['password']):
            raise HTTPException(401, 'Credenziali non valide')
        token = secrets.token_urlsafe(32)
        csrf = secrets.token_urlsafe(24)
        db.execute('DELETE FROM sessions WHERE expires<?', (time.time(),))
        db.execute(
            'INSERT INTO sessions VALUES(?,?,?,?)',
            (hashlib.sha256(token.encode()).hexdigest(), user['id'], time.time() + 43200, csrf),
        )
    response = JSONResponse({'csrf': csrf})
    response.set_cookie('diet_session', token, httponly=True, samesite='strict', max_age=43200)
    return response


@app.post('/api/logout')
def logout(request: Request):
    identity(request, True)
    with connect() as db:
        db.execute(
            'DELETE FROM sessions WHERE token=?',
            (hashlib.sha256(request.cookies['diet_session'].encode()).hexdigest(),),
        )
    response = JSONResponse({'ok': True})
    response.delete_cookie('diet_session')
    return response


@app.get('/api/profile')
def profile(request: Request):
    user = identity(request)
    data = profile_defaults(json.loads(user['profile']))
    return {'profile': data, 'csrf': user['csrf'], 'warnings': profile_target_warnings(data)}


@app.put('/api/profile')
async def update_profile(request: Request):
    user = identity(request, True)
    old = json.loads(user['profile'])
    data = await request.json()
    mode = data.get('mode', 'free')
    if mode not in (['free', 'sedentary', 'training'] if old['personal_diets'] else ['free']):
        raise HTTPException(400, 'Dieta personale non disponibile per questo profilo')
    preferred = data.get('preferred_cuisines', old.get('preferred_cuisines', []))
    with sqlite3.connect(ROOT / 'dataset/recipes/catalog.sqlite') as catalog:
        allowed = {r[0] for r in catalog.execute('SELECT DISTINCT cuisine_id FROM recipes')}
    if (
        not isinstance(preferred, list)
        or len(preferred) > 150
        or any(not isinstance(x, str) or x not in allowed for x in preferred)
    ):
        raise HTTPException(400, 'Cucine non valide')
    old['preferred_cuisines'] = list(dict.fromkeys(preferred))
    if 'goals' in data:
        import personal_goals
        old['goals']=personal_goals.validate(data['goals'])
    if 'energy_balance_target_kcal' in data:
        old['energy_balance_target_kcal']=workouts.finite(data['energy_balance_target_kcal'],'Bilancio calorico',-1000,1000,True)
    if 'day_type_targets' in data:
        groups=data['day_type_targets']
        if not isinstance(groups,dict) or set(groups)!= {'rest','training'}:raise diary.DomainError('Target per tipo di giornata non validi')
        try:
            for target in groups.values():validate_daily(dict(old.get('daily_meals',daily_defaults(bool(old.get('food_preferences')))),targets=target))
        except ValueError as exc:raise diary.DomainError(str(exc))
        old['day_type_targets']=groups
    try:old['daily_meals']=validate_daily(data.get('daily_meals',old.get('daily_meals',daily_defaults(bool(old.get('food_preferences'))))))
    except (ValueError,TypeError) as e:raise HTTPException(400,str(e))
    old.update(
        display_name=str(data.get('display_name', ''))[:80],
        mode=mode,
        preference_note=str(data.get('preference_note', ''))[:2000],
        targets=data.get('targets', old['targets']),
        meal_targets=data.get('meal_targets', {}),
        excluded_crea_ids=data.get('excluded_crea_ids', []),
        targets_demo=data.get('targets_demo', True),
    )
    if not isinstance(old['excluded_crea_ids'], list) or not all(isinstance(x, str) for x in old['excluded_crea_ids']):
        raise HTTPException(400, 'Esclusioni non valide')
    try:
        formulate(make_config(old, 0), load_foods())
        warnings = profile_target_warnings(old)
    except (ValueError, KeyError, TypeError) as e:
        raise HTTPException(400, str(e))
    with connect() as db:
        db.execute('UPDATE users SET profile=? WHERE id=?', (json.dumps(old), user['id']))
    return {'ok': True, 'warnings': warnings}


def make_config(profile, day):
    base = json.loads((ROOT / 'config/demo-diet-day.json').read_text())
    base.update(
        demo=profile['targets_demo'],
        mode=profile['mode'],
        day_index=day,
        main_meals_targets=profile['targets'],
        meal_targets=profile['meal_targets'],
        excluded_crea_ids=profile['excluded_crea_ids'],
        day_type=profile.get('_day_types_by_index',{}).get(day,'rest'),
    )
    settings=profile.get('daily_meals',daily_defaults(bool(profile.get('food_preferences'))))
    validate_daily(settings)
    base['daily_meals']=settings
    if settings['enabled']:
        base['food_preferences']=profile.get('food_preferences',{})
        base['demo']=settings['targets_demo']
    return base


@app.get('/api/plans')
def plans(request: Request):
    user = identity(request)
    with connect() as db:
        rows = db.execute(
            'SELECT id,created,payload,selected FROM plans WHERE user_id=? ORDER BY id DESC LIMIT 30', (user['id'],)
        ).fetchall()
        feedback={r['plan_id']:r['rating'] for r in db.execute('SELECT plan_id,rating FROM plan_feedback WHERE user_id=?',(user['id'],))}
    return [
        {'id': r['id'], 'created': r['created'], 'selected': bool(r['selected']), 'plan': json.loads(r['payload']), 'feedback':feedback.get(r['id'])}
        for r in rows
    ]


@app.post('/api/generate')
async def generate(request: Request):
    user = identity(request, True)
    profile = json.loads(user['profile'])
    data = await request.json()
    day = data.get('day_index', data.get('horizon', {}).get('day_index', 0))
    if isinstance(day, bool) or not isinstance(day, int) or not 0 <= day < 14:
        raise HTTPException(400, 'Giorno non valido')
    if data.get('horizon', {}).get('days', 1) != 1:
        raise HTTPException(400, 'Usa la generazione settimanale per più giorni')
    if solver_lock.locked():
        raise HTTPException(409, 'Calcolo già in corso: riprova fra poco')
    async with solver_lock:
        config = make_config(profile, day)
        if 'mode' in data and data['mode'] != config['mode']:
            raise HTTPException(400, 'Programma diverso dal profilo attivo')
        with connect() as db:
            view=diary.day_view(db,user['id'],profile,diary.local_today().isoformat())
            kind=data.get('day_type','training' if any(w['status']!='skipped' for w in view['workouts']) else 'rest')
            if kind not in ('rest','training'):raise HTTPException(400,'Tipo di giornata non valido')
            config['day_type']=kind;context=context_key(config)
            observations=bandit.observations(db,user['id'],profile).get(context,[])
            previous=db.execute('SELECT payload FROM plans WHERE user_id=? AND selected=1 AND created>=?',(user['id'],time.time()-7*86400)).fetchall()
        history={(x['meal'],x['food_id']) for row in previous for x in json.loads(row['payload']).get('selections',[]) if x['meal'] in ('lunch','dinner')}
        report=load_health_report(health_directory(user['id']))
        health=health_algorithm_inputs(report) if report else None
        try:
            async with stdio_client(StdioServerParameters(command=optees_command(config))) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    result = await orchestrate_day(session,config,load_foods(),data,history,observations,health,profile.get('energy_balance_target_kcal'))
        except ValueError as e:
            raise HTTPException(400,str(e))
        except Exception as e:
            print('Planner error:',repr(e),flush=True)
            raise HTTPException(422,'Calcolo non riuscito. Controlla obiettivi ed esclusioni.')
        with connect() as db:
            cursor=db.execute('INSERT INTO plan_set(user_id,created,payload,input) VALUES(?,?,?,?)',(user['id'],time.time(),'{}',json.dumps(dict(config=config,profile=profile,request=data,history=sorted(history),observations=observations,health=health))))
            result['run_id']=str(cursor.lastrowid)
            for plan in result['plans']:
                cursor=db.execute('INSERT INTO plans(user_id,created,payload) VALUES(?,?,?)',(user['id'],time.time(),json.dumps(plan)))
                plan['id']=cursor.lastrowid
            result['count']=len(result['plans'])
            db.execute('UPDATE plan_set SET payload=? WHERE id=?',(json.dumps(result),int(result['run_id'])))
        return result


@app.post('/api/plans/{plan_id}/select')
def select_plan(plan_id: int, request: Request):
    user = identity(request, True)
    with connect() as db:
        row = db.execute('SELECT payload FROM plans WHERE id=? AND user_id=?', (plan_id, user['id'])).fetchone()
        if not row:
            raise HTTPException(404, 'Piano non trovato')
        payload = json.loads(row['payload'])
        if 'days' in payload:raise HTTPException(400,'Usa applica piano per una settimana')
        if payload['status'] not in ['optimal', 'feasible']:
            raise HTTPException(400, 'Piano senza soluzione')
        db.execute(
            'UPDATE plans SET selected=0 WHERE user_id=? AND json_extract(payload,\'$.day_index\')=? AND json_extract(payload,\'$.mode\')=?',
            (user['id'], payload['day_index'], payload['mode']),
        )
        db.execute('UPDATE plans SET selected=1 WHERE id=? AND user_id=?', (plan_id, user['id']))
    return {'ok': True}


@app.post('/api/plans/{plan_id}/feedback')
async def plan_feedback(plan_id: int, request: Request):
    user=identity(request,True);data=await request.json()
    rating=data.get('rating')
    if data.get('tried') is not True or isinstance(rating,bool) or not isinstance(rating,int) or not 1<=rating<=5:
        raise HTTPException(400,'Conferma di aver provato il piano e assegna un voto da 1 a 5')
    profile=owner_profile(user)
    with connect() as db:
        row=db.execute('SELECT payload FROM plans WHERE id=? AND user_id=?',(plan_id,user['id'])).fetchone()
        if not row:raise HTTPException(404,'Piano non trovato')
        if json.loads(row['payload'])['status'] not in ['optimal','feasible']:raise HTTPException(400,'Piano senza soluzione')
        db.execute('INSERT INTO plan_feedback VALUES(?,?,?,?) ON CONFLICT(user_id,plan_id) DO UPDATE SET rating=excluded.rating,tried_at=excluded.tried_at',(user['id'],plan_id,rating,time.time()))
        trials=bandit.trials(db,user['id'],profile,plan_id)
    return dict(ok=True,learning=dict(parameters=bandit.PARAMETERS,status='eligible' if any(t['reward'] is not None for t in trials) else 'insufficient_data',reason=None if any(t['reward'] is not None for t in trials) else 'Servono applicazione, prova dichiarata e diario/allenamenti completi.',trials=trials))


def health_directory(user_id):
    return DB.parent / 'health' / f'user_{user_id}'


def health_import_allowed(user_id):
    marker=DB.parent/'health/owner.json'
    return marker.exists() and json.loads(marker.read_text()).get('user_id')==user_id


@app.get('/api/health')
def health_summary(request: Request):
    user=identity(request);report=load_health_report(health_directory(user['id']))
    job=dict(health_job) if health_job.get('user_id')==user['id'] else None
    if job:job.pop('user_id',None)
    return dict(imported=report is not None,can_import=health_import_allowed(user['id']),job=job,report=report,algorithm_inputs=health_algorithm_inputs(report) if report else None)


@app.post('/api/health/import')
async def health_import(request: Request):
    global health_task
    user=identity(request,True)
    if not health_import_allowed(user['id']):raise HTTPException(403,'Nessuna esportazione sanitaria assegnata a questo profilo')
    if (health_directory(user['id'])/'health.importing.sqlite').exists():raise HTTPException(409,'Importazione esterna già in corso')
    if health_lock.locked() or (health_task and not health_task.done()):raise HTTPException(409,'Importazione già in corso')
    archives=list((ROOT/'sanitary_data_export').glob('*.zip'))
    if len(archives)!=1:raise HTTPException(400,'Lascia un solo ZIP nella cartella delle esportazioni sanitarie')
    owner=dict(user_id=user['id'],username=user['username'])
    health_job.clear();health_job.update(user_id=user['id'],state='starting')
    async def run():
        async with health_lock:
            try:
                from apple_health import import_zip
                await asyncio.to_thread(import_zip,archives[0],health_directory(user['id']),owner,lambda s:health_job.update(s))
            except Exception as error:
                print('Health import error:',repr(error),flush=True)
                health_job.update(state='failed',message='Importazione non riuscita; il riepilogo precedente resta disponibile.')
    health_task=asyncio.create_task(run())
    return {'started':True}


@app.get('/api/cuisines')
def cuisines(request: Request):
    identity(request)
    with sqlite3.connect(ROOT / 'dataset/recipes/catalog.sqlite') as db:
        return [
            {'id': r[0], 'name': r[1], 'count': r[2]}
            for r in db.execute('SELECT cuisine_id,cuisine,COUNT(*) FROM recipes GROUP BY cuisine_id ORDER BY cuisine')
        ]


@app.get('/api/recipes')
def recipes(request: Request, q: str = '', cuisine: str = '', preferred: bool = False, offset: int = 0):
    user = identity(request)
    profile = json.loads(user['profile'])
    if len(q) > 100 or len(cuisine) > 80 or not 0 <= offset <= 10000:
        raise HTTPException(400, 'Filtro non valido')
    from import_recipes import fold

    titles_it = load_recipe_titles_it()
    clauses = []
    args = []
    if q:
        # Match the original catalog text or the Italian title overlay.
        needle = fold(q)
        italian = [rid for rid, title in titles_it.items() if needle in fold(title)]
        clauses.append("(search_text LIKE ? ESCAPE '\\'" + (' OR id IN (' + ','.join('?' * len(italian)) + ')' if italian else '') + ')')
        args.append('%' + needle.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_') + '%')
        args.extend(italian)
    if cuisine:
        clauses.append('cuisine_id=?')
        args.append(cuisine)
    favorites = profile.get('preferred_cuisines', [])
    if preferred:
        if not favorites:
            return {'total': 0, 'recipes': []}
        clauses.append('cuisine_id IN (' + ','.join('?' for _ in favorites) + ')')
        args.extend(favorites)
    where = ' WHERE ' + ' AND '.join(clauses) if clauses else ''
    images = load_recipe_images()
    with sqlite3.connect(ROOT / 'dataset/recipes/catalog.sqlite') as db:
        found = db.execute('SELECT id, title FROM recipes' + where, args).fetchall()
        # Recipes with a verified photo first, then by Italian title.
        found.sort(key=lambda r: (r[0] not in images, fold(titles_it.get(r[0], r[1])), r[0]))
        page = [r[0] for r in found[offset : offset + 30]]
        payloads = dict(db.execute('SELECT id, payload FROM recipes WHERE id IN (' + ','.join('?' * len(page)) + ')', page).fetchall()) if page else {}
    recipe_list = []
    for rid in page:
        rec = json.loads(payloads[rid])
        rec['title_it'] = titles_it.get(rid, rec['title'])
        img = images.get(rid)
        if img:
            rec['illustrative_image'] = img
        recipe_list.append(rec)
    return {'total': len(found), 'recipes': recipe_list}


@app.get('/api/recipe-solver')
def recipe_solver_options(request: Request):
    identity(request)
    images = load_recipe_images()
    templates_list = []
    for r in recipe_templates():
        r_copy = dict(r)
        if r['id'] in images:
            r_copy['illustrative_image'] = images[r['id']]
        templates_list.append(r_copy)
    return {'recipes': templates_list, 'defaults': json.loads((ROOT / 'config/demo-recipe.json').read_text())}


@app.get('/api/recipe-diet-options')
def recipe_diet_options(request: Request, mode: str = 'free', day_index: int = 0, meal: str = 'lunch'):
    user = identity(request)
    profile = json.loads(user['profile'])
    if mode != 'free' and not profile.get('personal_diets'):
        raise HTTPException(403, 'Le diete personali sono disponibili solo nel profilo del proprietario')
    try:
        return meal_options(mode, day_index, meal)
    except (ValueError, KeyError) as e:
        raise HTTPException(400, str(e))


@app.get('/api/recipe-runs')
def recipe_runs(request: Request):
    user = identity(request)
    with connect() as db:
        rows = db.execute(
            'SELECT id,created,payload FROM recipe_runs WHERE user_id=? ORDER BY id DESC LIMIT 10', (user['id'],)
        ).fetchall()
    return [{'id': r['id'], 'created': r['created'], 'result': json.loads(r['payload'])} for r in rows]


@app.post('/api/recipe-optimize')
async def recipe_optimize(request: Request):
    user = identity(request, True)
    profile = json.loads(user['profile'])
    data = await request.json()
    if not isinstance(data, dict):
        raise HTTPException(400, 'Configurazione non valida')
    recipe = next((r for r in recipe_templates() if r['id'] == data.get('recipe_id')), None)
    if not recipe:
        raise HTTPException(400, 'Ricetta senza associazioni verificate')
    disabled = data.get('disabled_products', [])
    allowed = {c['source'] + ':' + c['id'] for i in recipe['ingredients'] for c in i['candidates']}
    if not isinstance(disabled, list) or any(not isinstance(p, str) or p not in allowed for p in disabled):
        raise HTTPException(400, 'Prodotti esclusi non validi')
    config = {k: data[k] for k in ['targets', 'flexibility', 'scale_min', 'scale_max'] if k in data}
    config.update(excluded_crea_ids=profile.get('excluded_crea_ids', []), disabled_products=disabled)
    try:
        formulate_recipe(recipe, config)
    except (ValueError, KeyError, TypeError) as e:
        raise HTTPException(400, str(e))
    if solver_lock.locked():
        raise HTTPException(409, 'Calcolo già in corso: riprova fra poco')
    async with solver_lock:
        command = optees_command()
        try:
            async with stdio_client(StdioServerParameters(command=command)) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    result = await optimize_recipe(session, recipe, config)
        except Exception as e:
            print('Recipe solver error:', repr(e), flush=True)
            raise HTTPException(422, 'Calcolo della ricetta non riuscito; dettagli nel terminale locale.')
        result['profile_mode'] = profile['mode']
        result['demo'] = True
        with connect() as db:
            db.execute(
                'INSERT INTO recipe_runs(user_id,created,payload) VALUES(?,?,?)',
                (user['id'], time.time(), json.dumps(result)),
            )
    return result


@app.exception_handler(diary.DomainError)
async def domain_error(request,exc):
    return JSONResponse({'detail':str(exc),'code':exc.code},status_code=exc.status)


@app.get('/api/day')
def read_day(request:Request,date:str):
    user=identity(request)
    with connect() as db:return diary.day_view(db,user['id'],owner_profile(user),date)


@app.get('/api/week')
def read_week(request:Request,start:str):
    user=identity(request)
    with connect() as db:return diary.week_view(db,user['id'],owner_profile(user),start)


@app.get('/api/foods/search')
def search_foods(request:Request,q:str,limit:int=20):
    user=identity(request)
    with connect() as db:return diary.search_foods(db,user['id'],owner_profile(user),q,limit)


async def mutate_diary(request,action,entry_id=None):
    user=identity(request,True)
    data={} if action=='delete' else await request.json()
    if not isinstance(data,dict):raise diary.DomainError('Corpo della richiesta non valido')
    with connect() as db:return diary.diary_mutation(db,user['id'],owner_profile(user),action,data,entry_id)


@app.post('/api/diary/confirm')
async def confirm_meal(request:Request):return await mutate_diary(request,'confirm')
@app.post('/api/diary/entries')
async def add_diary_entry(request:Request):return await mutate_diary(request,'add')
@app.patch('/api/diary/entries/{entry_id}')
async def edit_diary_entry(entry_id:int,request:Request):return await mutate_diary(request,'edit',entry_id)
@app.delete('/api/diary/entries/{entry_id}')
async def delete_diary_entry(entry_id:int,request:Request):return await mutate_diary(request,'delete',entry_id)
@app.post('/api/diary/skip')
async def skip_meal(request:Request):return await mutate_diary(request,'skip')
@app.post('/api/diary/reset')
async def reset_meal(request:Request):return await mutate_diary(request,'reset')


@app.post('/api/measurements')
async def manual_measurement(request:Request):
    user=identity(request,True);data=await request.json()
    if not isinstance(data,dict):raise diary.DomainError('Corpo della richiesta non valido')
    with connect() as db:
        date=diary.add_measurement(db,user['id'],data)
        result=diary.day_view(db,user['id'],owner_profile(user),date)
        result['measurements']=[dict(r) for r in db.execute('SELECT date,kind,value,unit,source FROM measurement WHERE user_id=? AND date=?',(user['id'],date))]
        return result


def measurement_values(db,user_id,report=None,as_of=None):
    from zoneinfo import ZoneInfo
    as_of=as_of or diary.local_today();cutoff=as_of-dt.timedelta(days=365)
    values=[dict(r) for r in db.execute('SELECT id,date,kind,value,unit,source FROM measurement WHERE user_id=? AND date>=? AND date<=? ORDER BY date,id',(user_id,cutoff.isoformat(),as_of.isoformat()))]
    report=report if report is not None else load_health_report(health_directory(user_id))
    if report:
        health_db=health_directory(user_id)/'health.sqlite'
        if health_db.exists():
            zone=ZoneInfo(report.get('timezone','Europe/Rome'));begin=dt.datetime.combine(cutoff,dt.time(),zone).timestamp();end=dt.datetime.combine(as_of+dt.timedelta(days=1),dt.time(),zone).timestamp()
            with sqlite3.connect('file:'+str(health_db)+'?mode=ro',uri=True) as health:
                for value,timestamp,source in health.execute("SELECT value,end,source FROM measures WHERE kind='weight' AND end>=? AND end<? ORDER BY end",(begin,end)):
                    when=dt.datetime.fromtimestamp(timestamp,zone);values.append(dict(date=when.date().isoformat(),timestamp=when.isoformat(),kind='weight',value=value,unit='kg',source='apple_health',source_detail=source))
        else:values.extend(dict(date=x['date'],kind='weight',value=x['value'],unit='kg',source='apple_health',source_detail=x.get('source')) for x in report.get('weight_history',[]))
        values.extend(dict(date=x['date'],kind=k,value=x['value'],unit=x['unit'],source='apple_health',source_detail=x.get('source')) for k,x in report.get('measures',{}).items() if k!='weight')
    return sorted(values,key=lambda x:x['date'],reverse=True)


@app.get('/api/measurements')
def read_measurements(request:Request):
    user=identity(request)
    with connect() as db:return measurement_values(db,user['id'])


@app.get('/api/stats/progress')
def stats_progress(request:Request,weeks:int=8):
    import progress_analysis
    user=identity(request);today=diary.local_today();profile=owner_profile(user)
    with connect() as db:return progress_analysis.progress(db,user['id'],profile,measurement_values(db,user['id']),today,weeks)


@app.get('/api/stats/summary')
def stats_summary(request:Request):
    from progress_analysis import summary
    return summary(stats_progress(request,weeks=2))


@app.post('/api/progress/check-in')
async def monday_check_in(request:Request):
    import progress_analysis
    user=identity(request,True);data=await request.json()
    if not isinstance(data,dict) or set(data)-{'date','weight_kg'}:raise diary.DomainError('Check-in non valido')
    date=diary.valid_date(data.get('date'));day=dt.date.fromisoformat(date)
    if day.weekday()!=0 or day>diary.local_today():raise diary.DomainError('Il check-in richiede una data di lunedì non futura')
    profile=owner_profile(user)
    with connect() as db:
        diary.add_measurement(db,user['id'],dict(date=date,kind='weight',value=data.get('weight_kg'),unit='kg'))
        report=load_health_report(health_directory(user['id']))
        values=measurement_values(db,user['id'],report=report)
        analysis=progress_analysis.progress(db,user['id'],profile,values,day,weeks=3)
        proposal=recalibration.make_proposal(db,user['id'],profile,report,values,day,diary.local_today()) if not health_updating(user['id']) else dict(status='insufficient_data',reason='Importazione Salute in corso; riprova quando è conclusa.')
        return dict(date=date,analysis=analysis,previous_week=analysis['weeks'][-2],recalibration=proposal)


def health_updating(user_id):
    return (health_directory(user_id)/'health.importing.sqlite').exists() or (health_job.get('user_id')==user_id and health_task is not None and not health_task.done())


@app.get('/api/progress/recalibrations')
def read_recalibrations(request:Request):
    user=identity(request)
    with connect() as db:return recalibration.history(db,user['id'])


async def decide_recalibration(request,proposal_id,decision):
    user=identity(request,True);data=await request.json()
    if health_updating(user['id']):raise diary.DomainError('Importazione Salute in corso; riprova quando è conclusa','health_import_running',409)
    with connect() as db:
        db.execute('BEGIN IMMEDIATE')
        fresh=db.execute('SELECT * FROM users WHERE id=?',(user['id'],)).fetchone();profile=owner_profile(fresh)
        report=load_health_report(health_directory(user['id']));values=measurement_values(db,user['id'],report=report)
        result=recalibration.decide(db,user['id'],profile,report,values,proposal_id,data,decision,diary.local_today())
        result['profile']=profile_defaults(json.loads(db.execute('SELECT profile FROM users WHERE id=?',(user['id'],)).fetchone()['profile']))
        return result


@app.post('/api/progress/recalibrations/{proposal_id}/approve')
async def approve_recalibration(proposal_id:int,request:Request):return await decide_recalibration(request,proposal_id,'approve')


@app.post('/api/progress/recalibrations/{proposal_id}/reject')
async def reject_recalibration(proposal_id:int,request:Request):return await decide_recalibration(request,proposal_id,'reject')


@app.get('/api/plan-sets/{set_id}')
def read_plan_set(set_id:int,request:Request):
    user=identity(request)
    with connect() as db:row=db.execute('SELECT payload FROM plan_set WHERE id=? AND user_id=?',(set_id,user['id'])).fetchone()
    if not row:raise diary.DomainError('Piano non trovato','not_found',404)
    return json.loads(row['payload'])


@app.post('/api/plan-sets/{set_id}/apply')
async def apply_plan_set(set_id:int,request:Request):
    user=identity(request,True);data=await request.json()
    if not isinstance(data,dict):raise diary.DomainError('Corpo della richiesta non valido')
    plan_set=read_plan_set(set_id,request)
    plan=next((p for p in plan_set['plans'] if p.get('id')==data.get('plan_id')),None)
    if not plan:raise diary.DomainError('Alternativa non trovata','not_found',404)
    with connect() as db:
        result=(joint.apply_week if plan_set.get('kind')=='joint' else workouts.apply_week if plan_set.get('kind')=='workout' else diary.apply_plan)(db,user['id'],owner_profile(user),plan_set,plan,data)
        if result['applied_slots']:bandit.record_application(db,user['id'],owner_profile(user),plan,result)
        if result['applied_slots']:db.execute('UPDATE plans SET selected=1 WHERE id=? AND user_id=?',(plan['id'],user['id']))
        return result


planning_tasks={}

@app.get('/api/jobs/{job_id}')
def read_job(job_id:str,request:Request):
    user=identity(request)
    with connect() as db:row=db.execute('SELECT * FROM job WHERE id=? AND user_id=?',(job_id,user['id'])).fetchone()
    if not row:raise diary.DomainError('Calcolo non trovato','not_found',404)
    return dict(state=row['state'],progress=row['progress'],result=dict(plan_set_id=row['result_ref']) if row['result_ref'] else None,error=json.loads(row['error']) if row['error'] else None)


async def planning_job(job_id,user_id,profile,data,kind):
    try:
        from week_orchestration import generate_week,generate_meal_alternatives
        async with solver_lock:
            with connect() as db:db.execute("UPDATE job SET state='running',progress=.1 WHERE id=?",(job_id,))
            with connect() as db:
                if kind=='workout':configuration=None
                elif kind=='meal':configuration=generate_meal_alternatives(db,user_id,profile,data,make_config)
                else:
                    configuration=None
                    import datetime as dt
                    profile['_day_types_by_index']={}
                    start=dt.date.fromisoformat(data['week_start']);locks={(x.get('date'),x.get('slot')):x for x in data.get('locked',[])}
                    for offset in range(7):
                        date=(start+dt.timedelta(days=offset)).isoformat()
                        view=diary.day_view(db,user_id,profile,date)
                        profile['_day_types_by_index'][(data.get('day_index',start.weekday())+offset)%14]='training' if any(w['status']!='skipped' for w in view['workouts']) else 'rest'
                        for meal in view['meals']:
                            if meal.get('consumed_estimate'):raise diary.DomainError('Un pasto consumato ha nutrienti a intervallo: il bilancio esatto non è disponibile','interval_nutrients_unavailable')
                            source=meal['eaten'] if meal['eaten'] is not None else meal['planned'] if meal['planned'] and meal['planned']['locked'] else None
                            if source is not None:locks[date,meal['slot']]=dict(date=date,slot=meal['slot'],items=[{k:item[k] for k in ('food','grams','units') if k in item} for item in source['items']])
                    data=dict(data,locked=list(locks.values()))
                    if kind=='joint':
                        workout_locks=joint.locked_workouts(db,user_id,data['week_start'])
                        joint_state=joint.state_hash(db,user_id,profile,data['week_start'])
            async with stdio_client(StdioServerParameters(command=optees_command())) as (read,write):
                async with ClientSession(read,write) as session:
                    await session.initialize()
                    if kind=='joint':
                        report=load_health_report(health_directory(user_id))
                        health=health_algorithm_inputs(report) if report else None
                        with connect() as db:observations=bandit.observations(db,user_id,profile)
                        result=await joint.generate_week(session,profile,data,make_config,load_foods(),health,workout_locks,observations)
                        result['state_hash']=joint_state
                    elif kind=='workout':result=await workouts.generate_week(session,profile,data)
                    elif kind=='week':
                        with connect() as db:
                            observations=bandit.observations(db,user_id,profile)
                            recent=db.execute('SELECT payload FROM plans WHERE user_id=? AND selected=1 AND created>=?',(user_id,time.time()-7*86400)).fetchall()
                        history=set()
                        for row in recent:
                            p=json.loads(row['payload'])
                            for day in p.get('days',[p]):history.update(s['food_id'] for s in day.get('selections',[]))
                        result=await generate_week(session,profile,data,make_config,load_foods(),history,observations)
                    else:result=await configuration(session)
            with connect() as db:
                set_id=db.execute('INSERT INTO plan_set(user_id,created,payload,input) VALUES(?,?,?,?)',(user_id,time.time(),'{}',json.dumps(dict(profile=profile,request=data,kind=kind)))).lastrowid
                result['run_id']=str(set_id)
                for p in result['plans']:
                    p['id']=db.execute('INSERT INTO plans(user_id,created,payload) VALUES(?,?,?)',(user_id,time.time(),json.dumps(p))).lastrowid
                db.execute('UPDATE plan_set SET payload=? WHERE id=?',(json.dumps(result),set_id))
                db.execute("UPDATE job SET state='done',progress=1,result_ref=? WHERE id=?",(set_id,job_id))
    except Exception as exc:
        print('Planning job error:',repr(exc),flush=True)
        error=dict(code=exc.code if isinstance(exc,diary.DomainError) else 'infeasible' if isinstance(exc,ValueError) else 'calculation_failed',detail=str(exc) if isinstance(exc,diary.DomainError) else 'Calcolo non riuscito; verifica vincoli e obiettivi.')
        with connect() as db:db.execute("UPDATE job SET state='failed',error=? WHERE id=?",(json.dumps(error),job_id))
    finally:planning_tasks.pop(job_id,None)


async def enqueue_planning(request,kind):
    user=identity(request,True);profile=owner_profile(user);data=await request.json()
    if not isinstance(data,dict):raise diary.DomainError('Corpo della richiesta non valido')
    if kind=='workout':workouts.week_config(data)
    elif kind in ('week','joint'):
        diary.valid_date(data.get('week_start'))
        mode=data.get('mode',profile['mode'])
        if mode not in (('free','sedentary','training') if profile['personal_diets'] else ('free',)):raise diary.DomainError('Programma non disponibile')
        profile['mode']=mode
        if not isinstance(data.get('locked',[]),list):raise diary.DomainError('Blocchi non validi')
        if kind=='joint':joint.validate_request(profile,data)
    else:
        diary.valid_date(data.get('date'));diary.valid_slot(data.get('slot'))
        with connect() as db:
            if diary.state(db,user['id'],data['date'],data['slot'])!='unknown':raise diary.DomainError('Pasto già registrato','slot_already_logged',409)
            p=diary.planned(db,user['id'],data['date'],data['slot'])
            if p and p['locked']:raise diary.DomainError('Pasto bloccato','slot_locked',409)
    with connect() as db:
        if db.execute("SELECT 1 FROM job WHERE user_id=? AND state IN ('queued','running')",(user['id'],)).fetchone():raise diary.DomainError('Calcolo già in corso','job_running',409)
        job_id=secrets.token_hex(16);db.execute("INSERT INTO job VALUES(?,?,?,'queued',0,NULL,NULL,?)",(job_id,user['id'],kind,time.time()))
    task=asyncio.create_task(planning_job(job_id,user['id'],profile,data,kind));planning_tasks[job_id]=task
    return JSONResponse(dict(job_id=job_id),status_code=202)


@app.post('/api/plans/week')
async def plan_week(request:Request):return await enqueue_planning(request,'week')
@app.post('/api/plans/meal-alternatives')
async def meal_alternatives(request:Request):return await enqueue_planning(request,'meal')


@app.get('/api/workouts/catalog')
def workout_catalog(request:Request):
    return workouts.catalog(owner_profile(identity(request)))

@app.get('/api/workouts/sessions/{session_id}')
def workout_session(session_id:str,request:Request):
    return workouts.session_by_id(owner_profile(identity(request)),session_id)

@app.get('/api/workouts/logs/{log_id}')
def workout_log(log_id:int,request:Request):
    user=identity(request)
    with connect() as db:return workouts.read_log(db,user['id'],log_id)

@app.get('/api/workouts/logs')
def workout_logs(request:Request,start:str,end:str):
    user=identity(request);diary.valid_date(start);diary.valid_date(end)
    if end<start or (dt.date.fromisoformat(end)-dt.date.fromisoformat(start)).days>366:raise diary.DomainError('Intervallo non valido')
    with connect() as db:return [workouts.read_log(db,user['id'],r['id']) for r in db.execute('SELECT id FROM workout_log WHERE user_id=? AND date BETWEEN ? AND ? ORDER BY date,id',(user['id'],start,end)).fetchall()]

@app.post('/api/workouts/week')
async def workout_week(request:Request):return await enqueue_planning(request,'workout')

async def mutate_workout(request,action,log_id=None):
    user=identity(request,True);data=await request.json()
    with connect() as db:return workouts.mutation(db,user['id'],owner_profile(user),action,data,log_id)

@app.post('/api/workouts/start')
async def workout_start(request:Request):return await mutate_workout(request,'start')
@app.post('/api/workouts/{log_id}/sets')
async def workout_sets(log_id:int,request:Request):return await mutate_workout(request,'sets',log_id)
@app.post('/api/workouts/{log_id}/finish')
async def workout_finish(log_id:int,request:Request):return await mutate_workout(request,'finish',log_id)
@app.post('/api/workouts/skip')
async def workout_skip(request:Request):return await mutate_workout(request,'skip')


@app.get('/api/workouts/planned/{planned_id}')
def planned_workout(planned_id:int,request:Request):
    user=identity(request)
    with connect() as db:
        value=dict(workouts.planned(db,user['id'],planned_id));value['session']=json.loads(value.pop('snapshot'));value['duration_seconds']=value['session']['duration_seconds'];value['minutes']=workouts.display_minutes(value['duration_seconds']);return value


@app.get('/api/workouts/config')
def read_workout_config(request:Request):
    user=identity(request);profile=owner_profile(user);public=workouts.catalog(profile)
    return workout_settings.view(profile['_workout_settings'],public)

@app.patch('/api/workouts/config')
async def update_workout_config(request:Request):
    user=identity(request,True);data=await request.json()
    with connect() as db:
        settings=workout_settings.update(workout_settings.read(db,user['id']),data)
        # Compile every overridden protocol before committing; invalid EMOM recovery is rejected.
        profile=owner_profile(user);profile['_workout_settings']=settings
        public=workouts.catalog(profile)
        db.execute('INSERT INTO workout_configuration(user_id,settings,updated) VALUES(?,?,?) ON CONFLICT(user_id) DO UPDATE SET settings=excluded.settings,updated=excluded.updated',(user['id'],json.dumps({k:v for k,v in settings.items() if k in workout_settings.defaults()}),workouts.now()))
        result=diary.day_view(db,user['id'],profile,diary.local_today().isoformat())
        result['workout_configuration']=workout_settings.view(settings,public)
        return result


@app.post('/api/plans/joint-week')
async def joint_week(request:Request):return await enqueue_planning(request,'joint')


# Previews are deliberately ephemeral: reading a proposed correction writes no rows.
rebalance_previews={}

@app.get('/api/rebalance/presets')
def rebalance_presets(request:Request):
    import meal_rebalance
    identity(request)
    return meal_rebalance.catalog()

@app.post('/api/rebalance/preview')
async def rebalance_preview(request:Request):
    import meal_rebalance
    user=identity(request,True);profile=owner_profile(user)
    meal=meal_rebalance.diary_request(await request.json(),diary.local_today())
    with connect() as db:snapshot=meal_rebalance.snapshot(db,user['id'],profile,meal)
    if solver_lock.locked():raise diary.DomainError('Calcolo già in corso','solver_busy',409)
    async with solver_lock:
        async with stdio_client(StdioServerParameters(command=optees_command(make_config(profile,0)))) as (read,write):
            async with ClientSession(read,write) as session:
                await session.initialize()
                result=await meal_rebalance.preview(session,profile,meal,snapshot,make_config,load_foods())
    token=secrets.token_urlsafe(24);now=time.time()
    for key in list(rebalance_previews):
        if rebalance_previews[key]['expires']<now:del rebalance_previews[key]
    rebalance_previews[token]=dict(user=user['id'],state=snapshot['state'],start=snapshot['start'],result=result,expires=now+1800)
    return dict({k:v for k,v in result.items() if not k.startswith('_')},preview_id=token)

async def rebalance_decide(request,preview_id,action):
    import meal_rebalance
    user=identity(request,True)
    if await request.json()!={}:raise diary.DomainError('Corpo della decisione non valido')
    proposal=rebalance_previews.get(preview_id)
    if not proposal or proposal['user']!=user['id'] or proposal['expires']<time.time():raise diary.DomainError('Anteprima scaduta o non trovata','not_found',404)
    with connect() as db:
        db.execute('BEGIN IMMEDIATE')
        fresh=dict(db.execute('SELECT * FROM users WHERE id=?',(user['id'],)).fetchone())
        result=meal_rebalance.decide(db,user['id'],owner_profile(fresh),preview_id,proposal,action)
    # Retain token until expiry so repeated actions return a conflict, not duplicate writes.
    return result

@app.post('/api/rebalance/{preview_id}/apply')
async def rebalance_apply(preview_id:str,request:Request):return await rebalance_decide(request,preview_id,'apply')

@app.post('/api/rebalance/{preview_id}/keep')
async def rebalance_keep(preview_id:str,request:Request):return await rebalance_decide(request,preview_id,'keep')


@app.get('/api/bandit/summary')
def bandit_summary(request:Request):
    user=identity(request);profile=owner_profile(user)
    with connect() as db:
        trials=bandit.trials(db,user['id'],profile);observations=bandit.observations(db,user['id'],profile)
    return dict(parameters=bandit.PARAMETERS,eligible_days=sum(t['reward'] is not None for t in trials),pending_days=sum(t['reward'] is None for t in trials),contexts={key:dict(observations=len(value),arms=sorted({a for a,_ in value})) for key,value in observations.items()},trials=trials)


@app.get('/api/goals')
def read_goals(request:Request):
    import personal_goals
    user=identity(request)
    return personal_goals.view(json.loads(user['profile']))

@app.put('/api/goals/{block}')
async def save_goals(block:str,request:Request):
    import personal_goals
    user=identity(request,True);data=await request.json()
    field={'body':'body','activity':'activity','training':'training_priorities','strength-anchors':'strength_anchors'}.get(block)
    if not field:raise diary.DomainError('Blocco non trovato','not_found',404)
    if field in ('training_priorities','strength_anchors'):
        key='priorities' if field=='training_priorities' else 'anchors'
        if not isinstance(data,dict) or set(data)!={key}:raise diary.DomainError('Blocco non valido')
        data=data[key]
    value=personal_goals.validate_block(field,data)
    with connect() as db:
        db.execute('BEGIN IMMEDIATE')
        stored=json.loads(db.execute('SELECT profile FROM users WHERE id=?',(user['id'],)).fetchone()[0])
        if field=='body' and value.get('pace')=='custom' and value['pace_pct_per_week']>.5:
            series=personal_goals.analysis.weight_series(measurement_values(db,user['id']),diary.local_today())
            if series['status']=='available' and value.get('target_weight_kg',0)>series['daily_points'][-1]['filtered_kg']:raise diary.DomainError('Ritmo in aumento massimo 0,5% a settimana')
        stored.setdefault('goals',{})[field]=value
        db.execute('UPDATE users SET profile=? WHERE id=?',(json.dumps(stored),user['id']))
    return personal_goals.view(stored)

@app.post('/api/goals/energy-proposal')
async def goals_energy_proposal(request:Request):
    import personal_goals
    user=identity(request,True)
    if await request.json()!={}:raise diary.DomainError('Corpo non valido')
    with connect() as db:
        db.execute('BEGIN IMMEDIATE')
        fresh=dict(db.execute('SELECT * FROM users WHERE id=?',(user['id'],)).fetchone());profile=owner_profile(fresh)
        report=load_health_report(health_directory(user['id']));values=measurement_values(db,user['id'],report=report)
        return personal_goals.propose(db,user['id'],profile,values,report,diary.local_today())

@app.post('/api/goals/energy-proposal/{identifier}/{decision}')
async def goals_energy_decide(identifier:int,decision:str,request:Request):
    import personal_goals
    user=identity(request,True);data=await request.json()
    if decision not in ('approve','reject'):raise diary.DomainError('Decisione non trovata','not_found',404)
    with connect() as db:
        db.execute('BEGIN IMMEDIATE')
        fresh=dict(db.execute('SELECT * FROM users WHERE id=?',(user['id'],)).fetchone());profile=owner_profile(fresh)
        report=load_health_report(health_directory(user['id']));values=measurement_values(db,user['id'],report=report)
        return personal_goals.decide(db,user['id'],profile,values,report,identifier,data,decision)


@app.get('/api/foods/barcode/{code}')
def food_barcode(code:str,request:Request):
    import personal_foods
    return personal_foods.lookup(code,owner_profile(identity(request)))

@app.post('/api/foods/personal')
async def create_personal_food(request:Request):
    import personal_foods
    user=identity(request,True);data=await request.json()
    with connect() as db:
        db.execute('BEGIN IMMEDIATE');return personal_foods.save(db,user['id'],data)

@app.put('/api/foods/personal/{identifier}')
async def update_personal_food(identifier:str,request:Request):
    import personal_foods
    user=identity(request,True);data=await request.json()
    with connect() as db:
        db.execute('BEGIN IMMEDIATE');return personal_foods.save(db,user['id'],data,identifier)

@app.delete('/api/foods/personal/{identifier}')
def delete_personal_food(identifier:str,request:Request):
    import personal_foods
    user=identity(request,True)
    with connect() as db:
        db.execute('BEGIN IMMEDIATE');return personal_foods.delete(db,user['id'],identifier)

@app.put('/api/foods/preferred')
async def prefer_food(request:Request):
    import personal_foods
    user=identity(request,True);data=await request.json()
    with connect() as db:
        db.execute('BEGIN IMMEDIATE');return personal_foods.preferred(db,user['id'],data)


@app.post('/api/plan-sets/{set_id}/alternatives')
async def more_plan_alternatives(set_id:int,request:Request):
    """Extend this exact owner pool, without applying a plan or changing diary."""
    from week_orchestration import generate_week,generate_meal_alternatives
    from ingredient_overlap import report as overlap_report,amounts as overlap_amounts,overlap as overlap_value
    from daily_meals import products
    user=identity(request,True);body=await request.json()
    if not isinstance(body,dict) or set(body)-{'time_limit'}:raise diary.DomainError('Parametri alternative non validi')
    budget=body.get('time_limit',30)
    if isinstance(budget,bool) or not isinstance(budget,(int,float)) or not 1<=budget<=120:raise diary.DomainError('Tempo massimo non valido')
    async with solver_lock:
        with connect() as db:
            row=db.execute('SELECT * FROM plan_set WHERE id=? AND user_id=?',(set_id,user['id'])).fetchone()
            if not row:raise diary.DomainError('Pool non trovato','not_found',404)
            payload=json.loads(row['payload']);original=json.loads(row['input']);profile=owner_profile(identity(request))
            kind=original.get('kind','day' if 'config' in original else None)
            if kind not in ('day','week','meal'):raise diary.DomainError('Questo pool non contiene alternative dieta espandibili','unsupported_pool')
            if not payload.get('plans'):raise diary.DomainError('Pool privo di piani','empty_pool')
            old_profile=original.get('profile')
            clean=lambda p:{k:v for k,v in profile_defaults(dict(p)).items() if not k.startswith('_')}
            if old_profile and clean(old_profile)!=clean(profile):raise diary.DomainError('Profilo cambiato: genera un nuovo pool','plan_set_state_changed',409)
            token=recalibration.fingerprint(db,user['id'],profile,None,[]);old_payload=row['payload']
            data=dict(original.get('request',{}),k=3,pool_size=3,time_limit=budget,_existing_plans=payload['plans'])
            foods=load_foods();foods.update({'personal:'+k:v for k,v in products(profile.get('food_preferences',{})).items()})
            for plan in payload['plans']:
                for day in plan.get('days',[plan]):
                    for selection in day.get('selections',[]):
                        identifier=selection['food_id']
                        if identifier not in foods:
                            ref=dict(source=selection.get('source','CREA'),id=selection.get('reference_id') or identifier)
                            food=diary.resolve_food(ref,profile)
                            foods[identifier]=dict(source=ref['source'],source_id=ref['id'],name=food['name'],composition_provenance=food.get('composition_provenance'))
            if kind=='meal':configuration=generate_meal_alternatives(db,user['id'],profile,data,make_config)
            elif kind=='week':
                import datetime as dt
                locks={(x['date'],x['slot']):x for x in data.get('locked',[])}
                start=dt.date.fromisoformat(data['week_start'])
                for offset in range(7):
                    date=(start+dt.timedelta(days=offset)).isoformat();view=diary.day_view(db,user['id'],profile,date)
                    for meal in view['meals']:
                        if meal.get('consumed_estimate'):raise diary.DomainError('Pasto a intervallo: alternative esatte non disponibili','interval_nutrients_unavailable')
                        source=meal['eaten'] if meal['eaten'] is not None else meal['planned'] if meal['planned'] and meal['planned']['locked'] else None
                        if source is not None:locks[date,meal['slot']]=dict(date=date,slot=meal['slot'],items=[{k:i[k] for k in ('food','grams','units') if k in i} for i in source['items']])
                data['locked']=list(locks.values())
        async with stdio_client(StdioServerParameters(command=optees_command())) as (read,write):
            async with ClientSession(read,write) as session:
                await session.initialize()
                if kind=='meal':result=await configuration(session)
                elif kind=='week':result=await generate_week(session,original['profile'],data,make_config,foods)
                else:result=await orchestrate_day(session,original['config'],foods,data)
        additions=result.get('plans',[])
        previous=list(payload['plans'])
        for p in additions:
            vector=overlap_amounts(p,foods,profile,payload.get('slot'))
            if any(overlap_value(vector,overlap_amounts(prior,foods,profile,payload.get('slot')))>.5+1e-6 for prior in previous):raise diary.DomainError('Alternativa non abbastanza diversa','overlap_not_verified',422)
            previous.append(p)
        with connect() as db:
            db.execute('BEGIN IMMEDIATE')
            fresh=identity(request);current=owner_profile(fresh)
            saved=db.execute('SELECT payload FROM plan_set WHERE id=? AND user_id=?',(set_id,user['id'])).fetchone()
            if not saved or saved['payload']!=old_payload or recalibration.fingerprint(db,user['id'],current,None,[])!=token:raise diary.DomainError('Diario, piano o profilo cambiati: ripeti il calcolo','plan_set_state_changed',409)
            if not additions and not result.setdefault('pool',{}).get('overlap_searches'):
                result['pool']['overlap_searches']=[dict(certified=False,reason='Ricerca senza una certificazione delle alternative; il risultato non dimostra impossibilità.')]
            if not additions:return dict(status='no_more_alternatives',plan_set_id=set_id,added_plan_ids=[],reason=('Non è stata trovata un’altra alternativa entro il tempo disponibile; riprova con un budget maggiore.' if result.get('status')=='partial' or any(not s.get('certified',False) for s in result.get('pool',{}).get('overlap_searches',[])) else 'Non ci sono altre alternative abbastanza diverse: serve almeno il 50% di ingredienti diversi.'),pool=result.get('pool',{}))
            for p in additions:
                p['rank']=len(payload['plans'])+1
                p['role']='alternative_'+str(p['rank'])
                p['id']=db.execute('INSERT INTO plans(user_id,created,payload) VALUES(?,?,?)',(user['id'],time.time(),json.dumps(p))).lastrowid
                payload['plans'].append(p)
            payload['count']=len(payload['plans'])
            payload['pool']['candidates']=payload['pool'].get('candidates',0)+result['pool'].get('candidates',len(additions))
            payload['pool'].setdefault('extensions',[]).append(result['pool'])
            overlap_report(payload,payload['plans'],foods,profile,payload.get('slot'))
            db.execute('UPDATE plan_set SET payload=? WHERE id=?',(json.dumps(payload),set_id))
            # Payload references in the list and plan detail agree after overlap changes.
            for p in payload['plans']:db.execute('UPDATE plans SET payload=? WHERE id=? AND user_id=?',(json.dumps(p),p['id'],user['id']))
        return dict(status='extended',plan_set_id=set_id,added_plan_ids=[p['id'] for p in additions],plan_set=payload)


@app.get('/api/activities')
def activities_catalog(request:Request):
    identity(request)
    from activity_service import catalog
    return catalog()


@app.post('/api/activities/confirm')
async def activity_confirm(request:Request):
    user=identity(request,True);data=await request.json()
    import activity_service
    with connect() as db:
        db.execute('BEGIN IMMEDIATE')
        fresh=dict(db.execute('SELECT * FROM users WHERE id=?',(user['id'],)).fetchone())
        return activity_service.confirm(db,user['id'],owner_profile(fresh),data)


@app.post('/api/goals/day-targets/proposal')
async def propose_activity_targets(request:Request):
    import activity_targets
    user=identity(request,True);data=await request.json()
    with connect() as db:
        db.execute('BEGIN IMMEDIATE')
        fresh=dict(db.execute('SELECT * FROM users WHERE id=?',(user['id'],)).fetchone());profile=owner_profile(fresh)
        if health_updating(user['id']):return dict(status='insufficient_data',reason='Importazione Salute in corso: riprova quando termina.')
        report=load_health_report(health_directory(user['id']));measurements=measurement_values(db,user['id'],report=report)
        return activity_targets.propose(db,user['id'],profile,measurements,report,data,diary.local_today())


@app.post('/api/goals/day-targets/proposal/{identifier}/{decision}')
async def decide_activity_targets(identifier:int,decision:str,request:Request):
    import activity_targets
    user=identity(request,True);data=await request.json()
    if decision not in ('approve','reject'):raise diary.DomainError('Decisione non trovata','not_found',404)
    with connect() as db:
        db.execute('BEGIN IMMEDIATE')
        if health_updating(user['id']):raise diary.DomainError('Importazione Salute in corso','health_import_in_progress',409)
        fresh=dict(db.execute('SELECT * FROM users WHERE id=?',(user['id'],)).fetchone());profile=owner_profile(fresh)
        report=load_health_report(health_directory(user['id']));measurements=measurement_values(db,user['id'],report=report)
        return activity_targets.decide(db,user['id'],profile,measurements,report,identifier,data,decision,diary.local_today())
