import copy
import datetime as dt
import json
import unittest
from unittest.mock import patch
from test_meal_rebalance import RebalanceAPI
from test_recipe_solver import solve
from plan_diet_day import load_foods
from week_orchestration import weekly_model,decode_week
import recipe_intents

class RecipeIntentTests(RebalanceAPI):
    def setUp(self):
        super().setUp();self.profile['_energy_baseline_low']=1900
    def model(self,request=None,profile=None):
        profile=profile or self.profile;foods=load_foods()
        with patch.object(self.app.diary,'local_today',return_value=self.today):p,b,c,m=weekly_model(profile,dict(week_start=self.start,**(request or {})),self.app.make_config,foods)
        from scipy.optimize import milp,Bounds,LinearConstraint
        import numpy as np
        rows=p['constraints'];lower=[r['rhs'] if r['relation'] in ('=','>=') else -np.inf for r in rows];upper=[r['rhs'] if r['relation'] in ('=','<=') else np.inf for r in rows]
        solution=milp(np.array(p['objective']['coefficients']),integrality=np.array([int(v['integrality']!='C') for v in p['variables']]),bounds=Bounds([v['lb'] for v in p['variables']],[v['ub'] for v in p['variables']]),constraints=LinearConstraint(np.array([r['coefficients'] for r in rows]),lower,upper),options={'time_limit':15,'mip_rel_gap':.0001})
        result=dict(mathematical_status='optimal' if solution.success else 'feasible' if solution.x is not None else 'infeasible',validation={'status':'verified'},result={'variables':[] if solution.x is None else [dict(name=v['name'],value=float(x)) for v,x in zip(p['variables'],solution.x)]})
        return (decode_week(p,b,foods,result,m) if result['mathematical_status'] in ('optimal','feasible') else None),p,b,c
    def test_intent_favorites_are_soft_integer_and_max_two(self):
        self.profile['_preferred_recipe_ids']=['demo:pasta-pomodoro']
        plan,p,_,_=self.model();self.assertIsNotNone(plan)
        selections=[s for d in plan['days'] for s in d['selections'] if s.get('recipe_id')=='demo:pasta-pomodoro']
        self.assertGreater(len(selections),0);self.assertLessEqual(len(selections),2)
        self.assertTrue(all(isinstance(s['units'],int) and 1<=s['units']<=3 for s in selections));self.assertTrue(plan['constraint_report']['all_respected'])
        self.assertTrue(any(v['name'].startswith('d0_recipe_portions') for v in p['variables']))
        self.profile['excluded_crea_ids']=['000800']
        self.profile['_preferred_recipe_ids']=['demo:pasta-pomodoro']
        plan,_,_,_=self.model();self.assertIsNotNone(plan);self.assertFalse(plan['recipe_preferences'][0]['inserted']);self.assertIn('escluso',plan['recipe_preferences'][0]['reason'])
    def test_intent_locked_recipe_and_snapshot_survive_brand_changes(self):
        lock=dict(date='2026-10-07',slot='dinner',recipe=dict(id='demo:pasta-pomodoro',portions=1))
        plan,_,_,_=self.model(dict(locked_dishes=[lock]));self.assertIsNotNone(plan)
        day=next(d for d in plan['days'] if d['date']==lock['date']);recipe=next(s for s in day['selections'] if s['meal']=='dinner')
        self.assertEqual(recipe['units'],1);self.assertIn('dinner',day['locked_slots']);self.assertTrue(plan['anticipatory_rebalance']['limits'])
        with self.app.connect() as db:
            self.app.diary.apply_plan(db,self.user,self.profile,dict(week_start=self.start),plan,dict(scope='week',plan_id=0))
            db.commit()
            owner=self.app.owner_profile(dict(db.execute('SELECT * FROM users WHERE id=?',(self.user,)).fetchone()))
            ref=dict(source='recipe',id=recipe['reference_id']);before=self.app.diary.resolve_food(ref,owner)
            owner['food_preferences']={'preferred_products':{'000800':dict(source='OFF',id='8076800195057')}}
            after=self.app.diary.resolve_food(ref,owner);self.assertEqual(before,after)
            view=self.app.diary.day_view(db,self.user,owner,lock['date']);self.assertTrue(next(m for m in view['meals'] if m['slot']=='dinner')['planned']['locked'])
            from shopping_list import shopping_list
            result=shopping_list(db,self.user,owner,self.start,True,self.today);self.assertFalse(result['unresolved'])
    def test_intent_intervals_protected_and_invalid_presets(self):
        lock=dict(date='2026-10-07',slot='dinner',custom=dict(kcal=dict(min=500,max=600),protein_g=dict(min=25,max=35),fat_g=dict(min=10,max=20),carbs_available_g=dict(min=50,max=65)))
        plan,_,_,_=self.model(dict(locked_dishes=[lock]));self.assertIsNotNone(plan)
        day=next(d for d in plan['days'] if d['date']==lock['date'])
        for key,interval in day['nutrient_ranges'].items():
            spec=day['targets'][key+'_100g'];self.assertGreaterEqual(interval['min'],spec['min']-.001);self.assertLessEqual(interval['max'],spec['max']+.001)
        with self.app.connect() as db:
            self.app.diary.apply_plan(db,self.user,self.profile,dict(week_start=self.start),plan,dict(scope='week',plan_id=0))
            db.commit()
            owner=self.app.owner_profile(dict(db.execute('SELECT * FROM users WHERE id=?',(self.user,)).fetchone()))
            view=self.app.diary.day_view(db,self.user,owner,lock['date']);meal=next(m for m in view['meals'] if m['slot']=='dinner')
            self.assertEqual(meal['planned']['nutrition_basis'],'interval_midpoint');self.assertEqual(meal['planned']['nutrient_ranges']['kcal'],dict(min=500,max=600))
            from shopping_list import shopping_list
            result=shopping_list(db,self.user,owner,self.start,True,self.today);self.assertEqual(result['status'],'partial')
            with patch.object(self.app.diary,'local_today',return_value=dt.date(2026,10,7)):
                consumed=self.app.diary.diary_mutation(db,self.user,owner,'confirm',dict(date=lock['date'],slot='dinner'))
                again=self.app.diary.diary_mutation(db,self.user,owner,'confirm',dict(date=lock['date'],slot='dinner'))
            dinner=next(m for m in consumed['meals'] if m['slot']=='dinner');self.assertIsNone(dinner['eaten']['kcal']);self.assertEqual(dinner['eaten_range']['kcal'],dict(min=500,max=600));self.assertEqual(dinner['state'],'as_planned')
            self.assertEqual(dinner,next(m for m in again['meals'] if m['slot']=='dinner'))
        bad=dict(lock,custom=dict(lock['custom'],protein_g=None))
        self.assertRaises(self.app.diary.DomainError,recipe_intents.validate_lock,self.start,bad,self.profile,self.today)
        missing=dict(lock,preset=dict(id='missing',size='medio'));missing.pop('custom')
        self.assertRaises(self.app.diary.DomainError,recipe_intents.validate_lock,self.start,missing,self.profile,self.today)
    def test_intent_http_preference_lock_delete_and_isolation(self):
        path='/api/recipes/demo:pasta-pomodoro/preferred'
        self.assertEqual(self.client.put(path,json={'preferred':True}).status_code,403)
        self.assertEqual(self.client.put(path,json={'preferred':True},headers=self.headers).status_code,200)
        result=self.client.get('/api/recipes/preferences').json();self.assertTrue(result['recipes'][0]['preferred'])
        self.assertEqual(self.client.put(path,json={'preferred':False},headers=self.headers).status_code,200);self.assertFalse(self.client.get('/api/recipes/preferences').json()['recipes'])
        with patch.object(self.app.diary,'local_today',return_value=self.today):
            response=self.client.put('/api/week/'+self.start+'/locked-dishes',json=dict(date='2026-10-07',slot='dinner',recipe=dict(id='demo:pasta-pomodoro',portions=1)),headers=self.headers)
        self.assertEqual(response.status_code,200,response.text);self.assertEqual(response.json()['effect'],'next_generation_only')
        self.assertEqual(len(self.client.get('/api/week/'+self.start+'/locked-dishes').json()['locked_dishes']),1)
        other=type(self.client)(self.app.app);other.post('/api/register',json=dict(username='synthetic_friend_'+str(self.user),password='test-password-123'));other.post('/api/login',json=dict(username='synthetic_friend_'+str(self.user),password='test-password-123'))
        self.assertFalse(other.get('/api/recipes/preferences').json()['recipes']);self.assertFalse(other.get('/api/week/'+self.start+'/locked-dishes').json()['locked_dishes'])
        self.assertEqual(self.client.delete('/api/week/'+self.start+'/locked-dishes/2026-10-07/dinner',headers=self.headers).status_code,200)
        self.assertFalse(self.client.get('/api/week/'+self.start+'/locked-dishes').json()['locked_dishes'])
    def test_intent_unready_queue_and_no_nutritional_relaxation(self):
        with patch.object(recipe_intents,'catalog_recipe',return_value=dict(id='pending',title='Ricetta sintetica',ingredients=[dict(name='Ingrediente da verificare')])):
            data=recipe_intents.preferences(dict(_preferred_recipe_ids=['pending']));self.assertEqual(data['review_queue'][0]['priority'],'preferred_first');self.assertEqual(data['recipes'][0]['solver_status'],'unavailable')
        lock=dict(date='2026-10-07',slot='dinner',custom=dict(kcal=1800,protein_g=25,fat_g=200,carbs_available_g=50))
        plan,_,_,_=self.model(dict(locked_dishes=[lock]));self.assertIsNone(plan)
        profile=copy.deepcopy(self.profile);profile.pop('_energy_baseline_low')
        self.assertRaises(self.app.diary.DomainError,self.model,dict(locked_dishes=[lock]),profile)

    def test_intent_review_queue_prioritizes_pending_favorite(self):
        from match_recipe_ingredients import build_review_queue
        def recipe(identifier,name,count):
            return dict(id=identifier,title=identifier,ingredients=[dict(canonical_id=name,canonical_name=name,match_status='missing',original_name=name,ingredient_key=str(i),grams=None,quantity_status='requires_estimate',candidates=[],note=None) for i in range(count)])
        values=[recipe('common','usual',5),recipe('preferred','rare',1)]
        self.assertEqual(build_review_queue(values)[0]['canonical_id'],'usual')
        ranked=build_review_queue(values,['preferred']);self.assertEqual(ranked[0]['canonical_id'],'rare');self.assertTrue(ranked[0]['preferred_recipe_priority'])


    def test_intent_normalized_weights_recompute_actual_nutrients(self):
        from calculate_recipe_nutrients import food_lookup
        from recipe_special_sources import special_food
        from plan_diet_day import NUTRIENTS
        recipe=recipe_intents.materialize('demo:pasta-pomodoro',{})
        for n in NUTRIENTS:
            actual=sum(float(food_lookup(p['source'],p['id'])[n])*p['grams']/100 for p in recipe['selections'])
            key='carbs_g' if n=='carbs_available_g_100g' else n.replace('_100g','')
            self.assertAlmostEqual(actual,recipe['nutrients'][key],places=8)
        self.assertAlmostEqual(sum(p['grams'] for p in recipe['selections']),recipe['unit_g'],places=8)
        self.assertEqual(recipe['unit_g']%5,0)


def load_tests(loader,tests,pattern):
    return unittest.TestSuite(RecipeIntentTests(n) for n in RecipeIntentTests.__dict__ if n.startswith('test_intent_'))
