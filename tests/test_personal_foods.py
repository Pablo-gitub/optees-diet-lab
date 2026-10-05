import json
import unittest
from unittest.mock import patch
import test_diary_service as base
import personal_foods as labels

class PersonalFoods(base.DiaryTests):
    def payload(self,**kwargs):return dict(dict(name='Etichetta test',brand='Marca test',basis='per_100g',kcal=410,protein_g=20,carbs_g=40,fat_g=10,fiber_g=40),**kwargs)
    def create(self,**kwargs):return self.client.post('/api/foods/personal',json=self.payload(**kwargs),headers=self.headers)
    def test_gtin_lengths_checks_and_initial_zero(self):
        for code in ('96385074','036000291452','4006381333931','10012345678902'):
            self.assertEqual(labels.gtin(code),code)
            self.assertEqual(self.client.get('/api/foods/barcode/'+code).status_code,200)
        for code in ('036000291453','123','１２３４５６７８',12345678):
            with self.assertRaises(self.app.diary.DomainError):labels.gtin(code)
    def test_creation_basis_conversion_search_and_barcode_owner_scope(self):
        result=self.create(barcode='036000291452',basis='per_serving',serving_g=50,kj=857.72,kcal=None)
        # Exactly one energy unit is required, not a null alternative.
        self.assertEqual(result.status_code,400)
        data=self.payload(barcode='036000291452',basis='per_serving',serving_g=50,kj=857.72,protein_g=10,carbs_g=20,fat_g=5,fiber_g=20);data.pop('kcal')
        result=self.client.post('/api/foods/personal',json=data,headers=self.headers);self.assertEqual(result.status_code,200,result.text)
        food=result.json();self.assertAlmostEqual(food['per_100g']['kcal'],410);self.assertTrue(food['coherence']['ok'])
        code=self.client.get('/api/foods/barcode/036000291452').json();self.assertEqual(code['source'],'user_label');self.assertEqual(code['status'],'found')
        found=self.client.get('/api/foods/search?q=Etichetta&limit=50').json();self.assertTrue(any(f['food']==food['food'] for f in found))
        self.assertEqual(labels.lookup('036000291452',{})['status'],'not_found')
        self.assertEqual(self.client.post('/api/foods/personal',json=data).status_code,403)
    def test_volume_labels_density_and_coherence_flag(self):
        without=self.create(basis='per_100ml').json();self.assertIsNone(without['per_100g']['kcal']);self.assertIsNotNone(without['per_100ml'])
        with_density=self.create(basis='per_100ml',density_g_per_ml=1.25).json();self.assertAlmostEqual(with_density['per_100g']['kcal'],328)
        bad=self.create(kcal=100).json();self.assertFalse(bad['coherence']['ok']);self.assertFalse(bad['solver_eligible'])
        response=self.client.put('/api/foods/preferred',json=dict(generic=dict(source='CREA',id='000800'),product=bad['food']),headers=self.headers)
        self.assertEqual(response.status_code,400)
    def test_update_preference_deletion_and_ever_used_even_after_reset(self):
        created=self.create().json();identifier=created['food']['id'];url='/api/foods/personal/'+identifier
        changed=self.client.put(url,json=self.payload(name='Etichetta nuova'),headers=self.headers);self.assertEqual(changed.status_code,200,changed.text)
        response=self.client.put('/api/foods/preferred',json=dict(generic=dict(source='CREA',id='000800'),product=created['food']),headers=self.headers);self.assertEqual(response.status_code,200,response.text)
        clear=self.client.put('/api/foods/preferred',json=dict(generic=dict(source='CREA',id='000800'),product=None),headers=self.headers);self.assertEqual(clear.status_code,200)
        self.assertEqual(self.client.post('/api/diary/entries',json=dict(date=self.date,slot='lunch',food=created['food'],grams=50),headers=self.headers).status_code,200)
        self.client.post('/api/diary/reset',json=dict(date=self.date,slot='lunch'),headers=self.headers)
        self.assertEqual(self.client.delete(url,headers=self.headers).status_code,409)
        unused=self.create(name='Da eliminare').json()['food']['id'];self.assertEqual(self.client.delete('/api/foods/personal/'+unused,headers=self.headers).status_code,200)
    def test_local_off_has_priority_and_incomplete_status(self):
        from contextlib import contextmanager
        import sqlite3
        local=dict(name='Catalogo',nutrient_basis='per_100_g',kcal_100g=100,protein_g_100g=10,fat_g_100g=None,carbs_available_g_100g=10)
        original=sqlite3.connect
        @contextmanager
        def catalog(*args,**kwargs):
            db=original(':memory:');db.execute('CREATE TABLE products(barcode TEXT,payload TEXT)');db.execute('INSERT INTO products VALUES(?,?)',('036000291452',json.dumps(local)))
            try:yield db
            finally:db.close()
        with patch.object(labels.sqlite3,'connect',side_effect=catalog):
            response=labels.lookup('036000291452',{})
        self.assertEqual(response['source'],'OFF');self.assertEqual(response['status'],'incomplete')

for name in tuple(vars(base.DiaryTests)):
    if name.startswith('test_'):setattr(PersonalFoods,name,None)
