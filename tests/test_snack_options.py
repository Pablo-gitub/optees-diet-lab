"""T-009: contratto proposto delle opzioni; solo catalogo temporaneo e dati sintetici."""
import asyncio
import copy
import json
import importlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import daily_meals
import plan_diet_day as diet
from daily_meals import defaults
from ingredient_overlap import amounts,overlap
from week_orchestration import generate_week
from test_recipe_solver import solve
from test_daily_meals import preference_fixture
from audit_ingredient_overlap import config as audit_config

SLOTS=('breakfast','morning_snack','afternoon_snack')

class SnackOptionsTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.addCleanup(lambda:importlib.reload(daily_meals))
        self.path=Path(self.temp.name)/'snack-options.json'
        self.options=[dict(source='CREA',id=f'900{i:03d}',name='Opzione sintetica '+str(i),
                           group='frutta' if i<6 else 'latticino' if i<9 else 'cereale/cracker',
                           meals=list(SLOTS),portion_min_g=100,portion_max_g=150,
                           portion_source='Porzione sintetica per il contratto, non dati nutrizionali reali') for i in range(12)]
        self.document=dict(version=1,max_occurrences_per_meal=3,options=self.options)
        self.path.write_text(json.dumps(self.document))
        self.config=dict(demo=True,mode='free',day_index=0,excluded_crea_ids=[],portion_bounds_g={},
                         daily_meals=defaults(True),food_preferences={},
                         main_meals_targets=copy.deepcopy(defaults(True)['targets']))
        self.config['portion_bounds_g']=audit_config('free')['portion_bounds_g']
        self.foods=diet.load_foods()
        for option in self.options:
            self.foods[option['id']]=dict(source='CREA',source_id=option['id'],name=option['name'],
                kcal_100g='90',protein_g_100g='1',fat_g_100g='0.3',carbs_available_g_100g='20')
        real_read=Path.read_text
        def read(path,*args,**kwargs):
            if path.name=='snack-options.json':return self.path.read_bytes().decode()
            return real_read(path,*args,**kwargs)
        self.read_patch=patch.object(Path,'read_text',read);self.read_patch.start();self.addCleanup(self.read_patch.stop)
        real_open=Path.open
        def open_path(path,*args,**kwargs):
            return real_open(self.path if path.name=='snack-options.json' else path,*args,**kwargs)
        self.open_patch=patch.object(Path,'open',open_path);self.open_patch.start();self.addCleanup(self.open_patch.stop)

    def day(self):
        importlib.reload(daily_meals)
        foods=copy.deepcopy(self.foods)
        p,c,slots=diet.formulate(self.config,foods)
        async def local(session,problem):return solve(problem)
        with patch.object(diet,'solve_problem',side_effect=local):result=asyncio.run(diet.optimize_day(None,p))
        return diet.decode_result(self.config,p,c,slots,foods,result),c

    def week(self,k=1):
        importlib.reload(daily_meals)
        profile=dict(mode=self.config['mode'],config=copy.deepcopy(self.config))
        def factory(profile,index):
            config=copy.deepcopy(profile['config']);config['day_index']=index;return config
        async def local(session,problem):return solve(problem)
        with patch.object(diet,'solve_problem',side_effect=local):
            return asyncio.run(generate_week(None,profile,dict(week_start='2026-10-05',k=k,pool_size=k,time_limit=120),factory,copy.deepcopy(self.foods)))

    def test_enabled_slots_choose_one_catalog_option_with_five_gram_portions(self):
        plan,choices=self.day();self.assertTrue(plan['constraint_report']['all_respected'])
        allowed={o['id']:o for o in self.options}
        for slot in SLOTS:
            selected=[s for s in plan['selections'] if s['meal']==slot]
            self.assertEqual(len(selected),1)
            self.assertIn(selected[0]['food_id'],allowed)
            option=allowed[selected[0]['food_id']]
            self.assertGreaterEqual(selected[0]['grams'],option['portion_min_g'])
            self.assertLessEqual(selected[0]['grams'],option['portion_max_g'])
            self.assertEqual(selected[0]['grams']%5,0)
        for slot in SLOTS:self.assertEqual({c['food_id'] for c in choices if c['meal']==slot},set(allowed))

    def test_exclusions_and_meal_permissions_remove_candidates(self):
        self.config['excluded_crea_ids']=[self.options[0]['id']]
        self.document['options'][1]['meals']=['afternoon_snack'];self.path.write_text(json.dumps(self.document))
        _,choices=self.day()
        snack=[c for c in choices if c['meal'] in SLOTS]
        self.assertNotIn(self.options[0]['id'],{c['food_id'] for c in snack})
        self.assertIn(self.options[1]['id'],{c['food_id'] for c in snack if c['meal']=='afternoon_snack'})
        self.assertNotIn(self.options[1]['id'],{c['food_id'] for c in snack if c['meal']=='breakfast'})

    def test_weekly_variety_and_per_meal_cap(self):
        self.document.pop('max_occurrences_per_meal');self.path.write_text(json.dumps(self.document))
        result=self.week();self.assertTrue(result['plans'])
        counts={slot:{} for slot in SLOTS};identities=set()
        for day in result['plans'][0]['days']:
            for item in day['selections']:
                if item['meal'] in SLOTS:
                    ids=counts[item['meal']];ids[item['food_id']]=ids.get(item['food_id'],0)+1;identities.add(item['food_id'])
        self.assertGreaterEqual(len(identities),3)
        for count in counts.values():self.assertLessEqual(max(count.values()),3)

    def test_single_option_relaxes_weekly_variety_with_explicit_warning(self):
        self.document['options']=self.options[:1];self.path.write_text(json.dumps(self.document))
        result=self.week();self.assertTrue(result['plans'])
        self.assertTrue(result['plans'][0]['constraint_report']['all_respected'])
        snack=[s for d in result['plans'][0]['days'] for s in d['selections'] if s['meal'] in SLOTS]
        self.assertEqual({s['food_id'] for s in snack},{self.options[0]['id']})
        self.assertTrue(any(any(word in json.dumps(w).lower() for word in ('variet','spuntin','snack')) for w in result.get('warnings',[])),'Il ripiego sulla varietà degli spuntini deve essere visibile')

    def test_preferred_products_keep_fixed_servings_and_penalties(self):
        self.config['food_preferences']=preference_fixture()
        plan,choices=self.day()
        selected={s['meal']:s for s in plan['selections'] if s['meal'] in SLOTS}
        self.assertEqual((selected['breakfast']['food_id'],selected['breakfast']['grams']),('personal:bar',35))
        self.assertEqual((selected['morning_snack']['food_id'],selected['morning_snack']['grams']),('personal:crackers',32))
        self.assertEqual(plan['preference_penalty'],0)
        self.assertIn(self.options[0]['id'],{c['food_id'] for c in choices if c['meal']=='afternoon_snack'})

    def test_existing_banana_bounds_override_catalog_entry(self):
        banana=dict(self.options[0],id='007510',name='Banana sintetica',portion_min_g=80,portion_max_g=250)
        self.document['options']=[banana];self.path.write_text(json.dumps(self.document))
        self.config['daily_meals'].update(banana_min_g=125,banana_max_g=135)
        plan,_=self.day()
        for item in plan['selections']:
            if item['meal'] in SLOTS:
                self.assertEqual(item['food_id'],'007510');self.assertGreaterEqual(item['grams'],125);self.assertLessEqual(item['grams'],135)

    def test_afternoon_switch_disables_all_snack_options(self):
        self.config['daily_meals']['afternoon_fruit']=False
        plan,choices=self.day()
        self.assertEqual(plan['slots']['afternoon_snack'],'not_planned')
        self.assertFalse(any(c['meal']=='afternoon_snack' for c in choices))
        self.assertIn(self.options[0]['id'],{c['food_id'] for c in choices if c['meal']=='morning_snack'})

    def test_overlap_is_measured_before_after_in_free_and_synthetic_proxy(self):
        baseline=dict(version=1,max_occurrences_per_meal=7,options=[dict(self.options[0],id='007510',name='Banana',portion_min_g=100,portion_max_g=220)])
        for mode in ('free','sedentary'):
            with self.subTest(mode=mode):
                self.config['mode']=mode
                if mode!='free':
                    root=Path(self.temp.name)
                    rules=root/'rules.json';schedule=root/'schedule.json'
                    groups=[diet.STARCH,diet.VEG,diet.PROTEIN+diet.LEGUMES,diet.FRUIT]
                    rules.write_text(json.dumps({mode:{'A':[groups]}}))
                    schedule.write_text(json.dumps(dict(weeks=[[dict(lunch='A',dinner='A') for _ in range(7)] for _ in range(2)])))
                    self.config.update(rules_path=str(rules),schedule_path=str(schedule))
                self.path.write_text(json.dumps(baseline));before=self.week(k=3)
                self.path.write_text(json.dumps(self.document));after=self.week(k=3)
                for label,result in [('prima',before),('dopo',after)]:
                    self.assertEqual(len(result['plans']),3)
                    vectors=[amounts(p,self.foods) for p in result['plans']]
                    measured=max(overlap(a,b)*100 for i,a in enumerate(vectors) for b in vectors[:i])
                    self.assertAlmostEqual(measured,result['pool']['overlap_achieved'],places=2)
                    print(f'T-009 {mode} {label}: sovrapposizione {measured:.2f}%; nessuna soglia imposta')
                self.assertTrue(any(s['food_id'].startswith('900') for p in after['plans'] for d in p['days'] for s in d['selections'] if s['meal'] in SLOTS))

    def test_incomplete_catalog_food_is_not_an_option(self):
        self.foods[self.options[0]['id']]['fat_g_100g']=''
        _,choices=self.day()
        ids={c['food_id'] for c in choices if c['meal'] in SLOTS}
        self.assertNotIn(self.options[0]['id'],ids)
        self.assertIn(self.options[1]['id'],ids)

    def test_configured_weekly_limit_is_not_hardcoded_to_three(self):
        self.document['max_occurrences_per_meal']=2;self.path.write_text(json.dumps(self.document))
        result=self.week();self.assertTrue(result['plans'])
        for slot in SLOTS:
            counts={}
            for day in result['plans'][0]['days']:
                for item in day['selections']:
                    if item['meal']==slot:counts[item['food_id']]=counts.get(item['food_id'],0)+1
            self.assertLessEqual(max(counts.values()),2)
