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
from plan_diet_day import NUTRIENTS, load_foods, formulate, solve_problem, decode_result
from plan_recipe import templates as recipe_templates, formulate_recipe, optimize_recipe
from recipe_diet_compatibility import meal_options
from optees_command import optees_command
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
DB = Path(os.environ.get('DIET_WEB_DB', ROOT / 'data/personal/web.sqlite'))
app = FastAPI()
app.mount('/static', StaticFiles(directory=ROOT/'web/static'), name='static')
solver_lock = asyncio.Lock()


def connect():
    db = sqlite3.connect(DB)
    db.row_factory = sqlite3.Row
    return db


def password_hash(password, salt):
    return hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1).hex()


def defaults():
    config = json.loads((ROOT/'config/demo-diet-day.json').read_text())
    return dict(display_name='', mode='free', targets=config['main_meals_targets'],
                meal_targets={}, excluded_crea_ids=[], personal_diets=False,
                preference_note='', targets_demo=True, preferred_cuisines=[])


def load_recipe_images():
    path = ROOT / 'config/recipe-images.json'
    if path.exists():
        try:
            return json.loads(path.read_text()).get('images', {})
        except Exception:
            return {}
    return {}


def initialize():
    DB.parent.mkdir(parents=True, exist_ok=True)
    with connect() as db:
        db.executescript('''CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, username TEXT UNIQUE, salt TEXT, password TEXT, profile TEXT);
        CREATE TABLE IF NOT EXISTS sessions(token TEXT PRIMARY KEY, user_id INTEGER, expires REAL, csrf TEXT);
        CREATE TABLE IF NOT EXISTS plans(id INTEGER PRIMARY KEY, user_id INTEGER, created REAL, payload TEXT, selected INTEGER DEFAULT 0);
        CREATE TABLE IF NOT EXISTS recipe_runs(id INTEGER PRIMARY KEY, user_id INTEGER, created REAL, payload TEXT);''')
        if not db.execute('SELECT 1 FROM users').fetchone():
            password = secrets.token_urlsafe(16)
            salt = secrets.token_hex(16)
            profile = defaults()
            profile.update(display_name='Paolo', mode='sedentary', personal_diets=True)
            pref = ROOT/'data/personal/current_food_preferences.json'
            if pref.exists():
                profile['food_preferences'] = json.loads(pref.read_text())
                profile['preference_note'] = str(profile['food_preferences'].get('note', ''))
            db.execute('INSERT INTO users(username,salt,password,profile) VALUES(?,?,?,?)', ('paolo',salt,password_hash(password,salt),json.dumps(profile)))
            access = DB.parent/'web_access.txt'
            access.write_text('Accesso personale locale\nUtente: paolo\nPassword: '+password+'\n')
            access.chmod(0o600)
    DB.chmod(0o600)


initialize()


def identity(request, mutation=False):
    token = request.cookies.get('diet_session','')
    with connect() as db:
        row = db.execute('SELECT users.*, sessions.csrf FROM sessions JOIN users ON users.id=sessions.user_id WHERE token=? AND expires>?', (hashlib.sha256(token.encode()).hexdigest(),time.time())).fetchone()
    if not row:
        raise HTTPException(401, 'Accedi al tuo profilo')
    if mutation and not hmac.compare_digest(request.headers.get('x-csrf-token',''),row['csrf']):
        raise HTTPException(403,'Richiesta non autorizzata')
    return row


@app.middleware('http')
async def protect_origin(request, next_call):
    if request.method in ['POST','PUT','DELETE']:
        from urllib.parse import urlsplit
        origin = request.headers.get('origin')
        if origin and urlsplit(origin).netloc != request.headers.get('host'):
            return JSONResponse({'detail':'Origine non consentita'},status_code=403)
    response = await next_call(request)
    response.headers['Cache-Control']='no-store'
    response.headers['X-Content-Type-Options']='nosniff'
    response.headers['X-Frame-Options']='DENY'
    response.headers['Content-Security-Policy']="default-src 'self'; script-src 'self'; style-src 'self'; frame-ancestors 'none'"
    return response


@app.get('/')
def index():
    return FileResponse(ROOT/'web/static/index.html')


@app.post('/api/register')
async def register(request: Request):
    if os.environ.get('DIET_WEB_ALLOW_REGISTER', '1') == '0':
        raise HTTPException(403,'Creazione di nuovi profili disattivata')
    data = await request.json()
    username = str(data.get('username','')).strip().lower()
    password = str(data.get('password',''))
    if not username.isascii() or not username.replace('_','').isalnum() or not 3 <= len(username) <= 40 or not 10 <= len(password) <= 200:
        raise HTTPException(400,'Nome: 3–40 lettere/numeri; password: almeno 10 caratteri')
    profile = defaults();profile['display_name']=username
    salt=secrets.token_hex(16)
    try:
        with connect() as db:
            db.execute('INSERT INTO users(username,salt,password,profile) VALUES(?,?,?,?)',(username,salt,password_hash(password,salt),json.dumps(profile)))
    except sqlite3.IntegrityError:
        raise HTTPException(409,'Nome già utilizzato')
    return {'ok':True}


attempts = {}
@app.post('/api/login')
async def login(request: Request):
    peer = request.client.host
    recent = [x for x in attempts.get(peer,[]) if x > time.time()-60]
    if len(recent)>=10:
        raise HTTPException(429,'Attendi un minuto prima di riprovare')
    attempts[peer]=recent+[time.time()]
    data=await request.json()
    password=str(data.get('password',''))
    if len(password)>200:
        raise HTTPException(400,'Password troppo lunga')
    with connect() as db:
        user=db.execute('SELECT * FROM users WHERE username=?',(str(data.get('username','')).strip().lower(),)).fetchone()
        salt=user['salt'] if user else '00'*16
        candidate=password_hash(password,salt)
        if not user or not hmac.compare_digest(candidate,user['password']):
            raise HTTPException(401,'Credenziali non valide')
        token=secrets.token_urlsafe(32);csrf=secrets.token_urlsafe(24)
        db.execute('DELETE FROM sessions WHERE expires<?',(time.time(),))
        db.execute('INSERT INTO sessions VALUES(?,?,?,?)',(hashlib.sha256(token.encode()).hexdigest(),user['id'],time.time()+43200,csrf))
    response=JSONResponse({'csrf':csrf})
    response.set_cookie('diet_session',token,httponly=True,samesite='strict',max_age=43200)
    return response


@app.post('/api/logout')
def logout(request: Request):
    identity(request,True)
    with connect() as db:
        db.execute('DELETE FROM sessions WHERE token=?',(hashlib.sha256(request.cookies['diet_session'].encode()).hexdigest(),))
    response=JSONResponse({'ok':True});response.delete_cookie('diet_session');return response


@app.get('/api/profile')
def profile(request: Request):
    user=identity(request)
    data=json.loads(user['profile']);data.setdefault('preferred_cuisines',[])
    return {'profile':data, 'csrf':user['csrf']}


@app.put('/api/profile')
async def update_profile(request: Request):
    user=identity(request,True);old=json.loads(user['profile']);data=await request.json()
    mode=data.get('mode','free')
    if mode not in (['free','sedentary','training'] if old['personal_diets'] else ['free']):
        raise HTTPException(400,'Dieta personale non disponibile per questo profilo')
    preferred=data.get('preferred_cuisines',old.get('preferred_cuisines',[]))
    with sqlite3.connect(ROOT/'dataset/recipes/catalog.sqlite') as catalog:
        allowed={r[0] for r in catalog.execute('SELECT DISTINCT cuisine_id FROM recipes')}
    if not isinstance(preferred,list) or len(preferred)>150 or any(not isinstance(x,str) or x not in allowed for x in preferred):
        raise HTTPException(400,'Cucine non valide')
    old['preferred_cuisines']=list(dict.fromkeys(preferred))
    old.update(display_name=str(data.get('display_name',''))[:80],mode=mode,
               preference_note=str(data.get('preference_note',''))[:2000],targets=data.get('targets',old['targets']),
               meal_targets=data.get('meal_targets',{}),excluded_crea_ids=data.get('excluded_crea_ids',[]),
               targets_demo=data.get('targets_demo',True))
    if not isinstance(old['excluded_crea_ids'],list) or not all(isinstance(x,str) for x in old['excluded_crea_ids']):
        raise HTTPException(400,'Esclusioni non valide')
    try:
        formulate(make_config(old,0),load_foods())
    except (ValueError,KeyError,TypeError) as e:
        raise HTTPException(400,str(e))
    with connect() as db:
        db.execute('UPDATE users SET profile=? WHERE id=?',(json.dumps(old),user['id']))
    return {'ok':True}


def make_config(profile, day):
    base=json.loads((ROOT/'config/demo-diet-day.json').read_text())
    base.update(demo=profile['targets_demo'], mode=profile['mode'],day_index=day,
                main_meals_targets=profile['targets'],meal_targets=profile['meal_targets'],
                excluded_crea_ids=profile['excluded_crea_ids'])
    return base


@app.get('/api/plans')
def plans(request: Request):
    user=identity(request)
    with connect() as db:
        rows=db.execute('SELECT id,created,payload,selected FROM plans WHERE user_id=? ORDER BY id DESC LIMIT 30',(user['id'],)).fetchall()
    return [{'id':r['id'],'created':r['created'],'selected':bool(r['selected']),'plan':json.loads(r['payload'])} for r in rows]


@app.post('/api/generate')
async def generate(request: Request):
    user=identity(request,True);profile=json.loads(user['profile']);data=await request.json()
    day=data.get('day_index',0)
    if isinstance(day,bool) or not isinstance(day,int) or not 0<=day<14:
        raise HTTPException(400,'Giorno non valido')
    if solver_lock.locked():
        raise HTTPException(409,'Calcolo già in corso: riprova fra poco')
    async with solver_lock:
        config=make_config(profile,day);foods=load_foods()
        try:
            problem,choices,slots=formulate(config,foods)
            alternatives=[]
            async with stdio_client(StdioServerParameters(command=optees_command(config))) as (read,write):
                async with ClientSession(read,write) as session:
                    await session.initialize()
                    for _ in range(3):
                        result=await solve_problem(session,problem)
                        record=decode_result(config,problem,choices,slots,foods,result)
                        # Only expose the reviewable plan; raw problem/source paths stay on server.
                        safe={key:record[key] for key in ['demo','scope','slots','status','selections','nutrients']}
                        safe['mode']=config['mode'];safe['day_index']=day
                        safe['preference_status']='Preferenze registrate; non ancora usate per ordinare le alternative.'
                        if record['status'] not in ['optimal','feasible']:
                            if not alternatives: alternatives.append(safe)
                            break
                        alternatives.append(safe)
                        values={v['name']:v['value'] for v in result['result']['variables']}
                        selected=[c['y'] for c in choices if values[problem['variables'][c['y']]['name']]>.5]
                        row=[0]*len(problem['variables'])
                        for i in selected:row[i]=1
                        problem['constraints'].append(dict(coefficients=row,relation='<=',rhs=len(selected)-1))
        except Exception as e:
            # Do not send subprocess errors or private filenames to other profiles.
            print('Planner error:',repr(e),flush=True)
            raise HTTPException(422,'Calcolo non riuscito. Controlla obiettivi ed esclusioni; dettagli nel terminale locale.')
        with connect() as db:
            for safe in alternatives:
                db.execute('INSERT INTO plans(user_id,created,payload) VALUES(?,?,?)',(user['id'],time.time(),json.dumps(safe)))
    return {'count':len(alternatives)}


@app.post('/api/plans/{plan_id}/select')
def select_plan(plan_id: int,request: Request):
    user=identity(request,True)
    with connect() as db:
        row=db.execute('SELECT payload FROM plans WHERE id=? AND user_id=?',(plan_id,user['id'])).fetchone()
        if not row:raise HTTPException(404,'Piano non trovato')
        payload=json.loads(row['payload'])
        if payload['status'] not in ['optimal','feasible']:raise HTTPException(400,'Piano senza soluzione')
        db.execute('UPDATE plans SET selected=0 WHERE user_id=? AND json_extract(payload,\'$.day_index\')=? AND json_extract(payload,\'$.mode\')=?',(user['id'],payload['day_index'],payload['mode']))
        db.execute('UPDATE plans SET selected=1 WHERE id=? AND user_id=?',(plan_id,user['id']))
    return {'ok':True}


@app.get('/api/cuisines')
def cuisines(request: Request):
    identity(request)
    with sqlite3.connect(ROOT/'dataset/recipes/catalog.sqlite') as db:
        return [{'id':r[0],'name':r[1],'count':r[2]} for r in db.execute('SELECT cuisine_id,cuisine,COUNT(*) FROM recipes GROUP BY cuisine_id ORDER BY cuisine')]


@app.get('/api/recipes')
def recipes(request: Request,q: str='',cuisine: str='',preferred: bool=False,offset: int=0):
    user=identity(request);profile=json.loads(user['profile'])
    if len(q)>100 or len(cuisine)>80 or not 0<=offset<=10000:
        raise HTTPException(400,'Filtro non valido')
    from import_recipes import fold
    clauses=[];args=[]
    if q:
        clauses.append("search_text LIKE ? ESCAPE '\\'")
        args.append('%'+fold(q).replace('\\','\\\\').replace('%','\\%').replace('_','\\_')+'%')
    if cuisine:clauses.append('cuisine_id=?');args.append(cuisine)
    favorites=profile.get('preferred_cuisines',[])
    if preferred:
        if not favorites:return {'total':0,'recipes':[]}
        clauses.append('cuisine_id IN ('+','.join('?' for _ in favorites)+')');args.extend(favorites)
    where=' WHERE '+' AND '.join(clauses) if clauses else ''
    with sqlite3.connect(ROOT/'dataset/recipes/catalog.sqlite') as db:
        total=db.execute('SELECT COUNT(*) FROM recipes'+where,args).fetchone()[0]
        rows=db.execute('SELECT payload FROM recipes'+where+' ORDER BY title,id LIMIT 30 OFFSET ?',[*args,offset]).fetchall()
    images = load_recipe_images()
    recipe_list = []
    for r in rows:
        rec = json.loads(r[0])
        img = images.get(rec['id'])
        if img:
            rec['illustrative_image'] = img
        recipe_list.append(rec)
    return {'total':total,'recipes':recipe_list}


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
    return {'recipes':templates_list,'defaults':json.loads((ROOT/'config/demo-recipe.json').read_text())}


@app.get('/api/recipe-diet-options')
def recipe_diet_options(request: Request, mode: str='free', day_index: int=0, meal: str='lunch'):
    user=identity(request);profile=json.loads(user['profile'])
    if mode!='free' and not profile.get('personal_diets'):
        raise HTTPException(403,'Le diete personali sono disponibili solo nel profilo del proprietario')
    try:return meal_options(mode,day_index,meal)
    except (ValueError,KeyError) as e:raise HTTPException(400,str(e))


@app.get('/api/recipe-runs')
def recipe_runs(request: Request):
    user=identity(request)
    with connect() as db:
        rows=db.execute('SELECT id,created,payload FROM recipe_runs WHERE user_id=? ORDER BY id DESC LIMIT 10',(user['id'],)).fetchall()
    return [{'id':r['id'],'created':r['created'],'result':json.loads(r['payload'])} for r in rows]


@app.post('/api/recipe-optimize')
async def recipe_optimize(request: Request):
    user=identity(request,True);profile=json.loads(user['profile']);data=await request.json()
    if not isinstance(data,dict):raise HTTPException(400,'Configurazione non valida')
    recipe=next((r for r in recipe_templates() if r['id']==data.get('recipe_id')),None)
    if not recipe:raise HTTPException(400,'Ricetta senza associazioni verificate')
    disabled=data.get('disabled_products',[])
    allowed={c['source']+':'+c['id'] for i in recipe['ingredients'] for c in i['candidates']}
    if not isinstance(disabled,list) or any(not isinstance(p,str) or p not in allowed for p in disabled):raise HTTPException(400,'Prodotti esclusi non validi')
    config={k:data[k] for k in ['targets','flexibility','scale_min','scale_max'] if k in data}
    config.update(excluded_crea_ids=profile.get('excluded_crea_ids',[]),disabled_products=disabled)
    try:formulate_recipe(recipe,config)
    except (ValueError,KeyError,TypeError) as e:raise HTTPException(400,str(e))
    if solver_lock.locked():raise HTTPException(409,'Calcolo già in corso: riprova fra poco')
    async with solver_lock:
        command=optees_command()
        try:
            async with stdio_client(StdioServerParameters(command=command)) as (read,write):
                async with ClientSession(read,write) as session:
                    await session.initialize();result=await optimize_recipe(session,recipe,config)
        except Exception as e:
            print('Recipe solver error:',repr(e),flush=True)
            raise HTTPException(422,'Calcolo della ricetta non riuscito; dettagli nel terminale locale.')
        result['profile_mode']=profile['mode'];result['demo']=True
        with connect() as db:
            db.execute('INSERT INTO recipe_runs(user_id,created,payload) VALUES(?,?,?)',(user['id'],time.time(),json.dumps(result)))
    return result
