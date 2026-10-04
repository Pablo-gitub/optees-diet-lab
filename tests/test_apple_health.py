import datetime as dt
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
import zipfile
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from apple_health import import_zip,normalize,resolve_intervals,split_days,timestamp,summarize
from health_inputs import refresh_report,algorithm_inputs
from zoneinfo import ZoneInfo


def export(path,records,workouts=None):
    root=ET.Element('HealthData')
    for record in records:ET.SubElement(root,'Record',record)
    for attrs,statistics in workouts or []:
        w=ET.SubElement(root,'Workout',attrs)
        for stat in statistics:ET.SubElement(w,'WorkoutStatistics',stat)
    with zipfile.ZipFile(path,'w') as z:z.writestr('apple_health_export/export.xml',ET.tostring(root))


def record(type_,value,unit,start,end,source='Apple Watch'):
    return dict(type='HKQuantityTypeIdentifier'+type_,value=str(value),unit=unit,startDate=start,endDate=end,creationDate=end,sourceName=source)


class HealthTests(unittest.TestCase):
    def test_healthkit_fraction_is_displayed_as_percentage_points(self):
        with tempfile.TemporaryDirectory() as temp:
            temp=Path(temp);export(temp/'h.zip',[record('BodyFatPercentage',.25,'%', '2026-10-01 00:00:00 +0200','2026-10-01 00:00:00 +0200')])
            r=import_zip(temp/'h.zip',temp/'out',{'user_id':1})
            self.assertEqual(r['measures']['body_fat']['value'],25);self.assertEqual(r['measures']['body_fat']['raw_value'],.25)
        with self.assertRaises(ValueError):normalize('body_fat',25,'%')

    def test_units_and_invalid_values(self):
        self.assertAlmostEqual(normalize('active_energy',4184,'kJ'),1000)
        self.assertEqual(normalize('height',1.8,'m'),180)
        for value in ['nan','inf',-1]:
            with self.assertRaises(ValueError):normalize('weight',value,'kg')
        with self.assertRaises(ValueError):normalize('height',1.8,'furlong')
    def test_overlap_priority_and_partial_overlap_are_not_added(self):
        rows=[dict(start=0,end=100,value=100,source='phone',priority=2),dict(start=25,end=75,value=100,source='watch',priority=3)]
        r=resolve_intervals(rows);self.assertEqual(r['value'],150);self.assertEqual(r['covered_seconds'],100);self.assertEqual(r['overlap_seconds'],50)
        self.assertEqual(r['sources'],{'phone':50,'watch':100})
    def test_adjacent_intervals_and_duplicate_watch_samples(self):
        r=resolve_intervals([dict(start=0,end=10,value=10,source='watch',priority=3)]*2+[dict(start=10,end=20,value=20,source='watch',priority=3)])
        self.assertEqual(r['value'],30);self.assertEqual(r['covered_seconds'],20)
    def test_midnight_and_dst_split_preserve_energy(self):
        zone=ZoneInfo('Europe/Rome');start=timestamp('2026-03-28 23:00:00 +0100');end=timestamp('2026-03-30 01:00:00 +0200')
        parts=list(split_days(start,end,2500,zone));self.assertEqual(len(parts),3);self.assertEqual(parts[1][2]-parts[1][1],23*3600);self.assertAlmostEqual(sum(p[3] for p in parts),2500)
    def test_real_import_is_repeatable_and_workouts_do_not_inflate_daily_energy(self):
        with tempfile.TemporaryDirectory() as temp:
            temp=Path(temp);start='2026-10-01 00:00:00 +0200';end='2026-10-02 00:00:00 +0200'
            energy=record('ActiveEnergyBurned',600,'kcal',start,end)
            rows=[energy,energy,record('BasalEnergyBurned',1400,'kcal',start,end),record('BodyMass',80,'kg',start,start),record('Height',1.8,'m',start,start),record('HeartRate',70,'count/min',start,start),record('Height',1.8,'invalid',start,start)]
            workouts=[(dict(workoutActivityType='HKWorkoutActivityTypeCycling',sourceName='Watch',startDate='2026-10-01 10:00:00 +0200',endDate='2026-10-01 10:30:00 +0200',duration='30',durationUnit='min'),[dict(type='HKQuantityTypeIdentifierActiveEnergyBurned',sum='100',unit='kcal')])]
            archive=temp/'health.zip';export(archive,rows,workouts)
            r=import_zip(archive,temp/'result',{'user_id':1});second=import_zip(archive,temp/'result',{'user_id':1})
            self.assertEqual(r,second);self.assertEqual(r['import']['duplicates_skipped'],1);self.assertEqual(r['import']['records_seen'],7)
            self.assertEqual(r['measures']['height']['value'],180);self.assertEqual(r['daily'][0]['total_estimated_kcal'],2000);self.assertEqual(r['workouts'][0]['active_kcal'],100)
            self.assertEqual(r['import']['invalid']['HKQuantityTypeIdentifierHeight'],1)
            db=sqlite3.connect(temp/'result/health.sqlite');self.assertEqual(db.execute('SELECT COUNT(*) FROM energy').fetchone()[0],2)
            report=summarize(db,today=dt.date(2026,10,4));db.close();self.assertEqual(report['windows'][0]['valid_days'],1);self.assertEqual(report['scenarios']['status'],'insufficient_or_stale')
    def test_workout_window_fallback_does_not_use_ambiguous_legacy_energy(self):
        with tempfile.TemporaryDirectory() as temp:
            temp=Path(temp);start='2026-10-01 10:00:00 +0200';end='2026-10-01 10:30:00 +0200'
            w=dict(workoutActivityType='HKWorkoutActivityTypeCycling',startDate=start,endDate=end,duration='30',totalEnergyBurned='999',totalEnergyBurnedUnit='kcal')
            export(temp/'health.zip',[record('ActiveEnergyBurned',100,'kcal',start,end)],[(w,[])])
            r=import_zip(temp/'health.zip',temp/'out',{'user_id':1})
            self.assertEqual(r['workouts'][0]['active_kcal'],100);self.assertEqual(r['workouts'][0]['active_energy_kind'],'energy_samples_in_workout_window')
            self.assertEqual(r['workouts'][0]['legacy_energy']['value'],'999')
    def test_current_days_and_missing_days_are_not_zero_baselines(self):
        with tempfile.TemporaryDirectory() as temp:
            temp=Path(temp);rows=[]
            for day in [1,3]:
                start=f'2026-10-{day:02d} 00:00:00 +0200';end=f'2026-10-{day+1:02d} 00:00:00 +0200'
                rows.extend([record('ActiveEnergyBurned',600,'kcal',start,end),record('BasalEnergyBurned',1400,'kcal',start,end)])
            export(temp/'h.zip',rows);import_zip(temp/'h.zip',temp/'out',{'user_id':1})
            db=sqlite3.connect(temp/'out/health.sqlite');r=summarize(db,today=dt.date(2026,10,3));db.close()
            self.assertEqual(r['windows'][0]['valid_days'],1);self.assertEqual(r['windows'][0]['mean_daily_estimated_kcal'],2000)
    def test_failed_new_import_preserves_previous_snapshot(self):
        with tempfile.TemporaryDirectory() as temp:
            temp=Path(temp);export(temp/'ok.zip',[record('BodyMass',80,'kg','2026-10-01 00:00:00 +0200','2026-10-01 00:00:00 +0200')]);r=import_zip(temp/'ok.zip',temp/'out',{'user_id':1})
            with zipfile.ZipFile(temp/'bad.zip','w') as z:z.writestr('export.xml','<HealthData><Record')
            with self.assertRaises(ET.ParseError):import_zip(temp/'bad.zip',temp/'out',{'user_id':1})
            self.assertEqual(json.loads((temp/'out/summary.json').read_text()),r)
    def test_refresh_separates_active_resting_energy_and_expires_models(self):
        r=dict(timezone='Europe/Rome',as_of='2026-10-01',measures={},scenarios={'valid_days':1,'status':'available'},windows=[{'days':28,'end_date':'2026-10-01','valid_days':1}],daily=[dict(date='2026-10-01',usable_for_baseline=True,active_kcal=500,resting_kcal=1500)],workout_forecasts=[dict(observations=20,age_days=80,status='provisional')])
        refreshed=refresh_report(r,today=dt.date(2026,10,20))
        self.assertEqual(refreshed['windows'][0]['mean_active_kcal'],500)
        self.assertEqual(refreshed['windows'][0]['mean_resting_kcal'],1500)
        self.assertEqual(refreshed['workout_forecasts'][0]['status'],'insufficient_or_stale')
        self.assertEqual(r['workout_forecasts'][0]['age_days'],80)
    def test_cached_baseline_becomes_stale_without_changing_targets(self):
        r=dict(timezone='Europe/Rome',as_of='2026-10-01',measures={},scenarios={'valid_days':20,'status':'available'},windows=[{'days':28,'end_date':'2026-10-01'}],workout_forecasts=[])
        refreshed=refresh_report(r,today=dt.date(2026,11,1));self.assertEqual(refreshed['scenarios']['status'],'insufficient_or_stale');self.assertEqual(r['scenarios']['status'],'available')
        self.assertEqual(algorithm_inputs(refreshed)['nutritional_targets'],'unchanged_requires_goal_configuration')

if __name__=='__main__':unittest.main()
