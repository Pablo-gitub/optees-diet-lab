"""Local multi-profile planner. Personal configurations are never served as static files."""

import asyncio
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
    if request.method in ['POST', 'PUT', 'DELETE']:
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
    data = json.loads(user['profile'])
    data.setdefault('preferred_cuisines', [])
    data.setdefault('daily_meals',daily_defaults(bool(data.get('food_preferences'))))
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
    strategy=data.get('strategy','balanced')
    if strategy not in (*STRATEGIES,'bandit'):
        raise HTTPException(400,'Strategia non valida')
    day = data.get('day_index', 0)
    if isinstance(day, bool) or not isinstance(day, int) or not 0 <= day < 14:
        raise HTTPException(400, 'Giorno non valido')
    if solver_lock.locked():
        raise HTTPException(409, 'Calcolo già in corso: riprova fra poco')
    async with solver_lock:
        config = make_config(profile, day)
        context=hashlib.sha256(json.dumps(dict(version='nutrition-strategy-ucb1-v1',configuration={k:config.get(k) for k in ['mode','main_meals_targets','daily_meals','meal_targets','excluded_crea_ids','food_preferences']}),sort_keys=True).encode()).hexdigest()
        requested=strategy; reason=None
        if strategy=='bandit':
            with connect() as db:
                trials=db.execute('SELECT p.payload,f.rating FROM plan_feedback f JOIN plans p ON p.id=f.plan_id AND p.user_id=f.user_id WHERE f.user_id=?',(user['id'],)).fetchall()
            observations=[(p['optimization']['strategy'],(r['rating']-1)/4) for r in trials if (p:=json.loads(r['payload'])).get('optimization',{}).get('context')==context]
            strategy,reason=choose_arm(observations)
        foods = load_foods()
        try:
            problem, choices, slots = formulate(config, foods)
            alternatives = []
            async with stdio_client(StdioServerParameters(command=optees_command(config))) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    results=[]
                    if strategy=='pareto':
                        keys=['kcal','protein_g','fat_g','carbs_available_g']
                        for weights in [None]+[{key:4. for key in [focus]} for focus in keys]:
                            result=await solve_strategy(session,problem,config,choices,'pareto',weights)
                            if result['mathematical_status'] in ['optimal','feasible']:results.append(result)
                            elif not results:results=[result];break
                        if results and results[0]['mathematical_status'] in ['optimal','feasible']:
                            results=nondominated(results)
                    for attempt in range(len(results) if strategy=='pareto' else 3):
                        result=results[attempt] if strategy=='pareto' else await solve_strategy(session,problem,config,choices,strategy)
                        record = decode_result(config, problem, choices, slots, foods, result)
                        # Only expose the reviewable plan; raw problem/source paths stay on server.
                        safe = {
                            key: record[key] for key in ['demo', 'scope', 'slots', 'status', 'selections', 'nutrients','nutrients_by_meal','daily_policy','diet_note','preference_penalty','preference_changes','constraint_report']
                        }
                        safe['optimization']=result.get('optimization',{'strategy':strategy})
                        safe['optimization'].update(context=context,requested=requested,bandit_reason=reason,pareto_scope='sampled_weighted_solutions' if strategy=='pareto' else None)
                        safe['mode'] = config['mode']
                        safe['day_index'] = day
                        safe['preference_status'] = (
                            'Colazione e spuntini: preferenze applicate dopo i vincoli rigidi, prima degli scarti nutrizionali.' if config['daily_meals']['enabled'] else 'Preferenze di colazione/spuntini non attive.'
                        )
                        if record['status'] not in ['optimal', 'feasible']:
                            if not alternatives:
                                alternatives.append(safe)
                            break
                        alternatives.append(safe)
                        if strategy=='pareto':continue
                        values = {v['name']: v['value'] for v in result['result']['variables']}
                        selected = [c['y'] for c in choices if values[problem['variables'][c['y']]['name']] > 0.5]
                        row = [0] * len(problem['variables'])
                        for i in selected:
                            row[i] = 1
                        problem['constraints'].append(dict(coefficients=row, relation='<=', rhs=len(selected) - 1))
        except Exception as e:
            # Do not send subprocess errors or private filenames to other profiles.
            print('Planner error:', repr(e), flush=True)
            raise HTTPException(
                422, 'Calcolo non riuscito. Controlla obiettivi ed esclusioni; dettagli nel terminale locale.'
            )
        with connect() as db:
            for safe in alternatives:
                db.execute(
                    'INSERT INTO plans(user_id,created,payload) VALUES(?,?,?)',
                    (user['id'], time.time(), json.dumps(safe)),
                )
    return {'count': len(alternatives)}


@app.post('/api/plans/{plan_id}/select')
def select_plan(plan_id: int, request: Request):
    user = identity(request, True)
    with connect() as db:
        row = db.execute('SELECT payload FROM plans WHERE id=? AND user_id=?', (plan_id, user['id'])).fetchone()
        if not row:
            raise HTTPException(404, 'Piano non trovato')
        payload = json.loads(row['payload'])
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
    with connect() as db:
        row=db.execute('SELECT payload FROM plans WHERE id=? AND user_id=?',(plan_id,user['id'])).fetchone()
        if not row:raise HTTPException(404,'Piano non trovato')
        if json.loads(row['payload'])['status'] not in ['optimal','feasible']:raise HTTPException(400,'Piano senza soluzione')
        db.execute('INSERT INTO plan_feedback VALUES(?,?,?,?) ON CONFLICT(user_id,plan_id) DO UPDATE SET rating=excluded.rating,tried_at=excluded.tried_at',(user['id'],plan_id,rating,time.time()))
    return {'ok':True}


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
