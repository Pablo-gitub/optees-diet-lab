import copy
import json
from unittest.mock import patch
import test_meal_rebalance as base
from test_recipe_solver import solve


class RebalanceVerification(base.RebalanceAPI):
    def request(self):return dict(date=self.start,from_diary=True)
    def logged_surplus(self):
        with self.app.connect() as db:
            self.app.diary.diary_mutation(db,self.user,self.profile,'confirm',dict(date=self.start,slot='breakfast'))
            self.app.diary.diary_mutation(db,self.user,self.profile,'add',dict(date=self.start,slot='breakfast',food=dict(source='CREA',id='000800'),grams=100))

    def test_http_result_verification_errors_are_unavailable_without_writes(self):
        self.logged_surplus()
        for variant in ('bounds_first','bounds_second','missing','nan','unverified','decode','safety','unexpected'):
            with self.subTest(variant=variant):
                calls=0
                async def fake(_,problem):
                    nonlocal calls
                    calls+=1;result=solve(problem)
                    if variant.startswith('bounds') and calls==(1 if variant=='bounds_first' else 2):
                        index=next(i for i,v in enumerate(problem['variables']) if 'locked_q' in v['name'])
                        result['result']['variables'][index]['value']=problem['variables'][index]['ub']+5
                    elif variant=='missing':result.pop('result')
                    elif variant=='nan':result['result']['variables'][0]['value']=float('nan')
                    elif variant=='unverified':result['validation']['status']='failed'
                    return result
                from contextlib import ExitStack
                with self.app.connect() as db:before='\n'.join(db.iterdump())
                with ExitStack() as stack:
                    stack.enter_context(patch('plan_diet_day.solve_problem',side_effect=fake))
                    stack.enter_context(patch.object(self.app.diary,'local_today',return_value=self.today))
                    if variant in ('decode','unexpected'):
                        stack.enter_context(patch('meal_rebalance.decode_week',side_effect=ValueError('Vincolo non rispettato') if variant=='decode' else RuntimeError('errore nella verifica')))
                    if variant=='safety':
                        import meal_rebalance
                        real=meal_rebalance.decode_week
                        def unsafe(*args,**kwargs):
                            decoded=real(*args,**kwargs);decoded['days'][0]['nutrients']['kcal']-=500;return decoded
                        stack.enter_context(patch('meal_rebalance.decode_week',side_effect=unsafe))
                    response=self.client.post('/api/rebalance/preview',json=self.request(),headers=self.headers)
                self.assertEqual(response.status_code,200,response.text);result=response.json()
                self.assertEqual(result['status'],'unavailable',result);self.assertTrue(result['reason'])
                self.assertEqual(result['days'],[]);self.assertEqual(result['budget']['correction_kcal'],0);self.assertNotIn('_plan',result)
                self.assertEqual(result['verification']['status'],'failed')
                if variant.startswith('bounds'):
                    self.assertEqual(result['verification']['code'],'variable_out_of_bounds')
                    self.assertTrue(result['verification']['variables']);self.assertIn('date',result['verification']['variables'][0])
                with self.app.connect() as db:self.assertEqual(before,'\n'.join(db.iterdump()))
                self.assertEqual(self.client.post('/api/rebalance/'+result['preview_id']+'/apply',json={},headers=self.headers).status_code,400)

    def test_real_optees_two_applied_rebalances_use_updated_legacy_portions(self):
        # Simulate the old backend: the reference is already outside today's
        # configured pasta range. It remains a legitimate legacy reference.
        with self.app.connect() as db:
            for row in db.execute("SELECT id,items FROM planned_meal WHERE date>? AND slot='lunch' AND week_plan_id IN (SELECT id FROM week_plan WHERE user_id=?)",(self.start,self.user)).fetchall():
                items=json.loads(row['items'])
                for item in items:
                    if item['food']['id']=='000800':item['grams']=45
                db.execute('UPDATE planned_meal SET items=? WHERE id=?',(json.dumps(items),row['id']))
        self.logged_surplus();cumulative={};applied=0
        with patch.object(self.app.diary,'local_today',return_value=self.today):
            for iteration in range(2):
                if iteration:
                    with self.app.connect() as db:self.app.diary.diary_mutation(db,self.user,self.profile,'add',dict(date=self.start,slot='breakfast',food=dict(source='CREA',id='000800'),grams=100))
                with self.app.connect() as db:before='\n'.join(db.iterdump())
                response=self.client.post('/api/rebalance/preview',json=self.request(),headers=self.headers)
                self.assertEqual(response.status_code,200,response.text);result=response.json()
                self.assertIn(result['status'],('full','partial'),result)
                self.assertEqual(result['change_policy']['stage'],'grams')
                with self.app.connect() as db:self.assertEqual(before,'\n'.join(db.iterdump()))
                from rebalance_model import quantities
                for day in result['days']:
                    cumulative[day['date']]=cumulative.get(day['date'],0)+day['reduction_kcal']
                    self.assertLessEqual(cumulative[day['date']],200.001)
                    for change in day['changes']:
                        old=quantities(change['before']);new=quantities(change['after'])
                        self.assertEqual(old.keys(),new.keys())
                        for ref in old:
                            self.assertGreaterEqual(new[ref],old[ref]*.8-.001)
                            self.assertLessEqual(new[ref],old[ref]*1.2+.001)
                            self.assertAlmostEqual((new[ref]-old[ref])%5,0,places=3)
                action=self.client.post('/api/rebalance/'+result['preview_id']+'/apply',json={},headers=self.headers)
                self.assertEqual(action.status_code,200,action.text);applied+=1
            self.assertEqual(applied,2)
            with self.app.connect() as db:self.assertEqual(db.execute("SELECT count(*) FROM rebalance_decision WHERE user_id=? AND decision='apply'",(self.user,)).fetchone()[0],2)

    def test_tiny_legacy_reference_keeps_valid_portion_bounds(self):
        from rebalance_model import build
        from plan_diet_day import load_foods
        with self.app.connect() as db:
            row=self.app.diary.planned(db,self.user,'2026-10-06','lunch');items=json.loads(row['items'])
            for item in items:
                if item['food']['id']=='009210':item['grams']=2
            db.execute('UPDATE planned_meal SET items=? WHERE id=?',(json.dumps(items),row['id']))
            import meal_rebalance
            snap=meal_rebalance.snapshot(db,self.user,self.profile,self.request())
        views=snap['views'][1:]
        p,blocks,choices,_,_=build(self.profile,dict(week_start=self.start,locked=[],_active_dates=[v['date'] for v in views]),self.app.make_config,load_foods(),views,'grams',set())
        for v in p['variables']:self.assertLessEqual(v['lb'],v['ub'])
        choice=next(c for c in choices if c['date']=='2026-10-06' and c['meal']=='lunch' and c['food_id']=='009210')
        self.assertEqual((p['variables'][choice['q']]['lb'],p['variables'][choice['q']]['ub']),(2,2))
        for block in blocks:
            for c in block['choices']:
                global_q=p['variables'][c['q']+block['shift']];local_q=block['problem']['variables'][c['q']]
                self.assertEqual((local_q['lb'],local_q['ub']),(global_q['lb'],global_q['ub']))


for name in tuple(vars(base.RebalanceAPI)):
    if name.startswith('test_'):setattr(RebalanceVerification,name,None)
