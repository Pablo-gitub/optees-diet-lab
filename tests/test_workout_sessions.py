import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from workout_sessions import compile_session,build_sessions,validate_session
from build_workout_catalog import build,REVIEWED
from plan_workout_week import formulate
from test_recipe_solver import solve


class WorkoutSessionsTests(unittest.TestCase):
    def setUp(self):
        self.protocols={p['id']:p for p in json.loads((ROOT/'config/workout-protocols.json').read_text())['protocols']}
        self.index={key:dict(source_id=key,equipment_feasible=True,requirements=req,primary_muscles=['quadriceps'],secondary_muscles=[]) for key,req in REVIEWED.items()}
    def session(self,protocol,movements=None,overrides=None):
        return compile_session('test','Test',self.protocols[protocol],movements or ['bodyweight-squat'],self.index,overrides=overrides,warmup_seconds=0,cooldown_seconds=0,transition_seconds=0)
    def test_traditional_sets_count_only_between_set_rests(self):
        s=self.session('hypertrophy_sets');self.assertEqual(s['duration_seconds'],3*40+2*90)
        self.assertEqual(s['exercises'][0]['repetitions'],10);self.assertEqual(s['intensity']['load_kg'],None);validate_session(s)
    def test_isometry_keeps_seconds_and_no_dynamic_set_score(self):
        s=self.session('isometric_basic',['plank']);self.assertEqual(s['duration_seconds'],3*20+2*40)
        self.assertIsNone(s['exercises'][0]['repetitions']);self.assertEqual(s['score_vector']['muscle_coverage_proxy'],{});self.assertTrue(s['resistance_session'])
    def test_emom_exact_clock_and_rejects_insufficient_recovery(self):
        s=self.session('emom_basic',['push-up','inverted-row']);self.assertEqual(s['duration_seconds'],3*2*60)
        self.assertEqual(s['time_breakdown_seconds']['rest'],3*2*31)
        with self.assertRaises(ValueError):self.session('emom_basic',overrides={'reps':15})
    def test_circuit_accounts_for_station_and_round_changes(self):
        s=self.session('circuit_basic',['bodyweight-squat','push-up']);self.assertEqual(s['duration_seconds'],3*2*30+3*20+2*60+2*20)
        self.assertEqual(s['cardio_work_seconds'],0);self.assertEqual(s['score_vector']['muscle_coverage_proxy'],{})
    def test_hiit_separates_work_recovery_and_pending_readiness(self):
        s=self.session('cardio_hiit',['stationary-bike']);self.assertEqual(s['duration_seconds'],6*(30+90));self.assertEqual(s['cardio_work_seconds'],180)
        self.assertIn('high_intensity_readiness',s['pending_configuration'])
    def test_invalid_numbers_unknown_parameters_and_wrong_method(self):
        for value in [True,-1,float('inf'),float('nan'),1.5]:
            with self.assertRaises(ValueError):self.session('hypertrophy_sets',overrides={'sets':value})
        with self.assertRaises(ValueError):self.session('hypertrophy_sets',overrides={'invented':10})
        with self.assertRaises(ValueError):self.session('cardio_hiit',['push-up'])
        with self.assertRaises(ValueError):self.session('isometric_basic',['push-up'])
    def test_unavailable_equipment_omits_sessions_without_substituting(self):
        self.index['inverted-row']['equipment_feasible']=False
        sessions,missing=build_sessions(self.index)
        self.assertTrue(any(x['id']=='emom_bodyweight' for x in missing))
        self.assertFalse(any(x['id']=='emom_bodyweight' for x in sessions))
    def test_generated_sessions_have_nonoverlapping_complete_timelines(self):
        sessions,missing=build_sessions(self.index);self.assertEqual(len(sessions),11);self.assertEqual(missing,[])
        for s in sessions:validate_session(s);self.assertEqual(s['duration_seconds'],sum(e['duration_seconds'] for e in s['timeline']))
        broken=copy.deepcopy(sessions[0]);broken['timeline'][1]['start_seconds']+=1
        with self.assertRaises(ValueError):validate_session(broken)
    def test_weekly_solver_counts_full_time_but_only_cardio_work(self):
        s=compile_session('bike','Bike',self.protocols['cardio_continuous'],['stationary-bike'],self.index)
        cfg=json.loads((ROOT/'config/demo-week.json').read_text());cfg.update(days={d:28 for d in cfg['days']},sessions_min=1,sessions_max=1,strength_sessions_min=0,strength_sessions_max=0,cardio_minutes_min=20)
        with self.assertRaises(ValueError):formulate(cfg,{'model_version':'workout-sessions-v2','templates':[s]},'time')
        cfg['days']={d:29 for d in cfg['days']};cfg['cardio_minutes_min']=21
        p,_=formulate(cfg,{'model_version':'workout-sessions-v2','templates':[s]},'time');self.assertEqual(solve(p)['mathematical_status'],'infeasible')
        cfg['cardio_minutes_min']=20;p,_=formulate(cfg,{'model_version':'workout-sessions-v2','templates':[s]},'time');self.assertEqual(solve(p)['mathematical_status'],'optimal')
    def test_weekly_rejects_personal_unconfigured_and_filters_goals(self):
        sessions,_=build_sessions(self.index);cfg=json.loads((ROOT/'config/demo-week.json').read_text());cfg['demo']=False
        with self.assertRaises(ValueError):formulate(cfg,{'model_version':'workout-sessions-v2','templates':sessions},'time')
        cfg.update(demo=True,goal='aerobic_endurance',strength_sessions_min=0)
        _,slots=formulate(cfg,{'model_version':'workout-sessions-v2','templates':sessions},'time')
        self.assertTrue(all(t['format']=='continuous' for _,t in slots))

if __name__=='__main__':unittest.main()
