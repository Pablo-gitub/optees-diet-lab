"""Profile-owned breakfast/snack choices; whole-day constraints, not diet approval."""
import math

DAILY_TARGETS={
 'kcal_100g':dict(min=1400,target=1800,max=2400),
 'protein_g_100g':dict(min=45,target=80,max=140),
 'fat_g_100g':dict(min=25,target=60,max=90),
 'carbs_available_g_100g':dict(min=90,target=235,max=300),
}

def defaults(personal=False):
 import copy
 return dict(enabled=personal,allow_second_bar=False,afternoon_fruit=True,banana_min_g=100,banana_max_g=220,targets=copy.deepcopy(DAILY_TARGETS),targets_demo=True,policy='personalized_habits')


def validate(settings):
 if not isinstance(settings,dict):raise ValueError('Configurazione colazione/spuntini non valida')
 for key in ['enabled','allow_second_bar','afternoon_fruit','targets_demo']:
  if not isinstance(settings.get(key),bool):raise ValueError('Opzione non valida: '+key)
 if settings.get('policy')!='personalized_habits':raise ValueError('Modalità colazione/spuntini non implementata')
 low=settings.get('banana_min_g');high=settings.get('banana_max_g')
 if any(isinstance(x,bool) or not isinstance(x,(int,float)) or not math.isfinite(x) for x in [low,high]) or not 20<=low<=high<=500:raise ValueError('Porzioni banana: 20–500 g edibili, minimo ≤ massimo')
 targets=settings.get('targets')
 if not isinstance(targets,dict) or set(targets)!=set(DAILY_TARGETS):raise ValueError('Obiettivi giornalieri incompleti')
 for n,s in targets.items():
  if not isinstance(s,dict):raise ValueError('Obiettivo giornaliero non valido')
  xs=[s.get(k) for k in ['min','target','max']]
  if any(isinstance(x,bool) or not isinstance(x,(int,float)) or not math.isfinite(x) for x in xs) or not 0<=xs[0]<=xs[1]<=xs[2]<=10000 or xs[1]==0:raise ValueError('Obiettivo giornaliero non valido: '+n)
 return settings


def products(preferences):
 result={}
 for p in preferences.get('products',[]):
  serving=p['serving_g'];basis=p['label_basis_g'];label=p['label_nutrients']
  if not isinstance(serving,(int,float)) or serving<=0 or not isinstance(basis,(int,float)) or basis<=0:raise ValueError('Etichetta personale non valida')
  values=[p['kcal_per_serving']/serving*100,label['protein_g']/basis*100,label['fat_g']/basis*100,label['carbs_g']/basis*100]
  if any(not math.isfinite(v) or v<0 for v in values):raise ValueError('Nutrienti etichetta personale non validi')
  result[p['id']]=dict(name=p['name'],source='user_label',source_id=p['id'],serving_g=serving,
   kcal_100g=str(values[0]),protein_g_100g=str(values[1]),fat_g_100g=str(values[2]),carbs_available_g_100g=str(values[3]))
 return result


def add_choices(config,foods,var,add,choices):
 settings=validate(config['daily_meals']);prefs=config.get('food_preferences',{});local=products(prefs)
 foods.update({'personal:'+k:v for k,v in local.items()})
 preferences=prefs.get('preferences',{});cost={}
 for meal in ['breakfast','morning_snack','afternoon_snack']:
  if meal=='afternoon_snack' and not settings['afternoon_fruit']:continue
  requested=preferences.get(meal,{}).get('preferred_product_id')
  options=[]
  if requested:
   if requested not in local:raise ValueError('Prodotto preferito senza etichetta completa: '+meal)
   p=local[requested];options.append(('personal:'+requested,p['serving_g'],p['serving_g'],0))
   if meal=='breakfast' and settings['allow_second_bar']:
    options.append(('personal:'+requested,2*p['serving_g'],2*p['serving_g'],.1))
  if '007510' not in config.get('excluded_crea_ids',[]):
   options.append(('007510',settings['banana_min_g'],settings['banana_max_g'],1 if requested else 0))
  if not options:raise ValueError('Nessuna scelta disponibile per '+meal)
  ys=[]
  for option,(food_id,low,high,penalty) in enumerate(options):
   food=foods[food_id]
   values=[float(food[n])/100 for n in ['kcal_100g','protein_g_100g','fat_g_100g','carbs_available_g_100g']]
   if any(not math.isfinite(v) or v<0 for v in values):raise ValueError('Nutrienti mancanti nello spuntino')
   y=var(f'{meal}_choice_{option}',0,1,'B');q=var(f'{meal}_grams_{option}',0,high);ys.append(y)
   add({q:1,y:-high},'<=',0);add({q:1,y:-low},'>=',0)
   cost[y]=penalty
   choices.append(dict(meal=meal,combination='personalized_habits',branch_index=option,group=0,food_id=food_id,y=y,q=q,nutrients=values,
    source=food.get('source','CREA'),preferred=penalty==0,units=round(low/food['serving_g']) if food_id.startswith('personal:') else None))
  add({y:1 for y in ys},'=',1)
 return cost
