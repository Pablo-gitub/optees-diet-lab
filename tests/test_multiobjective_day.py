import asyncio
import copy
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from multiobjective_day import solve_strategy,nondominated,choose_arm
from test_recipe_solver import solve


class MultiobjectiveTests(unittest.TestCase):
    def fixture(self):
        variables=[dict(name=n,lb=0,ub=20,integrality='C') for n in ['x','y','dev0','dev1']]
        rows=[([1,1,0,0],'=',20),([1,0,-1,0],'<=',5),([-1,0,-1,0],'<=',-5),([0,1,0,-1],'<=',10),([0,-1,0,-1],'<=',-10)]
        p=dict(version='1',variables=variables,constraints=[dict(coefficients=c,relation=r,rhs=b) for c,r,b in rows],objective=dict(sense='min',coefficients=[0,0,.2,.1]))
        config={'main_meals_targets':{'kcal_100g':dict(min=0,target=5,max=20),'protein_g_100g':dict(min=0,target=10,max=20)}}
        choices=[dict(q=0,nutrients=[1,0,0,0]),dict(q=1,nutrients=[0,1,0,0])]
        return p,config,choices
    def run_strategy(self,strategy,weights=None):
        p,c,choices=self.fixture();before=copy.deepcopy(p)
        async def fake(session,problem):return solve(problem)
        with patch('multiobjective_day.solve_problem',side_effect=fake):result=asyncio.run(solve_strategy(None,p,c,choices,strategy,weights))
        self.assertEqual(p,before)
        return result
    def test_minmax_and_maxmin_have_distinct_optima(self):
        a=self.run_strategy('minmax');b=self.run_strategy('maxmin')
        x=lambda r:next(v['value'] for v in r['result']['variables'] if v['name']=='x')
        self.assertAlmostEqual(x(a),20/3,places=5)
        self.assertAlmostEqual(x(b),8,places=5)
        self.assertAlmostEqual(a['optimization']['worst_relative_error'],1/3,places=5)
        self.assertAlmostEqual(b['optimization']['minimum_satisfaction'],.8,places=5)
    def test_pareto_preserves_tradeoffs_removes_dominated_and_duplicates(self):
        a=self.run_strategy('pareto',{'kcal':4});b=self.run_strategy('pareto',{'protein_g':4})
        dominated=copy.deepcopy(a);dominated['optimization']['relative_errors']={'kcal':2,'protein_g':2}
        self.assertEqual(len(nondominated([a,b,copy.deepcopy(a),dominated])),2)
    def test_bandit_explores_only_untried_strategies_then_learns(self):
        self.assertEqual(choose_arm([]),('balanced','exploration'))
        self.assertEqual(choose_arm([('balanced',1)]),('minmax','exploration'))
        self.assertEqual(choose_arm([('balanced',0),('minmax',1),('maxmin',0)]),('minmax','ucb1'))
    def test_personal_preferences_have_priority(self):
        p,c,choices=self.fixture();p['preference_coefficients']=[1,0,0,0]
        async def fake(session,problem):return solve(problem)
        with patch('multiobjective_day.solve_problem',side_effect=fake):r=asyncio.run(solve_strategy(None,p,c,choices,'minmax'))
        self.assertLess(next(v['value'] for v in r['result']['variables'] if v['name']=='x'),1e-6)

if __name__=='__main__':unittest.main()
