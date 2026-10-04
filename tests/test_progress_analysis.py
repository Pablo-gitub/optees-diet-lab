import datetime as dt
import math
import statistics
import unittest
from progress_analysis import weight_series,comparison


def weights(start,n=30,noise=True):
    return [dict(date=(start+dt.timedelta(days=i)).isoformat(),kind='weight',unit='kg',value=80-.02*i+(.3 if i%2 else -.3) if noise else 80-.02*i,source='manual') for i in range(n)]


class ProgressFilters(unittest.TestCase):
    def test_noisy_series_keeps_raw_and_reduces_oscillation(self):
        raw=weights(dt.date(2026,8,1));result=weight_series(raw,dt.date(2026,8,31))
        self.assertEqual(result['status'],'available');self.assertEqual(len(result['raw_points']),30)
        pts=result['daily_points'];raw_steps=[pts[i]['value']-pts[i-1]['value'] for i in range(1,30)];filtered_steps=[pts[i]['filtered_kg']-pts[i-1]['filtered_kg'] for i in range(1,30)]
        self.assertLess(statistics.pstdev(filtered_steps),statistics.pstdev(raw_steps)/2)
        self.assertTrue(all(math.isfinite(p['filter_variance_kg2']) and p['filter_variance_kg2']>0 for p in pts));self.assertLess(result['trend_7d'],0)
    def test_repeated_day_uses_median_once_and_manual_priority(self):
        raw=[dict(date='2026-09-01',kind='weight',unit='kg',value=v,source=s) for v,s in [(80,'manual'),(82,'manual'),(100,'apple_health')]]
        result=weight_series(raw,dt.date(2026,9,1))
        self.assertEqual(len(result['raw_points']),3);self.assertEqual(len(result['points']),1)
        self.assertEqual(result['value'],81);self.assertEqual(result['daily_points'][0]['aggregation_count'],2)
    def test_holes_are_not_filled_and_large_gaps_reset(self):
        raw=weights(dt.date(2026,8,1),noise=False);raw=[p for p in raw if p['date'] in ('2026-08-01','2026-08-03','2026-08-30')]
        result=weight_series(raw,dt.date(2026,8,30));self.assertEqual(len(result['points']),3)
        self.assertEqual(result['daily_points'][1]['gap_days'],2);self.assertTrue(result['daily_points'][-1]['reset'])
        self.assertIsNone(result['trend_7d']);self.assertEqual(result['trend_status'],'insufficient_data')
        self.assertEqual(weight_series(raw,dt.date(2026,10,1))['status'],'insufficient_data')
        self.assertEqual(weight_series([],dt.date(2026,10,1))['raw_points'],[])
    def test_comparison_separates_deviation_and_response_and_missing(self):
        week=dict(week_start='2026-09-07',week_end='2026-09-13',diet=dict(status='available',value=.7),training=dict(planned=0,status='insufficient_data'))
        self.assertEqual(comparison(week,{},dict(status='insufficient_data'),dt.date(2026,9,14))['classification'],'plan_not_followed')
        week['diet']['value']=1
        weight=dict(daily_points=[dict(date='2026-09-07',filtered_kg=80,filter_variance_kg2=.01),dict(date='2026-09-14',filtered_kg=82,filter_variance_kg2=.01)])
        expected=dict(status='available',points=[dict(central_kg=80,low_kg=79.9,high_kg=80.1)])
        self.assertEqual(comparison(week,weight,expected,dt.date(2026,9,14))['classification'],'response_differs_from_expected')
        weight['daily_points'][-1]['filtered_kg']=80.1
        self.assertEqual(comparison(week,weight,expected,dt.date(2026,9,14))['classification'],'within_expected_uncertainty')
        week['diet']['status']='insufficient_data'
        self.assertEqual(comparison(week,weight,expected,dt.date(2026,9,14))['status'],'insufficient_data')

    def test_known_linear_decline_with_noise_tracks_weekly_slope(self):
        import random
        randomizer=random.Random(42);start=dt.date(2026,8,1)
        raw=[dict(date=(start+dt.timedelta(days=i)).isoformat(),kind='weight',unit='kg',value=80-.3*i/7+randomizer.gauss(0,.04),source='manual') for i in range(35)]
        result=weight_series(raw,start+dt.timedelta(days=34))
        self.assertAlmostEqual(result['trend_7d'],-.3,delta=.08)
        self.assertLess(abs(result['daily_points'][-1]['filtered_kg']-(80-.3*34/7)),.15)
        self.assertEqual(result['parameters']['version'],'progress-v2')
        self.assertEqual(result['parameters']['filter_input'],'daily_median')
