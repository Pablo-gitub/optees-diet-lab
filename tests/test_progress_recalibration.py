import copy
import unittest
from daily_meals import defaults
import progress_recalibration as recal


class CalibrationLimits(unittest.TestCase):
    def test_extreme_requests_never_exceed_caps_or_minima(self):
        target=defaults(True)['targets']
        for requested in range(-10000,10001,157):
            proposal=recal.target_changes(dict(daily=target),requested)
            if proposal is None:continue
            change=proposal['changes']['daily'];before=change['before'];after=change['after']
            self.assertLessEqual(abs(change['delta_kcal']),min(100,before['kcal_100g']['target']*.05))
            for n,floor in recal.FLOORS.items():
                self.assertGreaterEqual(after[n]['min'],floor);self.assertEqual(after[n]['min'],before[n]['min'])
                self.assertGreaterEqual(after[n]['target'],after[n]['min']);self.assertLessEqual(after[n]['target'],after[n]['max'])
            recal.verify_changes(proposal['changes'])
    def test_day_type_limits_share_the_smallest_budget_and_protect_macros(self):
        daily=defaults(True)['targets'];rest=copy.deepcopy(daily);rest['kcal_100g']['target']=1600;rest['carbs_available_g_100g']['target']=185
        result=recal.target_changes(dict(daily=daily,rest=rest,training=daily),99999)
        self.assertEqual(result['applied_delta_kcal'],80)
        for change in result['changes'].values():
            self.assertEqual(change['before']['protein_g_100g'],change['after']['protein_g_100g'])
            self.assertEqual(change['before']['carbs_available_g_100g'],change['after']['carbs_available_g_100g'])
    def test_floor_boundary_does_not_reduce_and_unsafe_profiles_are_rejected(self):
        target=defaults(True)['targets'];target['kcal_100g'].update(min=1400,target=1400,max=2400);target['carbs_available_g_100g']['target']=135
        self.assertIsNone(recal.target_changes(dict(daily=target),-10000))
        bad=copy.deepcopy(target);bad['protein_g_100g']['min']=0
        with self.assertRaises(ValueError):recal.target_changes(dict(daily=bad),10)
        target=defaults(True)['targets'];proposal=recal.target_changes(dict(daily=target),100)['changes'];proposal['daily']['after']['kcal_100g']['target']=3000
        with self.assertRaises(ValueError):recal.verify_changes(proposal)
