import copy
import datetime as dt
import sys
import unittest
from pathlib import Path
from zoneinfo import ZoneInfo
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from joint_energy import non_workout_baseline,day_scenarios
from health_inputs import refresh_report,algorithm_inputs


class JointEnergy(unittest.TestCase):
    def test_old_summary_upgrades_from_private_database_without_reopening_zip(self):
        import json
        import tempfile
        from apple_health import import_zip
        from health_inputs import load_report
        from test_apple_health import export,record
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory);archive=path/'health.zip'
            export(archive,[record('ActiveEnergyBurned',600,'kcal','2026-10-01 00:00:00 +0200','2026-10-02 00:00:00 +0200'),record('BasalEnergyBurned',1500,'kcal','2026-10-01 00:00:00 +0200','2026-10-02 00:00:00 +0200')])
            imported=import_zip(archive,path/'private',{'user_id':123})
            old=copy.deepcopy(imported);old.pop('non_workout_scenarios');old['analysis_version']='old'
            summary=path/'private/summary.json';summary.write_text(json.dumps(old));archive.unlink()
            upgraded=load_report(path/'private')
            self.assertIn('non_workout_scenarios',upgraded);self.assertEqual(upgraded['import'],imported['import'])
            self.assertEqual(summary.stat().st_mode&0o777,0o600)
    def inputs(self):
        days=[];workouts=[];zone=ZoneInfo('Europe/Rome')
        for i in range(14):
            day=dt.date(2026,9,20)+dt.timedelta(days=i);start=dt.datetime.combine(day,dt.time(12),zone).timestamp()
            days.append(dict(date=day.isoformat(),usable_for_baseline=True,active_kcal=600,resting_kcal=1500,total_estimated_kcal=2100))
            workouts.append(dict(start=start,end=start+1800,date=day.isoformat(),active_kcal=300))
        return days,workouts
    def test_remove_observed_then_add_planned_once_with_provenance(self):
        days,workouts=self.inputs();net=non_workout_baseline(days,workouts,'Europe/Rome',dt.date(2026,10,4))
        self.assertEqual(net['valid_days'],14);self.assertEqual(net['central_kcal'],1800)
        model=dict(activity='HKWorkoutActivityTypeCycling',status='provisional',observations=14,age_days=1,kcal_per_min_p20=8,kcal_per_min_p50=10,kcal_per_min_p80=12)
        health=dict(non_workout_consumption_scenarios=net,workout_energy_models=[model])
        sessions=[dict(session_id='continuous_stationary-bike',session=dict(duration_seconds=1800))]
        energy=day_scenarios(health,sessions)
        self.assertEqual(energy['consumption_kcal'],dict(low=2040,central=2100,high=2160));self.assertTrue(energy['double_counting_prevented'])
        self.assertEqual(day_scenarios(health,[])['consumption_kcal']['central'],1800)
        self.assertEqual(energy['sessions'][0]['observations'],14)
    def test_missing_overlap_and_more_than_active_are_excluded(self):
        days,workouts=self.inputs();workouts[0]['active_kcal']=None;workouts.append(copy.deepcopy(workouts[1]));workouts[2]['active_kcal']=700
        net=non_workout_baseline(days,workouts,'Europe/Rome',dt.date(2026,10,4))
        self.assertEqual(net['valid_days'],11);self.assertEqual(len(net['excluded_days']),3)
        self.assertEqual(net['central_kcal'],1800)
    def test_midnight_split_and_unavailable_models_are_not_zero(self):
        days,workouts=self.inputs();zone=ZoneInfo('Europe/Rome')
        workouts=[];start=dt.datetime(2026,9,20,23,30,tzinfo=zone).timestamp()
        workouts.append(dict(start=start,end=start+3600,date='2026-09-20',active_kcal=300))
        net=non_workout_baseline(days,workouts,'Europe/Rome',dt.date(2026,10,4))
        self.assertEqual(sum(d['observed_workout_kcal'] for d in net['daily']),300)
        self.assertEqual(net['daily'][0]['non_workout_kcal'],1950);self.assertEqual(net['daily'][1]['non_workout_kcal'],1950)
        missing=day_scenarios(dict(non_workout_consumption_scenarios=net,workout_energy_models=[]),[dict(session_id='strength_dumbbells',session=dict(duration_seconds=1800))])
        self.assertEqual(missing['status'],'unavailable');self.assertNotIn('consumption_kcal',missing)
    def test_net_baseline_expires_without_modifying_targets(self):
        days,workouts=self.inputs();net=non_workout_baseline(days,workouts,'Europe/Rome',dt.date(2026,10,4))
        report=dict(timezone='Europe/Rome',as_of='2026-10-04',measures={},scenarios=dict(valid_days=14),windows=[dict(days=28,end_date='2026-10-03')],workout_forecasts=[],non_workout_scenarios=net)
        updated=refresh_report(report,today=dt.date(2026,11,1));self.assertEqual(updated['non_workout_scenarios']['status'],'insufficient_or_stale')
        inputs=algorithm_inputs(updated);self.assertEqual(inputs['nutritional_targets'],'unchanged_requires_goal_configuration')
        self.assertEqual(report['non_workout_scenarios']['status'],'available')
