import asyncio
import json
import time
from unittest.mock import patch
import test_diary_service as diary_tests
from test_recipe_solver import solve


class PersonalWorkoutConfiguration(diary_tests.DiaryTests):
    def settings(self,**data):
        return self.client.patch('/api/workouts/config',json=data,headers=self.headers)

    def catalog(self):return self.client.get('/api/workouts/catalog').json()
    def template(self,identifier):return next(t for t in self.catalog()['templates'] if t['id']==identifier)

    def test_new_profile_has_no_inherited_equipment_loads_or_readiness(self):
        response=self.client.get('/api/workouts/config');self.assertEqual(response.status_code,200)
        result=response.json();self.assertIsNone(result['settings']['level']);self.assertIsNone(result['settings']['equipment'])
        self.assertEqual(result['settings']['starting_loads_kg'],{})
        self.assertTrue(all(not s['personal_configuration_complete'] for s in result['sessions']))
        self.assertTrue(any(q['field']=='level' and q['prompt'] for q in result['missing_fields']))
        self.assertTrue(any(q['field']=='variants.inverted-row' and q['choices']==['feet_on_floor'] for q in result['missing_fields']))
        self.assertFalse(self.template('strength_dumbbells')['equipment_feasible'])
        for t in self.catalog()['templates']:self.assertTrue(t['demo']);self.assertTrue(all(e['load_kg'] is None for e in t['exercises']))
        self.assertEqual(self.client.patch('/api/workouts/config',json={}).status_code,403)

    def test_declared_loads_variants_and_protocol_parameters_are_used(self):
        variants={key:dict(variant='standard',executable=True) for key in ('dumbbell-floor-press','dumbbell-deadlift')}
        response=self.settings(level='beginner',equipment=['manubri'],available_loads_kg=[4,6,8],starting_loads_kg={'dumbbell-floor-press':4,'dumbbell-deadlift':6},variants=variants,intensity_confirmed=True,protocol_overrides={'strength_sets':{'sets':2,'reps':4,'rest_seconds':120}})
        self.assertEqual(response.status_code,200,response.text)
        template=self.template('strength_dumbbells');self.assertTrue(template['personal_configuration_complete'])
        self.assertEqual(template['pending_configuration'],[]);self.assertTrue(template['demo'])
        self.assertEqual([e['load_kg'] for e in template['exercises']],[4,6]);self.assertTrue(all(e['sets']==2 and e['repetitions']==4 for e in template['exercises']))
        self.assertEqual(template['duration_seconds'],300+30+2*(2*16+120)+30+180)
        self.assertEqual(template['parameter_provenance'],'user_overrides_with_demo_defaults')
        self.assertTrue(all(e['load_basis']=='kg_per_dumbbell' for e in template['exercises']))
        # A change to the generic diet profile must not erase workout settings.
        self.assertEqual(self.client.put('/api/profile',json=self.profile,headers=self.headers).status_code,200)
        self.assertEqual(self.client.get('/api/workouts/config').json()['settings']['starting_loads_kg']['dumbbell-deadlift'],6)

    def test_invalid_changes_are_atomic_and_dont_invent_loads(self):
        initial=self.client.get('/api/workouts/config').json()['settings']
        for data in [dict(level='expert'),dict(equipment=['invented']),dict(equipment=['manubri','manubri']),dict(starting_loads_kg={'dumbbell-deadlift':10}),dict(available_loads_kg=[True]),dict(variants={'push-up':dict(variant='handstand',executable=True)}),dict(protocol_overrides={'emom_basic':{'reps':30}}),dict(protocol_overrides={'strength_sets':{'sets':1.5}}),dict(intensity_confirmed='yes'),dict(level=[]),dict(available_loads_kg=[5,5])]:
            r=self.settings(**data);self.assertEqual(r.status_code,400,r.text)
            self.assertEqual(self.client.get('/api/workouts/config').json()['settings'],initial)
        r=self.settings(equipment=['manubri']);self.assertEqual(r.status_code,200)
        prompts=r.json()['workout_configuration']['missing_fields'];self.assertTrue(any(p['field']=='available_loads_kg' for p in prompts))
        self.assertTrue(any(p['field']=='starting_loads_kg.dumbbell-floor-press' for p in prompts))
        self.assertIsNone(self.template('strength_dumbbells')['exercises'][0]['load_kg'])

    def test_australian_setup_executable_variants_and_high_intensity_filter(self):
        variants={k:dict(variant='feet_on_floor' if k=='inverted-row' else 'knees' if k=='push-up' else 'standard',executable=True) for k in ('inverted-row','push-up','bodyweight-squat')}
        self.assertEqual(self.settings(level='beginner',equipment=['barra_trazioni'],variants=variants,intensity_confirmed=True).status_code,200)
        self.assertFalse(self.template('hypertrophy_basic')['equipment_feasible'])
        self.assertEqual(self.settings(australian_pullups_setup_verified=True).status_code,200)
        t=self.template('hypertrophy_basic');self.assertTrue(t['personal_configuration_complete']);self.assertEqual(t['exercises'][1]['variant'],'knees')
        variants['push-up']['executable']=False;self.settings(variants=variants)
        self.assertFalse(self.template('hypertrophy_basic')['equipment_feasible'])
        # Hard declarations still apply to demo candidates.
        from plan_workout_week import formulate
        from pathlib import Path
        cfg=json.loads((self.app.ROOT/'config/demo-week.json').read_text());cfg.update(sessions_min=1,sessions_max=1,strength_sessions_min=1,cardio_minutes_min=0,allowed_protocols=['hypertrophy_sets'])
        with self.assertRaises(ValueError):formulate(cfg,self.catalog(),'time')
        self.settings(equipment=['cyclette'],variants={'stationary-bike':dict(variant='standard',executable=True)})
        cfg.update(strength_sessions_min=0,allowed_protocols=['cardio_hiit'],allow_high_intensity_demo=True)
        with self.assertRaises(ValueError):formulate(cfg,self.catalog(),'time')
        self.settings(high_intensity_ready=True)
        _,slots=formulate(cfg,self.catalog(),'time');self.assertTrue(all(s['format']=='intervals' for _,s in slots))

    def test_personal_week_requires_configuration_but_remains_demo(self):
        from test_workout_api import WorkoutAPI
        request=WorkoutAPI.request(self);request.update(demo=False,sessions_min=1,sessions_max=1,strength_sessions_min=1,strength_sessions_max=1,cardio_minutes_min=0,allowed_protocols=['isometric_basic'])
        async def fake(session,p):return solve(p)
        def run():
            with self.app.connect() as db:
                user=db.execute('SELECT * FROM users WHERE id=?',(self.user,)).fetchone()
            return asyncio.run(self.app.workouts.generate_week(None,self.app.owner_profile(user),request))
        with patch('plan_diet_day.solve_problem',side_effect=fake):
            self.assertEqual(run()['status'],'infeasible')
            self.settings(level='beginner',equipment=[],intensity_confirmed=True,variants={'plank':dict(variant='standard',executable=True)})
            result=run();self.assertTrue(result['plans'])
            self.assertTrue(result['demo']);self.assertTrue(result['require_personal_configuration'])
            for p in result['plans']:
                self.assertTrue(all(s['session']['personal_configuration_complete'] and s['session']['demo'] for s in p['workout_sessions']))

    def test_configuration_is_private_and_does_not_mutate_started_snapshot(self):
        self.settings(level='intermediate',equipment=[],variants={'plank':dict(variant='standard',executable=True)},intensity_confirmed=True,starting_loads_kg={'plank':0})
        reply=self.client.post('/api/workouts/start',json=dict(session_id='isometric_core',date=self.date),headers=self.headers)
        self.assertEqual(reply.status_code,200,reply.text);log=reply.json()['workout_log_id']
        self.settings(protocol_overrides={'isometric_basic':{'hold_seconds':30}})
        detail=self.client.get(f'/api/workouts/logs/{log}').json();self.assertEqual(detail['session']['exercises'][0]['hold_seconds'],20)
        self.assertEqual(detail['session']['exercises'][0]['load_kg'],0)
        name='other'+str(time.time_ns());self.assertEqual(self.client.post('/api/register',json=dict(username=name,password='test-password-123')).status_code,200);self.client.post('/api/login',json=dict(username=name,password='test-password-123'))
        other=self.client.get('/api/workouts/config').json()['settings'];self.assertIsNone(other['level']);self.assertEqual(other['starting_loads_kg'],{});self.assertIsNone(other['equipment'])

    def test_legacy_inventory_transfer_is_once_only_and_never_fills_loads(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as directory, self.app.connect() as db:
            path=Path(directory)/'equipment.json';path.write_text(json.dumps(dict(equipment=['barra_trazioni','manubri'],requirements=dict(australian_pullups_setup_verified=True))))
            self.app.workout_settings.seed_legacy_equipment(db,self.user,path)
            settings=self.app.workout_settings.read(db,self.user)
            self.assertEqual(settings['equipment'],['barra_trazioni','manubri']);self.assertTrue(settings['australian_pullups_setup_verified'])
            self.assertIsNone(settings['level']);self.assertEqual(settings['starting_loads_kg'],{})
            path.write_text(json.dumps(dict(equipment=['cyclette'])))
            self.app.workout_settings.seed_legacy_equipment(db,self.user,path)
            self.assertEqual(self.app.workout_settings.read(db,self.user),settings)

    def test_changed_configuration_rejects_old_candidate_without_writing_plan(self):
        with self.app.connect() as db:
            user=db.execute('SELECT * FROM users WHERE id=?',(self.user,)).fetchone()
            payload=dict(kind='workout',mode='free',week_start=self.date,configuration_hash=self.app.workouts.configuration_hash(self.app.owner_profile(user)),plans=[dict(id=1234,workout_sessions=[])])
            set_id=db.execute('INSERT INTO plan_set(user_id,created,payload,input) VALUES(?,?,?,?)',(self.user,0,'{}','{}')).lastrowid
            payload['run_id']=str(set_id);db.execute('UPDATE plan_set SET payload=? WHERE id=?',(json.dumps(payload),set_id))
        self.settings(equipment=[])
        response=self.client.post(f'/api/plan-sets/{set_id}/apply',json=dict(plan_id=1234,scope='week'),headers=self.headers)
        self.assertEqual(response.status_code,409,response.text);self.assertEqual(response.json()['code'],'configuration_changed')
        with self.app.connect() as db:self.assertEqual(db.execute('SELECT count(*) FROM planned_session').fetchone()[0],0)


for name in tuple(vars(diary_tests.DiaryTests)):
    if name.startswith('test_'):setattr(PersonalWorkoutConfiguration,name,None)
