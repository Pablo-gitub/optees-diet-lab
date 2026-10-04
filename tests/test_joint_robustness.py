import asyncio
import copy
import unittest
from unittest.mock import patch
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import joint_robustness as robust


def plan(intake,consumption):
    return dict(days=[dict(nutrients=dict(kcal=intake),energy_scenarios=dict(status='available',consumption_kcal=dict(zip(robust.SCENARIOS,consumption)))) for _ in range(7)])


def envelope(problem,choice=0):
    values=[s['coefficients'][choice] for s in problem['scenarios']]
    return dict(mathematical_status='optimal',validation=dict(status='verified'),result=dict(orientation='minimize_maximum_loss',variables=[dict(name=v['name'],value=int(i==choice)) for i,v in enumerate(problem['variables'])],scenario_values=[dict(scenario_id=s['id'],value=value,is_binding=value==max(values)) for s,value in zip(problem['scenarios'],values)],guaranteed_value=max(values)))


class JointRobustness(unittest.TestCase):
    def test_mean_absolute_errors_do_not_cancel(self):
        p=plan(2000,[2000]*3)
        for i,d in enumerate(p['days']):d['nutrients']['kcal']+=100 if i<3 else -100
        robust.annotate([p],0)
        self.assertEqual(p['robustness']['max_loss_kcal'],100)
    def test_missing_balance_is_not_zero_and_incomplete_candidates_excluded(self):
        a=plan(2000,[1800,2000,2200]);b=copy.deepcopy(a)
        self.assertEqual(robust.annotate([a],None),[])
        b['days'][0]['energy_scenarios']['status']='unavailable'
        self.assertEqual(robust.annotate([a,b],0),[a]);self.assertEqual(a['robustness']['max_regret_kcal'],0)
        self.assertNotIn('max_loss_kcal',b['robustness'])
    def test_min_max_and_regret_can_select_different_plans(self):
        a=plan(2000,[1990,1990,1900]);b=plan(2000,[1920,1920,1920]);c=plan(2000,[1900,1900,2000])
        robust.annotate([a,b,c],0)
        self.assertEqual(min([a,b,c],key=lambda p:p['robustness']['max_loss_kcal']),b)
        self.assertEqual(min([a,b,c],key=lambda p:p['robustness']['max_regret_kcal']),b)
        # Asymmetric scenario minima make minimax regret differ from minimax loss.
        a['robustness']['scenarios']=dict(low=0,central=100,high=100)
        b['robustness']['scenarios']=dict(low=60,central=90,high=90)
        minima=dict(low=0,central=90,high=90)
        for p in (a,b):p['robustness']['regret_scenarios']={s:p['robustness']['scenarios'][s]-minima[s] for s in robust.SCENARIOS}
        self.assertEqual(robust.verify(robust.problem_for([a,b],'scenarios'),envelope(robust.problem_for([a,b],'scenarios'),1))['candidate_index'],1)
        self.assertEqual(robust.verify(robust.problem_for([a,b],'regret_scenarios'),envelope(robust.problem_for([a,b],'regret_scenarios'),0))['candidate_index'],0)
    def test_independent_verification_rejects_mixtures_wrong_values_and_false_optimum(self):
        pool=[plan(2000,[1900]*3),plan(2000,[1950]*3)];robust.annotate(pool,0);problem=robust.problem_for(pool,'scenarios')
        good=envelope(problem,1);self.assertTrue(robust.verify(problem,good)['verified'])
        mixture=copy.deepcopy(good)
        for v in mixture['result']['variables']:v['value']=.5
        wrong=copy.deepcopy(good);wrong['result']['scenario_values'][0]['value']=0
        guaranteed=copy.deepcopy(good);guaranteed['result']['guaranteed_value']=0
        duplicate=copy.deepcopy(good);duplicate['result']['variables'][0]['name']='pick_1'
        for bad in (mixture,wrong,guaranteed,duplicate,envelope(problem,0)):
            with self.assertRaises(ValueError):robust.verify(problem,bad)
    def test_adapter_invokes_loss_and_regret_and_verifies_both(self):
        pool=[plan(2000,[1900]*3),plan(2000,[1950]*3)]
        async def descriptor(*args):return dict(capability=dict(available=True))
        async def solver(session,problem):return envelope(problem,1)
        with patch.object(robust,'call',side_effect=descriptor),patch.object(robust,'solve',side_effect=solver) as mocked:
            summary=asyncio.run(robust.annotate_pool(None,pool,0))
        self.assertEqual(mocked.call_count,2);self.assertEqual(summary['status'],'verified');self.assertEqual(summary['min_max']['candidate_index'],1)
        self.assertEqual(summary['minimax_regret']['candidate_index'],1)
    def test_single_candidate_and_backend_unavailable_are_explicit(self):
        async def descriptor(*args):return dict(capability=dict(available=False))
        with patch.object(robust,'call',side_effect=descriptor):summary=asyncio.run(robust.annotate_pool(None,[plan(2000,[1900]*3)],0))
        self.assertEqual(summary['status'],'local_finite_pool');self.assertEqual(summary['backend_status'],'unavailable')

    def test_distinct_robust_role_and_session_diff_on_pareto_front(self):
        import joint_orchestration as joint
        a=plan(2000,[1900]*3);b=plan(2000,[1950]*3)
        common=dict(worst_error=.2,preference=1,training_fit=.5,training_minutes=60)
        for i,p in enumerate((a,b)):
            p.update(objectives=dict(common,nutrition_error=i+1,variety=i),workout_sessions=[])
            for j,d in enumerate(p['days']):d.update(date=f'2026-10-{5+j:02d}',selections=[])
        robust.annotate([a,b],0)
        result=dict(pool={},warnings=[])
        with patch('joint_orchestration.plan_diff',return_value={}),patch('week_orchestration.week_keys',return_value=set()):joint.select(result,[a,b],dict(k=2))
        self.assertEqual([p['role'] for p in result['plans']],['best','robust'])
        self.assertIn('sessions_moved',result['plans'][1]['diff'])

    def test_full_week_energy_scenarios_feed_the_robust_adapter(self):
        from test_joint_orchestration import fixture
        from plan_diet_day import load_foods
        from test_recipe_solver import solve as milp_solve
        import joint_orchestration as joint
        profile,request,make_config=fixture();request['energy_balance_target_kcal']=0
        health=dict(non_workout_consumption_scenarios=dict(status='available',source='synthetic_health',low_kcal=1800,central_kcal=1900,high_kcal=2000),workout_energy_models=[dict(activity='HKWorkoutActivityTypeCycling',status='provisional',observations=4,age_days=1,kcal_per_min_p20=5,kcal_per_min_p50=6,kcal_per_min_p80=7)])
        async def diet_solver(session,problem):return milp_solve(problem)
        async def descriptor(*args):return dict(capability=dict(available=True))
        async def selector(session,problem):
            choice=min(range(len(problem['variables'])),key=lambda i:max(s['coefficients'][i] for s in problem['scenarios']))
            return envelope(problem,choice)
        with patch('plan_diet_day.solve_problem',side_effect=diet_solver),patch.object(robust,'call',side_effect=descriptor),patch.object(robust,'solve',side_effect=selector):result=asyncio.run(joint.generate_week(None,profile,request,make_config,load_foods(),health))
        self.assertEqual(result['robust_selection']['status'],'verified')
        self.assertTrue(all(p['robustness']['status']=='available' for p in result['plans']))

    def test_explore_prefers_different_workout_and_explains_food_only_fallback(self):
        import joint_orchestration as joint
        def candidate(index,workout):
            p=plan(2000,[1900]*3)
            p.update(objectives=dict(nutrition_error=index+1,worst_error=.2,preference=1,variety=index,training_fit=.5,training_minutes=60),workout_sessions=[dict(date='2026-10-05',session_id=workout)],robustness=dict(status='unavailable'),arms=['food:'+str(index)])
            for j,d in enumerate(p['days']):d.update(date=f'2026-10-{5+j:02d}',selections=[])
            return p
        for different in (True,False):
            pool=[candidate(0,'bike'),candidate(3,'bike'),candidate(2,'bike'),candidate(1,'row' if different else 'bike')]
            result=dict(pool={},warnings=[])
            with patch('joint_orchestration.plan_diff',return_value={}),patch('week_orchestration.week_keys',return_value=set()),patch('joint_orchestration.exploration_score',side_effect=lambda p,o:(p['objectives']['variety'],)):
                joint.select(result,pool,dict(k=3))
            explored=next(p for p in result['plans'] if p['role']=='explore')
            if different:self.assertEqual(explored['workout_sessions'][0]['session_id'],'row')
            else:self.assertTrue(any('Esplorazione alimentare' in reason for reason in explored['explanation']['reasons']))
