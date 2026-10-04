import importlib.util
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def module(name,path):
 s=importlib.util.spec_from_file_location(name,ROOT/path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
imports=module('recipe_imports','scripts/import_recipes.py')
calc=module('recipe_calc','scripts/calculate_recipe_nutrients.py')
class RecipeTests(unittest.TestCase):
 def recipe(self):return {'id':'test','servings':2,'ingredients':[{'key':'1','grams_whole_recipe':100},{'key':'2','grams_whole_recipe':50}]}
 def maps(self):return {k:{'reviewed':True,'state_checked':True,'source':'CREA','id':k} for k in ['1','2']}
 def food(self,source,id):return {'name':id,'nutrient_basis':'per_100_g','kcal_100g':'200','protein_g_100g':'10','fat_g_100g':'5','carbs_available_g_100g':'30'}
 def test_total_and_per_serving(self):
  r=calc.calculate(self.recipe(),self.maps(),self.food)
  self.assertTrue(r['complete']);self.assertEqual(r['whole_recipe']['kcal'],300);self.assertEqual(r['per_serving']['kcal'],150)
  self.assertEqual(r['diet_eligibility'],'not_checked')
 def test_unknown_mapping_does_not_return_partial_total(self):
  maps=self.maps();del maps['2'];r=calc.calculate(self.recipe(),maps,self.food)
  self.assertFalse(r['complete']);self.assertIsNone(r['per_serving']['kcal'])
 def test_unknown_macronutrient_only_invalidates_that_total(self):
  def food(source,id):
   d=self.food(source,id)
   if id=='2':d['protein_g_100g']=''
   return d
  r=calc.calculate(self.recipe(),self.maps(),food)
  self.assertEqual(r['per_serving']['kcal'],150);self.assertIsNone(r['per_serving']['protein_g']);self.assertFalse(r['complete'])
 def test_liquid_density_and_unreviewed_state(self):
  def liquid(source,id):return dict(self.food(source,id),nutrient_basis='per_100_ml')
  self.assertFalse(calc.calculate(self.recipe(),self.maps(),liquid)['complete'])
  maps=self.maps()
  for m in maps.values():m['density_g_per_ml']=2
  self.assertEqual(calc.calculate(self.recipe(),maps,liquid)['per_serving']['kcal'],75)
  maps['1']['state_checked']=False
  self.assertFalse(calc.calculate(self.recipe(),maps,liquid)['complete'])
 def test_unit_conversion_is_explicit(self):
  self.assertEqual(imports.grams(.25,'kg'),250)
  for unit in ['ml','piece','tsp','toTaste']:self.assertIsNone(imports.grams(1,unit))
 def test_imported_sources_and_cuisines(self):
  unitools=imports.import_unitools();foodose=imports.import_foodose()
  self.assertEqual(len(unitools),501);self.assertEqual(len(foodose),333)
  self.assertEqual(sum(r['cuisine']=='Chinese' for r in unitools),6)
  self.assertEqual(sum(r['cuisine']=='Italian' for r in unitools+foodose),81)
  self.assertTrue(all(not r['solver_eligible'] for r in unitools+foodose))
  self.assertTrue(all(i['key'] for r in foodose for i in r['ingredients']))
if __name__=='__main__':unittest.main()
