import asyncio
import copy
import datetime as dt
import unittest
from unittest.mock import patch
from load_curve import curve,prescribe
from test_recipe_solver import solve
import test_activities as activity_tests
import workout_service as workouts

class LoadCurveTests(unittest.TestCase):
    def anchor(self):return dict(heavy=dict(kg=25,reps=5,date='2026-10-01'),light=dict(kg=20,reps=12,date='2026-10-01'))
    def test_two_anchors_fit_and_single_and_invalid_fall_back(self):
        model=curve(self.anchor(),today=dt.date(2026,10,6))
        self.assertAlmostEqual(model['k'],23)
        self.assertAlmostEqual(model['M']/(1+5/model['k']),25)
        self.assertAlmostEqual(model['M']/(1+12/model['k']),20)
        single=curve(dict(heavy=self.anchor()['heavy']),today=dt.date(2026,10,6))
        self.assertEqual(single['k'],30)
        invalid=self.anchor();invalid['light']['kg']=25
        self.assertTrue(curve(invalid,today=dt.date(2026,10,6))['warnings'])
    def test_load_rounds_down_and_missing_grid_is_not_invented(self):
        model=curve(self.anchor(),today=dt.date(2026,10,6))
        result=prescribe(model,8,2,[5,10,15,20,25])
        self.assertEqual(result['load_kg'],20)
        self.assertLessEqual(result['load_kg'],result['estimated_kg'])
        self.assertEqual(prescribe(model,8,2,[100])['status'],'unavailable')
        self.assertEqual(prescribe(model,None,2,[10])['status'],'unavailable')
    def test_robust_logs_weekly_cap_is_stable_on_regeneration(self):
        logs=[dict(date='2026-10-06',kg=30,reps=5,rpe=8) for _ in range(8)]+[dict(date='2026-10-06',kg=999,reps=5,rpe=9)]
        model=curve(self.anchor(),logs,dt.date(2026,10,6))
        self.assertLessEqual(model['M'],model['reference_M']*1.05)
        self.assertEqual(model,curve(self.anchor(),logs,dt.date(2026,10,6)))
        self.assertLess(model['M'],40)
    def test_double_activities_obey_actual_gap_and_duration(self):
        profile,data=activity_tests.ActivityTests().data();profile['goals']['activity'].update(max_session_minutes=20,max_sessions_per_day=2,min_gap_hours=4)
        first=data['week_start'];data.update(days={d:40 if d==first else 0 for d in data['days']},sessions_min=2,sessions_max=2,cardio_minutes_min=40,weekly_minutes_max=40,start_times={first:['08:00','14:00']})
        async def fake(session,p):
            model=copy.deepcopy(p)
            if model['objective']['sense']=='max':model['objective']['coefficients']=[-c for c in model['objective']['coefficients']]
            return solve(model)
        with patch('plan_diet_day.solve_problem',side_effect=fake):result=asyncio.run(workouts.generate_week(None,profile,data))
        self.assertTrue(result['plans'],result)
        for plan in result['plans']:
            items=sorted(plan['workout_sessions'],key=lambda s:s['start_time'])
            self.assertEqual(len(items),2)
            self.assertTrue(all(s['minutes']==20 for s in items))
            self.assertEqual([s['start_time'] for s in items],['08:00','14:00'])
            self.assertEqual(len({s['date'] for s in items}),1)
        data['start_times'][first]=['08:00','09:00']
        with patch('plan_diet_day.solve_problem',side_effect=fake):bad=asyncio.run(workouts.generate_week(None,profile,data))
        self.assertEqual(bad['status'],'infeasible')
    def test_double_strength_uses_recovery_days_and_new_protocols_are_short(self):
        profile,data=activity_tests.ActivityTests().data();profile['goals']=dict(activity=dict(gym='yes',max_session_minutes=30,max_sessions_per_day=2,min_gap_hours=4))
        profile['_workout_settings']['equipment']=['manubri']
        data.pop('activities',None);first=data['week_start'];data.update(days={d:60 if d==first else 0 for d in data['days']},allowed_protocols=['strength_sets'],sessions_min=2,sessions_max=2,strength_sessions_min=2,strength_sessions_max=2,cardio_minutes_min=0,weekly_minutes_max=60,start_times={first:['08:00','14:00']})
        async def fake(session,p):
            model=copy.deepcopy(p)
            if model['objective']['sense']=='max':model['objective']['coefficients']=[-c for c in model['objective']['coefficients']]
            return solve(model)
        with patch('plan_diet_day.solve_problem',side_effect=fake):result=asyncio.run(workouts.generate_week(None,profile,data))
        self.assertTrue(result['plans'],result)
        self.assertTrue(all(len(p['workout_sessions'])==2 for p in result['plans']))
        catalog=workouts.catalog(profile)
        for identifier in ('supersets_full_body','timed_compound_circuit'):
            template=next(s for s in catalog['templates'] if s['id']==identifier)
            self.assertLess(template['duration_seconds'],40*60)
            self.assertIn('muscles_per_minute',template['efficiency'])
        profile['_workout_settings']['protocol_overrides']={'strength_sets':dict(sets=11)}
        with patch('plan_diet_day.solve_problem',side_effect=fake):bad=asyncio.run(workouts.generate_week(None,profile,data))
        self.assertEqual(bad['status'],'infeasible')

    def test_legacy_single_session_migration_preserves_ids_and_is_repeatable(self):
        import sqlite3
        db=sqlite3.connect(':memory:')
        db.executescript("CREATE TABLE schema_migration(version INTEGER PRIMARY KEY,applied REAL); CREATE TABLE planned_session(id INTEGER PRIMARY KEY,week_plan_id INTEGER,date TEXT,session_id TEXT,minutes REAL,start_time TEXT,status TEXT,snapshot TEXT,UNIQUE(week_plan_id,date)); INSERT INTO planned_session VALUES(7,1,'2026-10-05','old',20,'08:00','done','{}');")
        workouts.migrate(db);workouts.migrate(db)
        self.assertEqual(db.execute('SELECT id,status FROM planned_session').fetchone(),(7,'done'))
        db.execute("INSERT INTO planned_session(week_plan_id,date,session_id,status) VALUES(1,'2026-10-05','second','chosen')")
        self.assertEqual(db.execute('SELECT count(*) FROM planned_session').fetchone()[0],2)
        db.close()
