import asyncio
import copy
import json
import unittest
from unittest.mock import patch
import nutrient_timing as timing
from plan_diet_day import formulate,load_foods,optimize_day,decode_result
from test_recipe_solver import solve
from test_joint_orchestration import fixture
import test_meal_matches
from week_orchestration import weekly_model,decode_week


def session(minutes=75,start='17:00',cardio=False):
    return dict(session_id='synthetic',start_time=start,session=dict(duration_seconds=minutes*60,cardio_work_seconds=minutes*60 if cardio else 0))

class TimingTests(unittest.TestCase):
    def profile(self):return dict(_filtered_weight_kg=80,meal_timing=dict(mode='auto',meals={}))
    def slots(self):return dict(lunch='planned',dinner='planned')
    def config(self):
        profile,request,make=fixture();profile['daily_meals']['targets']=request['day_targets']['rest'];config=make(profile,0);config['_timing_profile']=self.profile();config['_timing_sessions']=[session()];return config
    def test_eligibility_strict_sixty_start_explicit_and_filtered_weight(self):
        p=self.profile()
        for sessions in ([session(60)],[session(75,None)],[]):self.assertEqual(timing.context(p,sessions,self.slots())['status'],'inactive')
        self.assertEqual(timing.context(p,[session(61)],self.slots())['status'],'active')
        p['meal_timing']['mode']='explicit';self.assertEqual(timing.context(p,[session(30)],self.slots())['status'],'active')
        self.assertEqual(timing.context(p,[],self.slots())['status'],'unavailable')
        p['meal_timing']['explicit_session']=dict(start_time='17:00',duration_minutes=30)
        self.assertEqual(timing.context(p,[],self.slots())['sessions'][0]['session_id'],'profile_explicit')
        del p['_filtered_weight_kg'];self.assertEqual(timing.context(p,[session()],self.slots())['status'],'unavailable')
        p['meal_timing']['mode']='off';self.assertEqual(timing.context(p,[session()],self.slots())['status'],'inactive')
    def test_pre_uses_end_and_post_uses_first_start_and_during_not_planned(self):
        p=self.profile();p['meal_timing']['meals']={'lunch':dict(start_time='12:00',end_time='13:30'),'dinner':dict(start_time='19:30',end_time='20:00')}
        c=timing.context(p,[session(90)],self.slots());self.assertEqual(c['sessions'][0]['before'],'lunch');self.assertEqual(c['sessions'][0]['after'],'dinner');self.assertNotIn('during_suggestion',c['sessions'][0])
        c=timing.context(p,[session(91)],self.slots());self.assertFalse(c['sessions'][0]['during_suggestion']['planned'])
        p['meal_timing']['meals']['lunch']=dict(start_time='13:00',end_time='16:15')
        with self.assertRaises(ValueError):timing.context(p,[session()],self.slots())
        p['meal_timing']['meals']['lunch']=dict(start_time='14:00',end_time='16:15')
        self.assertIsNone(timing.context(p,[session()],self.slots())['sessions'][0]['before'])
        midnight=timing.context(self.profile(),[session(120,'23:00')],self.slots())['sessions'][0];self.assertIsNone(midnight['after']);self.assertIn('seguente',midnight['after_reason'])
    def test_soft_rules_same_energy_grid_targets_and_unknown_fiber(self):
        config=self.config();foods=load_foods();p,choices,slots=formulate(config,foods);initial=solve(p)
        async def fake(s,problem):return solve(problem)
        result=asyncio.run(timing.refine(None,p,initial,fake));a=decode_result(config,p,choices,slots,foods,initial);b=decode_result(config,p,choices,slots,foods,result)
        self.assertEqual(a['nutrients']['kcal'],b['nutrients']['kcal']);self.assertTrue(b['constraint_report']['all_respected']);self.assertEqual(b['meal_timing']['optimization']['status'],'optimal')
        self.assertTrue(all(x['grams']%5==0 for x in b['selections']));self.assertTrue(any(r['id']=='post_protein_min' for r in b['meal_timing']['rules']))
        for f in foods.values():f['fiber_g_100g']=''
        p,choices,slots=formulate(config,foods);result=solve(p);report=decode_result(config,p,choices,slots,foods,result)['meal_timing'];r=next(r for r in report['rules'] if r['id']=='pre_fiber');self.assertIsNone(r['satisfied']);self.assertIsNone(r['observed_g']);self.assertTrue(r['reason'])
    def test_impossible_soft_quota_locked_foods_remain_and_failure_falls_back(self):
        config=self.config();foods=load_foods();plain=copy.deepcopy(config);plain['_timing_sessions']=[];p,c,s=formulate(plain,foods);baseline=decode_result(plain,p,c,s,foods,solve(p))
        config['locked_meals']={slot:[dict(food_id=i['food_id'],grams=i['grams'],source=i['source'],reference_id=i['food_id']) for i in baseline['selections'] if i['meal']==slot] for slot in ('lunch','dinner')}
        config['_timing_profile']['_filtered_weight_kg']=300;p,c,s=formulate(config,foods);result=solve(p);self.assertEqual(result['mathematical_status'],'optimal')
        async def fake(_,p):return solve(p)
        result=asyncio.run(timing.refine(None,p,result,fake));record=decode_result(config,p,c,s,foods,result)
        for slot in ('lunch','dinner'):
            self.assertEqual([(x['food_id'],x['grams']) for x in record['selections'] if x['meal']==slot],[(x['food_id'],x['grams']) for x in baseline['selections'] if x['meal']==slot])
        self.assertTrue(any(r['satisfied'] is False and r['reason'] for r in record['meal_timing']['rules']))
        async def bad(_,p):raise ValueError('synthetic invalid')
        fallback=asyncio.run(timing.refine(None,p,result,bad));self.assertEqual(fallback['result'],result['result']);self.assertEqual(fallback['timing_optimization']['status'],'unavailable')
    def test_redistribution_actually_moves_macros_when_feasible(self):
        # Identical daily totals admit different meal distributions.
        config=self.config();variables=[];rows=[];choices=[]
        foods={'starch':dict(kcal_100g=400,protein_g_100g=0,fat_g_100g=0,carbs_available_g_100g=100,fiber_g_100g=1),
               'protein':dict(kcal_100g=400,protein_g_100g=100,fat_g_100g=0,carbs_available_g_100g=0,fiber_g_100g=0),
               'fat':dict(kcal_100g=900,protein_g_100g=0,fat_g_100g=100,carbs_available_g_100g=0,fiber_g_100g=0)}
        def var(name,lb,ub,kind='C'):
            variables.append(dict(name=name,lb=lb,ub=ub,integrality=kind));return len(variables)-1
        def add(c,r,rhs):rows.append((c,r,rhs))
        y=var('present',1,1,'B')
        for meal in ('lunch','dinner'):
            for food,row in foods.items():
                q=var(meal+'_'+food,0,200,'I');choices.append(dict(meal=meal,food_id=food,q=q,y=y,nutrients=[row[n]/100 for n in ('kcal_100g','protein_g_100g','fat_g_100g','carbs_available_g_100g')]))
        for food,total in (('starch',200),('protein',80),('fat',20)):add({c['q']:1 for c in choices if c['food_id']==food},'=',total)
        costs,energy=timing.add_rules(config,foods,choices,self.slots(),var,add);size=len(variables);dense=lambda row:[row.get(i,0) for i in range(size)]
        p=dict(version='1',variables=variables,constraints=[dict(coefficients=dense(c),relation=r,rhs=v) for c,r,v in rows],objective=dict(sense='min',coefficients=[0]*size),solver=dict(time_limit=5),timing_coefficients=dense(costs),timing_kcal_rows=[dense(r) for r in energy])
        # Valid starting allocation intentionally places fats before the workout.
        fixed=copy.deepcopy(p)
        for c,amount in zip(choices,(50,30,20,150,50,0)):fixed['constraints'].append(dict(coefficients=dense({c['q']:1}),relation='=',rhs=amount))
        first=solve(fixed)
        async def fake(_,problem):return solve(problem)
        result=asyncio.run(timing.refine(None,p,first,fake));self.assertEqual(result['timing_optimization']['status'],'optimal')
        quantities={v['name']:v['value'] for v in result['result']['variables']}
        self.assertGreaterEqual(quantities['lunch_starch'],80);self.assertLessEqual(quantities['lunch_fat'],9);self.assertTrue(20<=quantities['dinner_protein']<=32)
        self.assertEqual(result['timing_optimization']['daily_kcal'],[1300])
        first['mathematical_status']='feasible'
        second=asyncio.run(timing.refine(None,p,first,fake));self.assertEqual(second['mathematical_status'],'feasible');self.assertEqual(second['timing_optimization']['status'],'optimal')

    def test_week_blocks_and_multiobjective_keep_energy_per_day(self):
        profile,request,make=fixture();profile['daily_meals']['targets']=request['day_targets']['rest'];profile.update(self.profile());profile['_timing_sessions_by_date']={'2026-10-05':[session()]};foods=load_foods();p,blocks,_,maximum=weekly_model(profile,request,make,foods)
        first=solve(p)
        async def fake(_,p):return solve(p)
        result=asyncio.run(timing.refine(None,p,first,fake));a=decode_week(p,blocks,foods,first,maximum);b=decode_week(p,blocks,foods,result,maximum)
        self.assertEqual([d['nutrients']['kcal'] for d in a['days']],[d['nutrients']['kcal'] for d in b['days']]);self.assertEqual(b['days'][0]['meal_timing']['status'],'active');self.assertEqual(b['days'][1]['meal_timing']['status'],'inactive')
        from multiobjective_day import solve_strategy
        cfg=self.config();p,c,_=formulate(cfg,load_foods())
        with patch('multiobjective_day.solve_problem',side_effect=fake):r=asyncio.run(solve_strategy(None,p,cfg,c,'minmax'))
        self.assertEqual(r['timing_optimization']['status'],'optimal')

class TimingProfileTests(unittest.TestCase):
    setUp=test_meal_matches.MatchTests.setUp
    tearDown=test_meal_matches.MatchTests.tearDown
    # Reuse temporary DB setup without inheriting the eight match tests.
    def test_profile_validation_preservation_and_dayview(self):
        value=dict(mode='explicit',explicit_session=dict(start_time='17:00',duration_minutes=45),meals={})
        response=self.client.put('/api/profile',json=dict(self.profile,meal_timing=value),headers=self.headers);self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(self.client.get('/api/profile').json()['profile']['meal_timing'],value)
        response=self.client.put('/api/profile',json={k:v for k,v in self.profile.items() if k!='meal_timing'},headers=self.headers);self.assertEqual(response.status_code,200,response.text);self.assertEqual(self.client.get('/api/profile').json()['profile']['meal_timing'],value)
        response=self.client.put('/api/profile',json=dict(self.profile,meal_timing=dict(mode='explicit',meals={'lunch':dict(start_time='25:00',end_time='26:00')})),headers=self.headers);self.assertEqual(response.status_code,400)
        self.assertIsNone(self.client.get('/api/day/2026-10-05').json().get('meal_timing'))

    def test_applied_week_exposes_timing_and_marks_later_changes(self):
        profile,request,make=fixture();profile['daily_meals']['targets']=request['day_targets']['rest'];profile.update(TimingTests().profile());profile['_timing_sessions_by_date']={'2026-10-05':[session()]}
        foods=load_foods();p,blocks,_,maximum=weekly_model(profile,request,make,foods);plan=decode_week(p,blocks,foods,solve(p),maximum);plan['id']=1
        import diary_service as diary
        with self.web.connect() as db:
            result=diary.apply_plan(db,self.user,profile,dict(mode='free',run_id=1,week_start='2026-10-05'),plan,dict(scope='week',plan_id=1))
            self.assertEqual(result['meal_timing']['status'],'active')
            from progress_analysis import invalidate_forecast
            invalidate_forecast(db,self.user,'2026-10-05')
            self.assertEqual(diary.day_view(db,self.user,profile,'2026-10-05')['meal_timing']['status'],'unavailable')
        response=self.client.get('/api/day?date=2026-10-05');self.assertEqual(response.status_code,200,response.text);self.assertEqual(response.json()['meal_timing']['status'],'unavailable')

class TimingJointTests(unittest.TestCase):
    def test_new_joint_workout_is_used_before_application(self):
        import joint_orchestration as joint
        profile,request,make=fixture();profile.update(TimingTests().profile());profile['meal_timing']=dict(mode='explicit',meals={})
        request['k']=1;request['workout']['start_times']={d:'17:00' for d in joint.dates(request['week_start'])}
        async def fake(_,p):return solve(p)
        with patch('plan_diet_day.solve_problem',side_effect=fake):result=asyncio.run(joint.generate_week(None,profile,request,make,load_foods()))
        self.assertTrue(result['plans'],result)
        for day in result['plans'][0]['days']:
            self.assertEqual(day['meal_timing']['status'],'active' if day['workout_sessions'] else 'unavailable')
            if day['workout_sessions']:self.assertEqual(day['meal_timing']['sessions'][0]['start_minutes'],17*60)
