"""Weekly signed deviations, conservative intervals and explicit decisions."""
import asyncio
import copy
import json
import unittest
from unittest.mock import patch
import test_meal_rebalance as base
import meal_rebalance as rebalance
from plan_diet_day import load_foods
from test_recipe_solver import solve


class DiaryRebalance(base.RebalanceAPI):
    def request(self):return dict(date=self.start,from_diary=True)
    def log(self,action,slot,**data):
        with self.app.connect() as db:return self.app.diary.diary_mutation(db,self.user,self.profile,action,dict(date=self.start,slot=slot,**data))
    def test_pasta_twenty_grams_is_below_threshold(self):
        self.log('confirm','lunch')
        with self.app.connect() as db:
            entry=db.execute("SELECT id FROM diary_entry WHERE user_id=? AND slot='lunch' ORDER BY id",(self.user,)).fetchone()[0]
            self.app.diary.diary_mutation(db,self.user,self.profile,'edit',dict(grams=145),entry)
        p=self.proposal(self.request())['result']
        self.assertEqual(p['status'],'unchanged',p);self.assertEqual(p['days'],[])
        self.assertGreater(p['budget']['excess_kcal']['min'],0);self.assertLess(p['budget']['excess_kcal']['max'],100)
        self.assertEqual(p['limits']['minimum_weekly_deviation_kcal'],100)

    def test_added_apple_and_skipped_dinner_offset_and_return_calories(self):
        self.log('confirm','morning_snack')
        self.log('add','morning_snack',food=dict(source='CREA',id='007150'),grams=150)
        self.log('skip','dinner')
        with self.app.connect() as db:before=[dict(r) for r in db.execute('SELECT * FROM diary_entry WHERE user_id=? ORDER BY id',(self.user,))]
        proposal=self.proposal(self.request());p=proposal['result']
        self.assertIn(p['status'],('partial','full'),p)
        self.assertLess(p['budget']['excess_kcal']['max'],0);self.assertLess(p['budget']['correction_kcal'],0)
        self.assertEqual(len(p['deviations']),2)
        self.assertAlmostEqual(p['budget']['excess_kcal']['min'],sum(d['difference_kcal']['min'] for d in p['deviations']))
        for day in p['days']:
            self.assertLessEqual(day['after_kcal'],day['before_kcal']+200.001)
            self.assertLessEqual(day['after_kcal'],self.profile['daily_meals']['targets']['kcal_100g']['max']+.001)
            self.assertGreaterEqual(day['nutrients']['protein_g'],45)
            self.assertLessEqual(day['reduction_kcal'],0)
        cuts=[d['reduction_kcal'] for d in p['days']];self.assertLessEqual(max(cuts)-min(cuts),25.001)
        with self.app.connect() as db:
            answer=rebalance.decide(db,self.user,self.profile,'diary-apply',proposal,'apply')
            self.assertIsNone(answer['recorded']);self.assertEqual(answer['status'],'closed')
            self.assertEqual(before,[dict(r) for r in db.execute('SELECT * FROM diary_entry WHERE user_id=? ORDER BY id',(self.user,))])
            self.assertEqual(self.app.diary.state(db,self.user,self.start,'dinner'),'skipped')
            self.assertEqual(db.execute('SELECT count(*) FROM consumed_estimate WHERE user_id=?',(self.user,)).fetchone()[0],0)
        # Repeat analysis accounts for the already-applied return, never twice.
        repeat=self.proposal(self.request())['result']
        self.assertAlmostEqual(repeat['budget']['previous_correction_kcal'],p['budget']['correction_kcal'])
        self.assertAlmostEqual(repeat['budget']['excess_kcal']['min'],p['budget']['excess_kcal']['min']-p['budget']['correction_kcal'])
        self.assertGreaterEqual(repeat['budget']['excess_kcal']['min'],p['budget']['excess_kcal']['min'])
        self.assertLessEqual(abs(repeat['budget']['correction_kcal']),abs(repeat['budget']['excess_kcal']['max'])+.001)

    def test_keep_from_diary_changes_no_diary_or_plan_and_is_single_use(self):
        self.log('skip','dinner');proposal=self.proposal(self.request());self.app.rebalance_previews['diary-keep']=proposal
        with self.app.connect() as db:
            before={table:[dict(r) for r in db.execute('SELECT * FROM '+table)] for table in ('planned_meal','meal_log','diary_entry','consumed_estimate','week_plan')}
        answer=self.client.post('/api/rebalance/diary-keep/keep',json={},headers=self.headers)
        self.assertEqual(answer.status_code,200,answer.text);self.assertIsNone(answer.json()['recorded']);self.assertEqual(answer.json()['changed_days'],[])
        with self.app.connect() as db:
            for table,rows in before.items():self.assertEqual(rows,[dict(r) for r in db.execute('SELECT * FROM '+table)])
        self.assertEqual(self.client.post('/api/rebalance/diary-keep/keep',json={},headers=self.headers).status_code,409)
        self.assertEqual(self.client.post('/api/rebalance/diary-keep/apply',json={}).status_code,403)

    def test_negative_interval_never_returns_more_than_guaranteed_deficit(self):
        with self.app.connect() as db:baseline=rebalance.snapshot(db,self.user,self.profile,self.meal)['original_kcal']
        meal=rebalance.estimate(dict(date=self.start,slot='dinner',custom=dict(kcal=dict(min=baseline-400,max=baseline-200),protein_g=30,fat_g=20,carbs_available_g=70)),self.today)
        original=self.proposal(meal)
        with self.app.connect() as db:rebalance.decide(db,self.user,self.profile,'negative-estimate',original,'keep')
        p=self.proposal(self.request())['result'];self.assertEqual(p['status'],'partial',p)
        self.assertLess(p['budget']['correction_kcal'],0);self.assertGreaterEqual(p['budget']['correction_kcal'],-200.001)
        self.assertEqual(p['budget']['excess_kcal'],dict(min=-400,max=-200))

    def test_preset_preview_includes_prior_deviations_once(self):
        self.log('skip','lunch')
        with self.app.connect() as db:original=rebalance.snapshot(db,self.user,self.profile,self.meal)['original_kcal']
        meal=rebalance.estimate(dict(date=self.start,slot='dinner',custom=dict(kcal=original+300,protein_g=80,fat_g=100,carbs_available_g=300)),self.today)
        p=self.proposal(meal)['result']
        self.assertEqual(len(p['deviations']),2)
        self.assertLess(p['budget']['excess_kcal']['max'],0)
        # Reference already includes the skipped lunch; only the new dinner is added.
        self.assertAlmostEqual(p['budget']['after_week_kcal']['min'],p['budget']['reference_week_kcal']['min']+300-p['budget']['correction_kcal'],places=2)

    def test_threshold_boundary_and_uncertain_direction_leave_plan_unchanged(self):
        with self.app.connect() as db:baseline=rebalance.snapshot(db,self.user,self.profile,self.meal)['original_kcal']
        for kcal in (baseline+100,baseline-100,dict(min=baseline-300,max=baseline+300)):
            with self.subTest(kcal=kcal):
                meal=rebalance.estimate(dict(date=self.start,slot='dinner',custom=dict(kcal=kcal,protein_g=30,fat_g=20,carbs_available_g=70)),self.today)
                p=self.proposal(meal)['result']
                self.assertEqual(p['status'],'unchanged');self.assertEqual(p['budget']['correction_kcal'],0);self.assertEqual(p['days'],[])

    def test_positive_deviation_preserves_past_and_future_recorded_meals(self):
        self.log('confirm','lunch')
        self.log('add','lunch',food=dict(source='CREA',id='000800'),grams=100)
        future='2026-10-06'
        with self.app.connect() as db:
            self.app.diary.diary_mutation(db,self.user,self.profile,'confirm',dict(date=future,slot='dinner'))
            past=[dict(r) for r in db.execute('SELECT * FROM planned_meal WHERE date=?',(self.start,))]
            entries=[dict(r) for r in db.execute('SELECT * FROM diary_entry WHERE user_id=?',(self.user,))]
            recorded=dict(self.app.diary.planned(db,self.user,future,'dinner'))
        proposal=self.proposal(self.request());p=proposal['result'];self.assertIn(p['status'],('full','partial'),p)
        self.assertGreater(p['budget']['correction_kcal'],0)
        self.assertLessEqual(p['budget']['correction_kcal'],p['budget']['excess_kcal']['min']+.001)
        with self.app.connect() as db:
            rebalance.decide(db,self.user,self.profile,'positive-recorded',proposal,'apply')
            self.assertEqual(past,[dict(r) for r in db.execute('SELECT * FROM planned_meal WHERE date=?',(self.start,))])
            self.assertEqual(entries,[dict(r) for r in db.execute('SELECT * FROM diary_entry WHERE user_id=?',(self.user,))])
            self.assertEqual(recorded,dict(self.app.diary.planned(db,self.user,future,'dinner')))
        self.assertEqual(self.proposal(self.request())['result']['status'],'unchanged')

    def test_missing_recorded_nutrients_are_unavailable(self):
        self.log('confirm','lunch')
        with self.app.connect() as db:snap=rebalance.snapshot(db,self.user,self.profile,self.request())
        lunch=next(m for m in snap['views'][0]['meals'] if m['slot']=='lunch');lunch['eaten']['protein_g']=None
        async def fake(_,problem):return solve(problem)
        with patch('plan_diet_day.solve_problem',side_effect=fake),patch.object(self.app.diary,'local_today',return_value=self.today):
            result=asyncio.run(rebalance.preview(None,self.profile,self.request(),snap,self.app.make_config,load_foods()))
        self.assertEqual(result['status'],'unavailable');self.assertIn('Nutrienti mancanti',result['reason']);self.assertEqual(result['days'],[])

    def test_http_diary_preview_read_only_and_request_validation(self):
        self.log('skip','dinner')
        with self.app.connect() as db:before='\n'.join(db.iterdump())
        async def fake(_,problem):return solve(problem)
        with patch('plan_diet_day.solve_problem',side_effect=fake),patch.object(self.app.diary,'local_today',return_value=self.today):
            response=self.client.post('/api/rebalance/preview',json=self.request(),headers=self.headers)
        self.assertEqual(response.status_code,200,response.text);self.assertEqual(response.json()['source'],'diary')
        with self.app.connect() as db:self.assertEqual(before,'\n'.join(db.iterdump()))
        self.assertEqual(self.client.post('/api/rebalance/preview',json=dict(self.request(),slot='dinner'),headers=self.headers).status_code,400)
        self.assertEqual(self.client.post('/api/rebalance/preview',json=self.request()).status_code,403)
        with self.app.connect() as db:self.app.diary.diary_mutation(db,self.user,self.profile,'reset',dict(date=self.start,slot='dinner'))
        self.assertEqual(self.client.post('/api/rebalance/'+response.json()['preview_id']+'/apply',json={},headers=self.headers).status_code,409)


for name in tuple(vars(base.RebalanceAPI)):
    if name.startswith('test_'):setattr(DiaryRebalance,name,None)
