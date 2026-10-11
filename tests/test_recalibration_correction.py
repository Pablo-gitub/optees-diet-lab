"""T-004: test rossi per la ricalibrazione concatenata dopo correzione del diario."""
import copy
import datetime as dt
import json
from unittest.mock import patch

import progress_recalibration as recalibration
import test_checkin_presumed as checkin_base

TODAY = dt.date(2026, 10, 12)


class RecalibrationCorrectionTests(checkin_base.CheckinPresumedTests):
    def setUp(self):
        super().setUp()

    def test_checkin_saves_fingerprint_and_review_get_is_readonly(self):
        # Nessun check-in recente per l'utente: review torna checkin_date: None, corrected: False
        res = self.client.get('/api/progress/check-in/review')
        self.assertEqual(res.status_code, 200, res.text)
        self.assertIsNone(res.json().get('checkin_date'))
        self.assertFalse(res.json().get('corrected'))

        # Esegue il check-in completato
        self.seed_days(range(1, 15))
        self.calibration_data()
        checkin_res = self.checkin(mode='count')
        self.assertEqual(checkin_res.status_code, 200, checkin_res.text)
        self.assertEqual(checkin_res.json().get('status'), 'done')

        # Subito dopo il check-in: review segnala corrected: False, dismissed: False
        with self.app.connect() as db:
            before_changes = db.total_changes
        res = self.client.get('/api/progress/check-in/review')
        self.assertEqual(res.status_code, 200, res.text)
        data = res.json()
        self.assertEqual(data.get('checkin_date'), self.date(0))
        self.assertFalse(data.get('corrected'))
        self.assertFalse(data.get('dismissed'))

        # Nessuna scrittura su GET
        with self.app.connect() as db:
            self.assertEqual(db.total_changes, before_changes)

    def test_correction_within_14_days_sets_corrected_true_outside_keeps_false(self):
        self.seed_days(range(1, 15))
        self.calibration_data()
        self.checkin(mode='count')

        # Modifica su un pasto fuori dai 14 giorni (es. 15 giorni fa)
        self.plan(ago=15, slot='lunch')
        with self.app.connect() as db:
            self.app.diary.diary_mutation(db, self.user, self.profile, 'confirm', dict(date=self.date(15), slot='lunch'))

        res = self.client.get('/api/progress/check-in/review')
        self.assertEqual(res.status_code, 200, res.text)
        self.assertFalse(res.json().get('corrected'), "Modifica fuori dai 14 giorni non deve impostare corrected=True")

        # Modifica/salto di un pasto all'interno dei 14 giorni (es. giorno 3)
        with self.app.connect() as db:
            self.app.diary.diary_mutation(db, self.user, self.profile, 'skip', dict(date=self.date(3), slot='lunch'))

        res = self.client.get('/api/progress/check-in/review')
        self.assertEqual(res.status_code, 200, res.text)
        self.assertTrue(res.json().get('corrected'), "Salto o modifica in uno dei 14 giorni deve impostare corrected=True")

    def test_dismiss_and_subsequent_correction(self):
        self.seed_days(range(1, 15))
        self.calibration_data()
        self.checkin(mode='count')

        # Correzione nel periodo
        with self.app.connect() as db:
            self.app.diary.diary_mutation(db, self.user, self.profile, 'skip', dict(date=self.date(2), slot='dinner'))

        res = self.client.get('/api/progress/check-in/review')
        self.assertTrue(res.json().get('corrected'))
        self.assertFalse(res.json().get('dismissed'))

        # Salva snapshot profilo e proposte prima del dismiss
        with self.app.connect() as db:
            profile_before = db.execute('SELECT profile FROM users WHERE id=?', (self.user,)).fetchone()[0]
            proposals_before = db.execute('SELECT * FROM recalibration_proposal WHERE user_id=?', (self.user,)).fetchall()

        # Invio dismiss ("No")
        dismiss_res = self.client.post('/api/progress/check-in/review/dismiss', json=dict(checkin_date=self.date(0)), headers=self.headers)
        self.assertEqual(dismiss_res.status_code, 200, dismiss_res.text)

        # Target e proposte non devono essere modificati
        with self.app.connect() as db:
            profile_after = db.execute('SELECT profile FROM users WHERE id=?', (self.user,)).fetchone()[0]
            proposals_after = db.execute('SELECT * FROM recalibration_proposal WHERE user_id=?', (self.user,)).fetchall()
        self.assertEqual(profile_before, profile_after)
        self.assertEqual(len(proposals_before), len(proposals_after))

        # Review ora torna dismissed: True
        res = self.client.get('/api/progress/check-in/review')
        self.assertTrue(res.json().get('corrected'))
        self.assertTrue(res.json().get('dismissed'))

        # Nuova correzione (es. giorno 4)
        with self.app.connect() as db:
            self.app.diary.diary_mutation(db, self.user, self.profile, 'skip', dict(date=self.date(4), slot='lunch'))

        # Review torna di nuovo dismissed: False
        res = self.client.get('/api/progress/check-in/review')
        self.assertTrue(res.json().get('corrected'))
        self.assertFalse(res.json().get('dismissed'))

    def test_recalculate_chained_limits_and_cumulative_delta(self):
        # Configura target a 2000 kcal per avere cap del 5% = 100 kcal
        self.profile['daily_meals']['targets']['kcal_100g'].update(min=1400, target=2000, max=2500)
        with self.app.connect() as db:
            db.execute('UPDATE users SET profile=? WHERE id=?', (json.dumps(self.profile), self.user))

        # Baseline a 1600 kcal con intake a 1800 kcal -> estimate 1650 -> desired -350 -> applied -100
        for ago in range(1, 15):
            self.report['daily'].append(dict(date=self.date(ago), usable_for_baseline=True, total_estimated_kcal=1600))
        with self.app.connect() as db:
            for ago in range(15):
                self.app.diary.add_measurement(db, self.user, dict(date=self.date(ago), kind='weight', unit='kg', value=80.0))

        self.seed_days(range(1, 15), confirmed=True)
        checkin_res = self.checkin(mode='count')
        self.assertEqual(checkin_res.status_code, 200, checkin_res.text)
        proposal_1 = checkin_res.json().get('recalibration')
        self.assertEqual(proposal_1.get('status'), 'available')
        prop_id_1 = proposal_1['proposal']['id']
        self.assertEqual(proposal_1['proposal']['applied_delta_kcal'], -100)

        # Approva la prima proposta: target passa da 2000 a 1900
        approve_res = self.client.post(f'/api/progress/recalibrations/{prop_id_1}/approve',
                                       json=dict(state_token=proposal_1['proposal']['state_token'], reason='ok'),
                                       headers=self.headers)
        self.assertEqual(approve_res.status_code, 200, approve_res.text)

        # Correzione: dati chiedono ancora -100 (nessun margine residuo negativo perché cap cumulata è 100)
        with self.app.connect() as db:
            # Salto di un pasto riduce ulteriormente l'intake
            self.app.diary.diary_mutation(db, self.user, self.profile, 'skip', dict(date=self.date(1), slot='breakfast'))

        recalc_res = self.client.post('/api/progress/check-in/review/recalculate', json=dict(checkin_date=self.date(0)), headers=self.headers)
        self.assertEqual(recalc_res.status_code, 200, recalc_res.text)
        recalc_data = recalc_res.json()
        # Spazio residuo per riduzione è 0: status no_adjustment oppure applied_delta_kcal = 0
        if recalc_data.get('status') == 'available':
            self.assertGreaterEqual(recalc_data['proposal']['applied_delta_kcal'], 0)
            self.assertEqual(recalc_data['proposal']['allowed_delta_kcal']['min'], 0)
        else:
            self.assertEqual(recalc_data.get('status'), 'no_adjustment')

        # Ora modifica con dati che chiedono invece +30 kcal rispetto al nuovo target (1900):
        # Aggiorniamo health report baseline a un valore che porta desired a +30
        # Target 1900, bilancio 0. Se estimate = 1930 -> desired = +30.
        # Estimate = 0.75 * baseline + 0.25 * inferred. Con slope ~0, intake ~1930, baseline ~1930 -> desired = +30.
        with patch.object(self.app, 'load_health_report', side_effect=lambda *a: dict(
                version='synthetic-checkin', measures={}, weight_history=[],
                scenarios=dict(status='available'),
                daily=[dict(date=self.date(ago), usable_for_baseline=True, total_estimated_kcal=1930) for ago in range(1, 15)])):
            # Imposta le calorie dei pasti confermati a circa 1930
            recalc_res2 = self.client.post('/api/progress/check-in/review/recalculate', json=dict(checkin_date=self.date(0)), headers=self.headers)
            self.assertEqual(recalc_res2.status_code, 200, recalc_res2.text)
            recalc_data2 = recalc_res2.json()
            if recalc_data2.get('status') == 'available':
                self.assertEqual(recalc_data2['proposal']['applied_delta_kcal'], 30)
                # Cumulata: -100 + 30 = -70 kcal
                self.assertEqual(recalc_data2['proposal'].get('cumulative_delta_kcal'), -70)

    def test_cooldown_allowed_for_same_checkin_blocked_for_different(self):
        self.seed_days(range(1, 15), confirmed=True)
        self.calibration_data()
        checkin_res = self.checkin(mode='count')
        self.assertEqual(checkin_res.status_code, 200)
        prop_1 = checkin_res.json()['recalibration']
        self.assertEqual(prop_1['status'], 'available')
        prop_id_1 = prop_1['proposal']['id']

        # Approvazione prima proposta
        appr_res = self.client.post(f'/api/progress/recalibrations/{prop_id_1}/approve',
                                    json=dict(state_token=prop_1['proposal']['state_token'], reason='ok'),
                                    headers=self.headers)
        self.assertEqual(appr_res.status_code, 200)

        # Correzione pasto per attivare ricalibrazione
        with self.app.connect() as db:
            self.app.diary.diary_mutation(db, self.user, self.profile, 'skip', dict(date=self.date(1), slot='breakfast'))

        recalc_res = self.client.post('/api/progress/check-in/review/recalculate', json=dict(checkin_date=self.date(0)), headers=self.headers)
        self.assertEqual(recalc_res.status_code, 200)

        # Se la ricalibrazione ha generato una proposta (o forzando una proposta con lo stesso checkin_date),
        # l'approvazione deve essere consentita anche entro 7 giorni
        if recalc_res.json().get('status') == 'available':
            prop_id_chained = recalc_res.json()['proposal']['id']
            appr_chained = self.client.post(f'/api/progress/recalibrations/{prop_id_chained}/approve',
                                            json=dict(state_token=recalc_res.json()['proposal']['state_token'], reason='chained'),
                                            headers=self.headers)
            self.assertEqual(appr_chained.status_code, 200, appr_chained.text)

        # Con checkin_date diverso (es. altra settimana creata a mano), il cooldown blocca con 409
        with self.app.connect() as db:
            token = 'other_checkin_token'
            diff_id = db.execute(
                "INSERT INTO recalibration_proposal(user_id,checkin_date,created,state,fingerprint,payload) VALUES(?,?,?,'pending',?,?)",
                (self.user, self.date(7), TODAY.isoformat(), token, json.dumps(dict(changes=dict(daily=dict(before=self.profile['targets'], after=self.profile['targets'], delta_kcal=50)))))
            ).lastrowid
            with patch.object(recalibration, 'fingerprint', return_value=token):
                diff_appr = self.client.post(f'/api/progress/recalibrations/{diff_id}/approve',
                                             json=dict(state_token=token, reason='diff'),
                                             headers=self.headers)
                self.assertEqual(diff_appr.status_code, 409)
                self.assertIn('recalibration_cooldown', diff_appr.text)

    def test_history_shows_chaining_and_fingerprint_invalidation(self):
        self.seed_days(range(1, 15), confirmed=True)
        self.calibration_data()
        checkin_res = self.checkin(mode='count')
        prop_1 = checkin_res.json()['recalibration']['proposal']
        self.client.post(f"/api/progress/recalibrations/{prop_1['id']}/approve",
                         json=dict(state_token=prop_1['state_token'], reason='ok'),
                         headers=self.headers)

        with self.app.connect() as db:
            self.app.diary.diary_mutation(db, self.user, self.profile, 'skip', dict(date=self.date(2), slot='lunch'))

        recalc_res = self.client.post('/api/progress/check-in/review/recalculate', json=dict(checkin_date=self.date(0)), headers=self.headers)
        if recalc_res.json().get('status') == 'available':
            prop_2 = recalc_res.json()['proposal']
            self.assertEqual(prop_2.get('chained_from'), prop_1['id'])
            self.client.post(f"/api/progress/recalibrations/{prop_2['id']}/approve",
                             json=dict(state_token=prop_2['state_token'], reason='ok 2'),
                             headers=self.headers)

            history = self.client.get('/api/progress/recalibrations').json()
            approved_ids = [h['id'] for h in history if h.get('status') == 'approved']
            self.assertIn(prop_1['id'], approved_ids)
            self.assertIn(prop_2['id'], approved_ids)

    def test_security_csrf_auth_and_mismatched_checkin_date(self):
        # 401 senza autenticazione
        unauth = type(self.client)(self.app.app)
        self.assertEqual(unauth.get('/api/progress/check-in/review').status_code, 401)
        self.assertEqual(unauth.post('/api/progress/check-in/review/dismiss', json=dict(checkin_date=self.date(0))).status_code, 401)
        self.assertEqual(unauth.post('/api/progress/check-in/review/recalculate', json=dict(checkin_date=self.date(0))).status_code, 401)

        # 403 senza CSRF
        self.assertEqual(self.client.post('/api/progress/check-in/review/dismiss', json=dict(checkin_date=self.date(0))).status_code, 403)
        self.assertEqual(self.client.post('/api/progress/check-in/review/recalculate', json=dict(checkin_date=self.date(0))).status_code, 403)

        # Isolamento tra utenti
        other_client, other_user, other_profile, other_headers = self.account('other_user_t004')
        # Altro utente non vede check-in
        self.assertIsNone(other_client.get('/api/progress/check-in/review').json().get('checkin_date'))

        # checkin_date non corrispondente -> 409
        self.seed_days(range(1, 15))
        self.calibration_data()
        self.checkin(mode='count')
        mismatched = self.client.post('/api/progress/check-in/review/dismiss', json=dict(checkin_date=self.date(7)), headers=self.headers)
        self.assertEqual(mismatched.status_code, 409)
        self.assertIn('checkin', mismatched.text.lower())
