# T-004 · Correzione dopo il check-in: «Vuoi ricalibrare i giorni successivi?» con ricalibrazione concatenata

Autore della scheda: Claude · Data: 2026-10-11 · Tappa del piano: 2
Test rossi e backend: Codex (parte delicata: limiti e cooldown della ricalibrazione) · Interfaccia: Gemini (scheda successiva, dopo questo contratto) · Revisori: Codex, Claude

## Obiettivo

Se dopo un check-in l'utente corregge pasti dei giorni che quel check-in ha usato, l'app chiede se ricalibrare. Con «Sì» nasce una nuova proposta **concatenata**: parte dai target attuali (già cambiati dalla ricalibrazione approvata di quel check-in) e usa i dati corretti, e la variazione **complessiva** della settimana resta entro i limiti di sicurezza. Con «No» non cambia nulla: i dati corretti restano nel diario e pesano sui calcoli successivi.

## Decisioni del proprietario (11 ottobre 2026)

- Correzione dopo il check-in: si chiede se ricalibrare i giorni successivi; con «No» i dati restano solo come memoria per le settimane seguenti.
- Più ricalibrazioni nella stessa settimana sono **concatenate**: la successiva tiene conto della precedente, non riparte da zero né si somma alla cieca.

## Contesto (nomi verificati)

`scripts/progress_recalibration.py`: `SAFETY` (`max_weekly_change_kcal=100`, `max_weekly_change_fraction=.05`, `approval_cooldown_days=7`, `proposal_expiry_days=7`), `cooldown(db,user)` (blocca approvazioni entro 7 giorni da un'altra approvata), `make_proposal(...)` (14 giorni prima del check-in; `desired=estimate+balance-old_target` sui target correnti; `target_changes` limita il passo a ±min(100, 5%)), `decide(...)` (approva/rifiuta con `state_token`/`fingerprint`), tabella `recalibration_proposal` (`checkin_date`, `state`). `web/app.py`: `POST /api/progress/check-in`, `/api/progress/recalibrations*`. Pasti presunti e `as_of`: T-001, T-003.

## Contratto (backend)

1. **Riferimento del check-in.** Al check-in completato (`status:"done"`) si conserva un'impronta del diario dei 14 giorni usati (stessa base dei dati di `make_proposal`, presunti inclusi come in T-003), legata a utente e `checkin_date`. Scrittura solo dentro il check-in, mai nelle GET.
2. **Stato della correzione.** `GET /api/progress/check-in/review` → per l'ultimo check-in della settimana corrente (entro `proposal_expiry_days`): `{"checkin_date", "corrected": bool, "dismissed": bool}`; `corrected` è vero se l'impronta attuale dei 14 giorni differisce da quella salvata. Senza check-in recente: `{"checkin_date": null, "corrected": false}`. Nessuna scrittura.
3. **«No».** `POST /api/progress/check-in/review/dismiss {checkin_date}` → registra il rifiuto per l'impronta attuale; `review` torna `dismissed:true` finché non arriva una nuova correzione (impronta diversa). Nessuna modifica a target o proposte.
4. **«Sì».** `POST /api/progress/check-in/review/recalculate {checkin_date}` → nuova proposta con la pesata già salvata del check-in e i dati attuali; stessa risposta di `recalibration` nel check-in. Le proposte `pending` precedenti diventano `superseded` (come oggi).
5. **Concatenazione e limiti.** La nuova proposta parte dai target correnti. La variazione **cumulata** rispetto ai target prima della prima ricalibrazione approvata per lo stesso `checkin_date` non supera ±min(`max_weekly_change_kcal`, `max_weekly_change_fraction`·target). `allowed_delta_kcal` della proposta riflette lo spazio residuo.
6. **Cooldown.** L'approvazione di una proposta di correzione è ammessa anche entro `approval_cooldown_days` **solo** se l'unica ricalibrazione approvata nel periodo ha lo stesso `checkin_date`; la precedente resta `approved` nella cronologia e la nuova registra il collegamento (es. `chained_from`). Ogni altro caso di cooldown resta invariato.
7. Autenticazione, CSRF, isolamento fra utenti come gli altri endpoint dei progressi; `checkin_date` diverso dall'ultimo check-in recente → 409 con messaggio chiaro.

## Criteri di accettazione (test rossi di Codex)

- [ ] Check-in completato salva l'impronta; GET di `review` subito dopo → `corrected:false`; nessuna GET scrive.
- [ ] Correzione di un pasto (modifica, conferma di un presunto con contenuto diverso, salto) in uno dei 14 giorni → `corrected:true`; correzione fuori dai 14 giorni → `false`.
- [ ] `dismiss` → `dismissed:true`, target e proposte invariati; nuova correzione → di nuovo `dismissed:false`.
- [ ] `recalculate` dopo una ricalibrazione approvata di −100 (limite pieno) e dati che chiederebbero ancora −100 → nessuna ulteriore riduzione (spazio residuo 0); con dati che chiedono +30 → proposta +30, cumulata −70.
- [ ] Approvazione della proposta di correzione entro 7 giorni dalla prima approvata con lo stesso `checkin_date` → consentita; con `checkin_date` diverso → `recalibration_cooldown` come oggi.
- [ ] La cronologia mostra entrambe le approvazioni e il collegamento; i token/impronte esistenti continuano a invalidare decisioni su dati cambiati.
- [ ] 401/403/isolamento; `checkin_date` non corrispondente → 409.
- [ ] Suite completa verde.

## Interfaccia (scheda T-006, dopo il commit del backend)

Riquadro in Progressi e una riga in Oggi: «Hai corretto pasti usati nel check-in di lunedì. Vuoi ricalibrare i giorni successivi?» → **Sì** (mostra la nuova proposta con il blocco di approvazione esistente) / **No** (dismiss). Stile e accessibilità come T-002.

## Fuori perimetro

Rientro dopo uno sgarro (`meal_rebalance`, già con protezione dalla doppia compensazione); formule di stima del consumo; soglie diverse dai limiti esistenti.

## Base

```
45f1ddc2d05822c6ff9cda6d8195f0d67657e507
```

## File consentiti

```
scripts/progress_recalibration.py
scripts/progress_analysis.py
scripts/diary_service.py
web/app.py
```

## Test protetti

<!-- scritti da Codex -->
```
tests/test_recalibration_correction.py
```

## Test aggiuntivi consentiti

```
tests/test_recalibration_correction_extra.py
```

## Comando di test

```
set -a; . ./.env; set +a; PYTHONPATH=scripts:tests:. ${DIET_PYTHON:-python} -m unittest test_recalibration_correction test_progress_recalibration test_recalibration_api test_checkin_presumed test_progress_api -q
```

## Resoconto

## Revisione
