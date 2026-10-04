"""Regression B1: HTTP week → application → meal alternatives, with real Optees."""
import json
import shutil
import time
from unittest.mock import patch
from fastapi.testclient import TestClient
import test_diary_service as diary_tests
import test_week_orchestration as week_tests


class WeekMealEndToEnd(diary_tests.DiaryTests):
    # Inherit authentication/database setup, not the parent test methods.
    def test_applied_week_then_meal_alternatives_real_optees(self):
        from optees_command import optees_command
        if not shutil.which(optees_command()):self.skipTest('Optees MCP non installato')
        config=week_tests.WeekOrchestrationTests().profile()['config']
        def make_config(profile,day):return dict(config,day_index=day)
        def wait_job(client,identifier):
            deadline=time.monotonic()+120
            while time.monotonic()<deadline:
                reply=client.get('/api/jobs/'+identifier)
                self.assertEqual(reply.status_code,200)
                job=reply.json()
                if job['state'] in ('done','failed'):
                    self.assertEqual(job['state'],'done',job)
                    return client.get('/api/plan-sets/'+str(job['result']['plan_set_id'])).json()
                time.sleep(.05)
            self.fail('Timeout del job Optees')
        with TestClient(self.app.app) as client, patch.object(self.app,'make_config',side_effect=make_config):
            client.cookies.update(self.client.cookies)
            reply=client.post('/api/plans/week',json=dict(week_start=self.date,mode='free',k=1,pool_size=1),headers=self.headers)
            self.assertEqual(reply.status_code,202,reply.text)
            week=wait_job(client,reply.json()['job_id']);self.assertTrue(week['plans'])
            reply=client.post('/api/plan-sets/'+week['run_id']+'/apply',json=dict(plan_id=week['plans'][0]['id'],scope='week'),headers=self.headers)
            self.assertEqual(reply.status_code,200,reply.text)
            before=client.get('/api/day',params=dict(date=self.date)).json()
            reply=client.post('/api/plans/meal-alternatives',json=dict(date=self.date,slot='lunch'),headers=self.headers)
            self.assertEqual(reply.status_code,202,reply.text)
            alternatives=wait_job(client,reply.json()['job_id']);self.assertTrue(alternatives['plans'])
            for plan in alternatives['plans']:
                self.assertTrue(plan['constraint_report']['all_respected'])
                self.assertTrue(all(s['meal']=='lunch' for s in plan['selections']))
            reply=client.post('/api/plan-sets/'+alternatives['run_id']+'/apply',json=dict(plan_id=alternatives['plans'][0]['id'],scope='meal',date=self.date,slot='lunch'),headers=self.headers)
            self.assertEqual(reply.status_code,200,reply.text)
            after=reply.json()
            self.assertEqual(before['meals'][4],after['meals'][4])
            self.assertIsNone(after['totals']['eaten'])


# Keep only this end-to-end regression in this subclass.
for _name in tuple(vars(diary_tests.DiaryTests)):
    if _name.startswith('test_'):setattr(WeekMealEndToEnd,_name,None)
