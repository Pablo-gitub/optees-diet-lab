import asyncio
import copy
import unittest
from unittest.mock import patch
import plan_diet_day as diet
from test_recipe_solver import solve


def problem(minimum=0, mixed=False):
    return dict(version='1', variables=[dict(name='dev0' if not mixed else 'bonus', lb=minimum, ub=1, integrality='C')], constraints=[dict(coefficients=[1], relation='>=', rhs=minimum)], objective=dict(sense='min', coefficients=[1 if not mixed else -1]), solver=dict(time_limit=15))


class NearZeroObjectiveTests(unittest.TestCase):
    def run_problem(self, p, timeout=False):
        calls=[]
        async def fake(session, candidate):
            calls.append(copy.deepcopy(candidate))
            if timeout and len(calls)==1:
                return dict(mathematical_status='not_solved')
            return solve(candidate)
        with patch('plan_diet_day.solve_problem', side_effect=fake):
            result=asyncio.run(diet.optimize_day(None,p))
        return result,calls

    def test_near_zero_uses_single_short_feasibility_solve(self):
        result,calls=self.run_problem(problem())
        self.assertEqual(len(calls),1)
        self.assertEqual(calls[0]['objective']['coefficients'],[0])
        self.assertEqual(calls[0]['solver']['time_limit'],3)
        self.assertEqual(result['mathematical_status'],'optimal')
        self.assertEqual(result['optimality'],'within_absolute_tolerance')
        self.assertLessEqual(result['nutritional_deviation'],result['absolute_tolerance'])

    def test_infeasible_probe_preserves_normal_problem(self):
        p=problem(.1); result,calls=self.run_problem(p)
        self.assertEqual(len(calls),2)
        self.assertEqual(calls[1],p)
        self.assertEqual(result,solve(p))

    def test_timeout_falls_back(self):
        p=problem(.1);result,calls=self.run_problem(p,True)
        self.assertEqual(len(calls),2)
        self.assertEqual(calls[-1],p)
        self.assertEqual(result,solve(p))

    def test_preference_is_locked_before_probe(self):
        p=problem();p['preference_coefficients']=[1]
        result,calls=self.run_problem(p)
        self.assertEqual(len(calls),2)
        self.assertEqual(calls[0]['objective']['coefficients'],[1])
        self.assertEqual(calls[1]['constraints'][-2]['rhs'],1e-7)
        self.assertEqual(result['preference_penalty'],0)

    def test_mixed_objective_has_no_probe(self):
        p=problem(mixed=True);result,calls=self.run_problem(p)
        self.assertEqual(calls,[p])
        self.assertEqual(result,solve(p))

    def test_positive_soft_penalty_is_not_nutritional_deviation(self):
        p=problem();p['variables'][0]['name']='match_dislike_0'
        result,calls=self.run_problem(p)
        self.assertEqual(calls,[p])
        self.assertNotIn('optimality',result)

    def test_timing_preserves_absolute_certificate(self):
        p=problem(.0005)
        p['timing_coefficients']=[1]
        p['timing_kcal_rows']=[[1]]
        result,calls=self.run_problem(p)
        self.assertEqual(len(calls),2)
        self.assertLessEqual(calls[1]['constraints'][-2]['rhs'],result['absolute_tolerance'])
        self.assertEqual(result['optimality'],'within_absolute_tolerance')
        self.assertLessEqual(result['nutritional_deviation'],result['absolute_tolerance'])

    def test_probe_respects_shorter_existing_budget(self):
        p=problem();p['solver']['time_limit']=.5
        _,calls=self.run_problem(p)
        self.assertEqual(calls[0]['solver']['time_limit'],.5)

    def test_adapter_forwards_budget_and_relative_gap(self):
        from types import SimpleNamespace
        p=problem();p['solver']=dict(time_limit=.25,mip_gap=.05)
        raw=SimpleNamespace(success=False,status=1,x=[.1])
        with patch('test_recipe_solver.milp',return_value=raw) as backend:
            result=solve(p)
        self.assertEqual(result['mathematical_status'],'feasible')
        self.assertEqual(backend.call_args.kwargs['options'],dict(time_limit=.25,mip_rel_gap=.05))

    def test_adapter_timeout_without_incumbent_is_not_infeasible(self):
        from types import SimpleNamespace
        with patch('test_recipe_solver.milp',return_value=SimpleNamespace(success=False,status=1,x=None)):
            self.assertEqual(solve(problem())['mathematical_status'],'not_solved')
