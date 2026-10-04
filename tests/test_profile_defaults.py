import json
from unittest.mock import patch
import test_diary_service as base
from test_daily_meals import preference_fixture
from test_joint_orchestration import fixture


class ProfileDefaults(base.DiaryTests):
    def test_new_unsaved_profile_has_identical_defaults_for_ui_and_owner(self):
        with self.app.connect() as db:
            row=db.execute('SELECT * FROM users WHERE id=?',(self.user,)).fetchone()
        self.assertNotIn('daily_meals',json.loads(row['profile']))
        self.assertEqual(self.client.get('/api/profile').json()['profile']['daily_meals'],self.app.owner_profile(row)['daily_meals'])
        self.assertFalse(self.app.owner_profile(row)['daily_meals']['enabled'])
        # A freshly provisioned personal profile has habits but has never saved settings.
        fresh=json.loads(row['profile']);fresh['food_preferences']=preference_fixture()
        with self.app.connect() as db:
            db.execute('UPDATE users SET profile=? WHERE id=?',(json.dumps(fresh),self.user))
            row=db.execute('SELECT * FROM users WHERE id=?',(self.user,)).fetchone()
        shown=self.client.get('/api/profile').json()['profile']['daily_meals']
        self.assertTrue(shown['enabled']);self.assertEqual(shown,self.app.owner_profile(row)['daily_meals'])
        _,request,_=fixture(self.date)
        async def job(*args):pass
        with patch.object(self.app,'planning_job',side_effect=job):
            response=self.client.post('/api/plans/joint-week',json=request,headers=self.headers)
        self.assertEqual(response.status_code,202,response.text)
        with self.app.connect() as db:
            stored=json.loads(db.execute('SELECT profile FROM users WHERE id=?',(self.user,)).fetchone()['profile'])
        self.assertNotIn('daily_meals',stored)


for name in tuple(vars(base.DiaryTests)):
    if name.startswith('test_'):setattr(ProfileDefaults,name,None)
