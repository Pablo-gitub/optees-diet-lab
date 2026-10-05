import asyncio
import copy
import datetime as dt
import json
import unittest
from unittest.mock import patch
import test_diary_service as base
import meal_rebalance as rebalance
from daily_meals import defaults
from plan_diet_day import load_foods
from week_orchestration import weekly_model,decode_week
from test_recipe_solver import solve


class RebalanceAPI(base.DiaryTests):
    def setUp(self):
        super().setUp();self.today=dt.date(2026,10,5);self.start=self.today.isoformat()
        self.profile['mode']='free';self.profile['daily_meals']=defaults(False);self.profile['daily_meals'].update(enabled=True,targets_demo=False)
        with self.app.connect() as db:
            db.execute('UPDATE users SET profile=? WHERE id=?',(json.dumps(self.profile),self.user))
            db.execute('DELETE FROM planned_meal WHERE week_plan_id IN (SELECT id FROM week_plan WHERE user_id=?)',(self.user,));db.execute('DELETE FROM week_plan WHERE user_id=?',(self.user,))
        from test_week_orchestration import WeekOrchestrationTests
        original=self.app.make_config
        bounds=WeekOrchestrationTests().profile()['config']['portion_bounds_g']
        bounds.update({key:[80,150] for key in ('000800','000100','000530')})
        def config(profile,index):
            value=original(profile,index);value['portion_bounds_g']=copy.deepcopy(bounds);return value
        self.app.make_config=config
        selections=[]
        for slot in self.app.diary.SLOTS:
            entries=[('007510',200)] if slot not in ('lunch','dinner') else [('000800',125),('106500' if slot=='lunch' else '121410',120),('005730',100),('009210',15)]
            for identifier,grams in entries:selections.append(dict(meal=slot,food_id=identifier,source='CREA',grams=grams))
        self.plan=dict(id=0,days=[dict(date=date,mode='free',day_index=i,targets=copy.deepcopy(self.profile['daily_meals']['targets']),selections=copy.deepcopy(selections)) for i,date in enumerate(__import__('progress_analysis').days(self.start))])
        for day in self.plan['days']:
            items=[dict(food=dict(source='CREA',id=s['food_id']),grams=s['grams']) for s in day['selections']]
            day['nutrients']=self.app.diary.totals(self.app.diary.enriched(items,self.profile))
        self.plan['targets_by_date']={day['date']:day['targets'] for day in self.plan['days']}
        for day in self.plan['days']:
            day['scope']='full_day_planned_meals';day['energy_scenarios']=dict(status='available',consumption_kcal=dict(low=1900,central=2100,high=2300))
        with self.app.connect() as db:self.app.diary.apply_plan(db,self.user,self.profile,dict(week_start=self.start,mode='free',kind='joint',run_id='0'),self.plan,dict(plan_id=0,scope='week'))
        with self.app.connect() as db:self.profile=self.app.owner_profile(dict(db.execute('SELECT * FROM users WHERE id=?',(self.user,)).fetchone()))
        self.meal=rebalance.estimate(dict(date=self.start,slot='dinner',custom=dict(kcal=2500,protein_g=80,fat_g=100,carbs_available_g=300)),self.today)
    def proposal(self,meal=None):
        with self.app.connect() as db:snap=rebalance.snapshot(db,self.user,self.profile,meal or self.meal)
        async def fake(session,p):return solve(p)
        with patch('plan_diet_day.solve_problem',side_effect=fake),patch.object(self.app.diary,'local_today',return_value=self.today):
            result=asyncio.run(rebalance.preview(None,self.profile,meal or self.meal,snap,self.app.make_config,load_foods()))
        return dict(user=self.user,state=snap['state'],start=self.start,result=result,expires=__import__('time').time()+1800)
    def test_safe_partial_compensation_locks_and_spread(self):
        future='2026-10-06'
        with self.app.connect() as db:
            self.app.diary.diary_mutation(db,self.user,self.profile,'confirm',dict(date=future,slot='breakfast'))
            before=[dict(x) for x in db.execute('SELECT * FROM diary_entry WHERE user_id=?',(self.user,))]
            count=db.total_changes
            snap=rebalance.snapshot(db,self.user,self.profile,self.meal)
            self.assertEqual(db.total_changes,count)
        proposal=self.proposal();result=proposal['result'];self.assertEqual(result['status'],'partial',result)
        reductions=[d['reduction_kcal'] for d in result['days']]
        self.assertGreater(sum(reductions),0);self.assertLessEqual(max(reductions)-min(reductions),25.001)
        for day in result['days']:
            self.assertLessEqual(day['reduction_kcal'],200.001);self.assertGreaterEqual(day['after_kcal'],1400-.001);self.assertGreaterEqual(day['after_kcal'],1900-500-.001)
            self.assertGreaterEqual(day['nutrients']['protein_g'],45-.001)
        self.assertFalse(result['workout']['required'])
        with self.app.connect() as db:
            rebalance.decide(db,self.user,self.profile,'test-apply',proposal,'apply')
            self.assertEqual(before,[dict(x) for x in db.execute('SELECT * FROM diary_entry WHERE user_id=?',(self.user,))])
            view=self.app.diary.day_view(db,self.user,self.profile,self.start)
            dinner=next(m for m in view['meals'] if m['slot']=='dinner')
            self.assertIsNone(dinner['eaten']['kcal']);self.assertEqual(dinner['eaten_range']['kcal']['min'],2500)
            self.assertIsNone(view['totals']['eaten']['kcal'])
    def test_keep_records_interval_without_changing_future_plan_and_stale_is_conflict(self):
        proposal=self.proposal();self.app.rebalance_previews['test-keep']=proposal
        with self.app.connect() as db:before=[dict(r) for r in db.execute('SELECT * FROM planned_meal WHERE date>? AND week_plan_id IN (SELECT id FROM week_plan WHERE user_id=?) ORDER BY id',(self.start,self.user))]
        response=self.client.post('/api/rebalance/test-keep/keep',json={},headers=self.headers)
        self.assertEqual(response.status_code,200,response.text);self.assertEqual(response.json()['changed_days'],[])
        with self.app.connect() as db:
            self.assertEqual(before,[dict(r) for r in db.execute('SELECT * FROM planned_meal WHERE date>? AND week_plan_id IN (SELECT id FROM week_plan WHERE user_id=?) ORDER BY id',(self.start,self.user))])
            self.assertEqual(db.execute('SELECT count(*) FROM consumed_estimate WHERE user_id=?',(self.user,)).fetchone()[0],1)
        self.assertEqual(self.client.post('/api/rebalance/test-keep/keep',json={},headers=self.headers).status_code,409)
        self.assertEqual(self.client.post('/api/rebalance/test-keep/apply',json={}).status_code,403)
    def test_insufficient_health_does_not_propose_cuts_and_diary_change_invalidates(self):
        with self.app.connect() as db:
            db.execute("UPDATE week_plan SET day_context='{}' WHERE user_id=?",(self.user,))
        proposal=self.proposal();self.assertEqual(proposal['result']['status'],'unavailable');self.assertIn('Salute',proposal['result']['reason'])
        self.app.rebalance_previews['stale']=proposal
        with self.app.connect() as db:db.execute('INSERT INTO measurement(user_id,date,kind,value,unit,source) VALUES(?,?,?,80,?,?)',(self.user,self.start,'weight','kg','manual'))
        self.assertEqual(self.client.post('/api/rebalance/stale/keep',json={},headers=self.headers).status_code,409)
    def test_http_preview_with_real_optees_is_read_only(self):
        self.today=dt.date(2026,10,10)
        with self.app.connect() as db:before='\n'.join(db.iterdump())
        with patch.object(self.app.diary,'local_today',return_value=self.today):
            response=self.client.post('/api/rebalance/preview',json=dict(date=self.today.isoformat(),slot='dinner',custom=dict(kcal=2500,protein_g=80,fat_g=100,carbs_available_g=300)),headers=self.headers)
        self.assertEqual(response.status_code,200,response.text)
        result=response.json();self.assertEqual(result['status'],'partial',result)
        self.assertNotIn('_plan',result)
        with self.app.connect() as db:self.assertEqual(before,'\n'.join(db.iterdump()))
        applied=self.client.post('/api/rebalance/'+result['preview_id']+'/apply',json={},headers=self.headers)
        self.assertEqual(applied.status_code,200,applied.text);self.assertTrue(applied.json()['changed_days'])

    def test_interval_cannot_compensate_more_than_guaranteed_surplus(self):
        with self.app.connect() as db:base=rebalance.snapshot(db,self.user,self.profile,self.meal)['original_kcal']
        meal=rebalance.estimate(dict(date=self.start,slot='dinner',custom=dict(kcal=dict(min=base+500,max=base+900),protein_g=80,fat_g=100,carbs_available_g=300)),self.today)
        result=self.proposal(meal)['result']
        self.assertIn(result['status'],('partial','unchanged'),result)
        self.assertLessEqual(result['budget']['correction_kcal'],500.001)

    def test_optional_afternoon_snack_does_not_make_full_day_incomplete(self):
        self.profile['daily_meals']['afternoon_fruit']=False
        with self.app.connect() as db:
            db.execute('UPDATE users SET profile=? WHERE id=?',(json.dumps(self.profile),self.user))
            db.execute("DELETE FROM planned_meal WHERE slot='afternoon_snack' AND week_plan_id IN (SELECT id FROM week_plan WHERE user_id=?)",(self.user,))
        result=self.proposal()['result']
        self.assertEqual(result['status'],'partial',result)
        self.assertIsNotNone(result['budget']['reference_week_kcal'])
        self.assertTrue(all('afternoon_snack' not in [c['slot'] for c in d['changes']] for d in result['days']))

    def test_small_surplus_changes_only_main_meal_grams(self):
        with self.app.connect() as db:base=rebalance.snapshot(db,self.user,self.profile,self.meal)['original_kcal']
        meal=rebalance.estimate(dict(date=self.start,slot='dinner',custom=dict(kcal=base+61,protein_g=80,fat_g=100,carbs_available_g=300)),self.today)
        with patch.dict(rebalance.LIMITS,minimum_weekly_deviation_kcal=0):result=self.proposal(meal)['result']
        self.assertIn(result['status'],('full','partial'),result)
        self.assertEqual(result['change_policy']['stage'],'grams')
        self.assertGreater(result['budget']['correction_kcal'],50)
        from rebalance_model import quantities
        for day in result['days']:
            for change in day['changes']:
                self.assertIn(change['slot'],('lunch','dinner'))
                before=quantities(change['before']);after=quantities(change['after'])
                self.assertEqual(set(before),set(after))
                for key in before:self.assertAlmostEqual((after[key]-before[key])%5,0,places=3)
        self.assertLessEqual(sum(len(d['changes']) for d in result['days']),6)

    def test_pizza_preset_retains_products_and_excludes_future_pizza(self):
        meal=rebalance.estimate(dict(date=self.start,slot='dinner',preset=dict(id='pizzeria',size='medio')),self.today)
        result=self.proposal(meal)['result']
        self.assertIn(result['status'],('partial','full'),result)
        self.assertEqual(result['change_policy']['stage'],'grams')
        self.assertIn('000720',result['change_policy']['excluded_food_ids'])
        for day in result['_plan']['days']:
            self.assertTrue(all('pizza' not in s['food'].lower() for s in day['selections']))
        # The policy applies to all model levels, including substitutions.
        from rebalance_model import build,excluded_dishes
        foods=load_foods();excluded=excluded_dishes(meal,foods)
        with self.app.connect() as db:snap=rebalance.snapshot(db,self.user,self.profile,meal)
        views=snap['views'][1:];dates=[v['date'] for v in views]
        p,_,choices,_,_=build(self.profile,dict(week_start=self.start,locked=[],_active_dates=dates),self.app.make_config,foods,views,'all_meals',excluded)
        self.assertTrue(all(p['variables'][c['y']]['ub']==0 for c in choices if c['food_id'] in excluded))

    def test_missing_preset_refused_before_solver_and_catalog_explicit(self):
        cat=self.client.get('/api/rebalance/presets').json()
        self.assertTrue(all(isinstance(size['available'],bool) for preset in cat['presets'].values() for size in preset['sizes'].values()))
        unavailable=('pizzeria','piccolo');cat['presets']['pizzeria']['sizes']['piccolo']['calories_kcal']=dict(min=None,max=None);cat['presets']['pizzeria']['sizes']['piccolo']['available']=False
        with patch.object(rebalance,'catalog',return_value=cat),patch.object(self.app.diary,'local_today',return_value=self.today):
            response=self.client.post('/api/rebalance/preview',json=dict(date=self.start,slot='dinner',preset=dict(id=unavailable[0],size=unavailable[1])),headers=self.headers)
        self.assertEqual(response.status_code,400,response.text);self.assertEqual(response.json()['code'],'unavailable_preset')
        for bad in (None,dict(min=None,max=100),dict(min=200,max=100),True):
            with self.assertRaises(self.app.diary.DomainError):rebalance.estimate(dict(date=self.start,slot='dinner',custom=dict(kcal=bad,protein_g=10,fat_g=10,carbs_available_g=10)),self.today)

for name in tuple(vars(base.DiaryTests)):
    if name.startswith('test_'):setattr(RebalanceAPI,name,None)
