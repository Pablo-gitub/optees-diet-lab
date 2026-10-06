# Contratto API e modello dati — Oggi, Settimana, Diario, Statistiche

Stato: **approvato il 2026-10-04** (passo 2.1 di [development-plan.md](development-plan.md)). Implementazione: passo 2.2 (Codex) per diario e settimana, 3.1 per la palestra, 5.x per le statistiche complete. La generazione dei piani segue [orchestration.md](orchestration.md).

## 1. La schermata iniziale

L'app si apre su **una sola pagina che scorre**, in quest'ordine:

```text
┌──────────────────────────────────────────────────────────┐
│ OGGI · lunedì 6 ottobre · giornata di allenamento         │
│ ┌────────────── anelli ──────────────┐                    │
│ │ kcal 1.120 / 1.800  proteine 62/110 │  copertura 3/5 ✓  │
│ └─────────────────────────────────────┘                   │
│ ☕ Colazione   ✓ mangiato come previsto          173 kcal │
│ 🍎 Spuntino    ✓ mangiato · modificato           131 kcal │
│ 🍝 Pranzo      da registrare  [✓ Come previsto] [✎] [⇄]  │
│ 🍌 Spuntino    da registrare  [✓] [✎] [⇄]                │
│ 🍽 Cena        previsto                         [✎] [⇄]  │
│ 🏋 Palestra    Forza A · 50 min · 18:30   [Inizia] [Salta]│
├──────────────────────────────────────────────────────────┤
│ SETTIMANA  L ● ● ● ●  M ● ● ○ ○  M ○ ○ ○ ○ …              │
│ budget kcal  ████████░░░░  8.420 / 12.600  · 2/4 allen.   │
│ [Genera la prossima settimana]  [Ho sgarrato]             │
├──────────────────────────────────────────────────────────┤
│ STATISTICHE  peso 81,2 ↓0,4 (7 gg) · aderenza 86% ·       │
│              kcal medie 1.760 / 1.800 · allenamenti 2/4   │
│              → Progressi                                  │
└──────────────────────────────────────────────────────────┘
```

- **Oggi** è la parte principale: pasti e attività del giorno, con le azioni del diario. Su desktop i pasti stanno a sinistra, anelli e palestra a destra; su telefono è tutto in una colonna.
- Le azioni per pasto sono: **✓ Come previsto** (un tocco), **✎ Modifica** (togli, aggiungi, cambia grammi) e **⇄ Alternative**. Le alternative sono soluzioni ottime ammesse per quel pasto, tenendo fermi gli altri pasti del giorno (§5.4).
- **Settimana**: una striscia di 7 giorni. Toccare un giorno carica quel giorno nella sezione Oggi, senza cambiare pagina. Sotto ci sono il budget settimanale e le azioni settimanali.
- **Statistiche**: 3–4 riquadri riassuntivi. I grafici completi stanno nella pagina Progressi.
- Navigazione: **Oggi** (questa pagina) · **Piano** (generazione e confronto alternative settimanali) · **Libreria** (ricette ed esercizi) · **Progressi** (statistiche, peso, Salute) · **Profilo**.

## 2. Principi

1. **Previsto ≠ consumato.** Il piano (pianificato) e il diario (consumato) sono tabelle diverse. Generare o applicare un piano **non modifica mai** il diario.
2. **Dato mancante ≠ zero.** Un pasto non registrato è `unknown`, non 0 kcal. I totali del giorno riportano sempre la `coverage`.
3. **I calcoli li fa il server.** Nutrienti, totali e aderenza sono calcolati dal backend, con fonti; la UI li mostra e basta.
4. **Grammi interi.** Le quantità salvate sono intere (g) o in unità intere per i prodotti confezionati.
5. **Giorni nel fuso Europe/Rome.** Le date sono `YYYY-MM-DD` locali; i timestamp sono ISO 8601 con offset.
6. **Sicurezza come oggi.** Cookie di sessione, header `X-CSRF-Token` sulle mutazioni, isolamento per utente, errori senza percorsi o dettagli interni.
7. **Operazioni lunghe come job.** La generazione dei piani risponde `202 {job_id}`; lo stato si legge con `GET /api/jobs/{id}`.

## 3. Modello dati (SQLite, per utente)

### Riferimento a un alimento — `FoodRef`

```json
{"source": "CREA", "id": "000800"}
```

`source` ∈ `CREA` | `OFF` (Open Food Facts) | `user_label` (etichette del profilo) | `recipe` (ricetta del solver, porzione calcolata).

### Tabelle

| Tabella | Campi principali | Note |
|---|---|---|
| `week_plan` | id, user_id, week_start, mode, status (`draft`/`active`/`closed`), plan_set_run_id, created | una settimana attiva per utente e data |
| `planned_meal` | id, week_plan_id, date, slot, items (JSON di `{food, grams, units}`), role, status, locked | `slot` ∈ breakfast, morning_snack, lunch, afternoon_snack, dinner |
| `diary_entry` | id, user_id, date, slot, food (`FoodRef`), grams, units, origin, planned_meal_id, created, updated | `origin` ∈ `planned` (confermato dal piano), `added`, `replacement` |
| `meal_log` | user_id, date, slot, state, updated | stato esplicito del pasto (§3.1); chiave (user, date, slot) |
| `planned_session` | id, week_plan_id, date, session_id, minutes, start_time, status | `session_id` dal catalogo palestra |
| `workout_log` | id, user_id, date, planned_session_id, session_id, started, ended, rpe, notes | sessione eseguita |
| `set_log` | id, workout_log_id, exercise_id, set_no, reps, kg, seconds, rir | una riga per serie |
| `measurement` | id, user_id, date, kind, value, unit, source | `kind` ∈ weight, waist, …; `source` ∈ manual, apple_health |
| `job` | id, user_id, kind, state, progress, result_ref, error, created | stato dei calcoli lunghi |

### 3.1 Stati

| Oggetto | Stati | Transizioni |
|---|---|---|
| Pasto nel diario (`meal_log.state`) | `unknown` → `as_planned` / `modified` / `skipped` / `unplanned` | `as_planned` diventa `modified` se si toglie, si aggiunge o si cambia una quantità |
| Pasto pianificato (`planned_meal.status`) | `proposed` → `chosen` → `done` / `skipped` | `done`/`skipped` derivano dal diario, non si impostano a mano |
| Sessione (`planned_session.status`) | `proposed` → `chosen` → `in_progress` → `done` / `skipped` | `in_progress` all'avvio del `workout_log` |

`unplanned` indica un pasto registrato in uno slot senza piano (es. uno spuntino extra).

## 4. Lettura

### 4.1 `GET /api/day?date=2026-10-06` — sezione Oggi

```json
{
  "date": "2026-10-06",
  "day_type": "training",
  "mode": "training",
  "week_plan_id": 12,
  "targets": {"kcal": {"min": 1600, "target": 1800, "max": 2000}, "protein_g": {"…": "…"}},
  "totals": {
    "planned": {"kcal": 1790, "protein_g": 108, "carbs_available_g": 205, "fat_g": 58},
    "eaten":   {"kcal": 1120, "protein_g": 62,  "carbs_available_g": 140, "fat_g": 31},
    "coverage": {"logged_slots": 3, "planned_slots": 5}
  },
  "meals": [
    {
      "slot": "lunch",
      "state": "unknown",
      "planned": {"planned_meal_id": 301, "role": "best", "items": [{"food": {"source": "CREA", "id": "000800"}, "name": "Pasta di semola", "grams": 80, "kcal": 284}], "kcal": 531},
      "eaten": null,
      "actions": ["confirm", "edit", "alternatives", "skip"]
    }
  ],
  "workout": {"planned_session_id": 55, "session_id": "strength-a", "title": "Forza A", "minutes": 50, "start_time": "18:30", "status": "chosen", "media": {"thumbnail": "/static/media/exercises/push-up/0.jpg"}},
  "warnings": []
}
```

- `eaten` è `null` se il pasto non è registrato; se è registrato contiene `items` dal diario e i relativi totali.
- `actions` dice alla UI quali pulsanti mostrare: per esempio niente `alternatives` su un pasto già consumato.

#### B11 — Riferimento valutabile e voto in DayView

Campi aggiuntivi, presenti anche nelle risposte aggiornate delle mutazioni del diario:

```json
{"plan_id":42,"rating":4,"plan_evaluation":{"status":"available","reason":null,"plans":[{"plan_id":42,"rating":4,"rated_at":1791219600,"rating_scope":"plan","slots":["lunch","dinner"],"workout_ids":[],"scope":"lunch_and_dinner_only","feedback_endpoint":"/api/plans/42/feedback","feedback_available":true,"reason":null,"applied_at":1791200000}]}}
```

`plan_id` è l'id di `plans`, distinto da `week_plan_id` e `planned_meal_id`. Proviene dalla traccia di applicazione v2 del proprietario, verificando che i pasti/sessioni corrispondano ancora. `rating` è null se manca un voto, mai zero. Con più piani applicati ai componenti della giornata, `plan_evaluation.status = "multiple"`, `plans` contiene i riferimenti e gli alias superiori `plan_id`/`rating` sono null: la UI deve indicare pasti/allenamenti coperti, senza attribuire un voto arbitrario all'intera giornata.

Nessuna applicazione verificabile o piano successivamente sostituito: `status = "unavailable"`, `reason` esplicito, `plans = []`, alias null. Per giorni futuri il riferimento rimane visibile ma `feedback_available = false` e `reason` lo spiega. Una semplice generazione/selezione non crea un riferimento applicato. Leggere DayView non modifica voti, prove o ricompense.

Per «Com'è andata la giornata?» usare `POST feedback_endpoint` con `{ "rating": 1..5, "tried": true }` e CSRF. Il voto è **del piano**, condiviso tra i giorni di una sua applicazione settimanale (`rating_scope`), non una nuova valutazione autonoma per giorno: aggiornarlo sostituisce quello esistente. Il backend continua ad apprendere solo dai componenti effettivamente provati con dati sufficienti; salvare un voto non promette un aggiornamento del bandit (vedere `learning` nella risposta).

Dal B15, un rientro applicato conserva lo stesso riferimento valutabile: `plan_evaluation.plans[].rebalance_count` indica il numero di revisioni e `last_rebalanced_at` la più recente (0/null senza rientri). `applied_at`, piano originale e voto restano conservati. Il backend aggiorna il bilancio atteso del bandit; serve una nuova conferma dopo aver provato la versione ribilanciata per renderla eleggibile all'apprendimento. [Dettagli del rientro](backend-handoff-rebalance.md).

### 4.2 `GET /api/week?start=2026-10-06` — striscia Settimana

```json
{
  "week_start": "2026-10-06",
  "plan_status": "active",
  "days": [
    {"date": "2026-10-06", "day_type": "training", "meals": [{"slot": "breakfast", "state": "as_planned"}, {"slot": "lunch", "state": "unknown"}], "workout": "chosen", "kcal_planned": 1790, "kcal_eaten": 1120, "coverage": 0.6}
  ],
  "budget": {"kcal_target": 12600, "kcal_planned": 12480, "kcal_eaten": 8420, "kcal_remaining_planned": 4060, "complete_days": 4},
  "workouts": {"planned": 4, "done": 2}
}
```

### 4.3 `GET /api/stats/summary` — riquadri Statistiche

Ogni riquadro ha `status`: `available` | `insufficient_data` (con `reason`). Niente valori inventati.

```json
{
  "weight": {"status": "available", "value": 81.2, "unit": "kg", "trend_7d": -0.4, "points": [[ "2026-09-29", 81.6 ]], "source": "apple_health"},
  "adherence_week": {"status": "available", "diet": 0.86, "training": 0.5},
  "kcal_average": {"status": "available", "eaten_avg": 1760, "target": 1800, "days": 6},
  "workouts": {"status": "available", "done": 2, "planned": 4}
}
```

- Dal passo 5.1 il trend usa Kalman scalare sulle mediane giornaliere (progress-v2); EMA con emivita 7 giorni separata, conservando le pesate grezze. Parametri, copertura, serie attesa e check-in/decisioni sono definiti nel [contratto Progressi T10](backend-handoff-progress.md). Il precedente riepilogo provvisorio usava una media semplice dichiarata.
- L'aderenza dieta è la quota di pasti pianificati registrati come `as_planned` o con scostamento kcal ≤ 10%, sui soli giorni con copertura completa.

### 4.4 `GET /api/foods/search?q=ricotta&limit=20`

```json
[{"food": {"source": "OFF", "id": "8000300…"}, "name": "Ricotta", "brand": "Galbani", "source_label": "marca", "per_100g": {"kcal": 138, "protein_g": 8.8, "carbs_available_g": 3.5, "fat_g": 10}, "unit_g": null}]
```

Ordine: etichette del profilo, prodotti già usati, marca, CREA. Ricerca accent-insensitive in italiano.

## 5. Scrittura

Tutte richiedono `X-CSRF-Token`. Rispondono con la vista aggiornata del giorno (`DayView`, come §4.1), così la UI si aggiorna con una sola richiesta.

### 5.1 Diario

| Endpoint | Corpo | Effetto |
|---|---|---|
| `POST /api/diary/confirm` | `{date, slot}` | copia gli item pianificati nel diario con `origin: planned`; stato `as_planned`. Idempotente |
| `POST /api/diary/entries` | `{date, slot, food, grams?, units?}` | aggiunge un alimento (`origin: added`); stato `modified` o `unplanned` |
| `PATCH /api/diary/entries/{id}` | `{grams?, units?}` | cambia la quantità; stato `modified` |
| `DELETE /api/diary/entries/{id}` | — | toglie un alimento; stato `modified`. Cancellazione definitiva della riga: è un dato dell'utente, non un archivio |
| `POST /api/diary/skip` | `{date, slot}` | stato `skipped`, nessuna riga di diario |
| `POST /api/diary/reset` | `{date, slot}` | rimuove le righe dello slot; stato `unknown` |

Validazioni: date non oltre domani, grammi 1–3000, unità intere 1–20, `food` esistente.

### 5.2 Misure

`POST /api/measurements {date, kind, value, unit}`: inserimento manuale (es. pesata del lunedì). Le misure Salute restano importate a parte e vengono unite in lettura.

### 5.3 Piano della settimana

| Endpoint | Corpo | Effetto |
|---|---|---|
| `POST /api/plans/week` | `{week_start, mode, locked: [...]}` | job → `PlanSet` (orchestration v2) |
| `GET /api/jobs/{id}` | — | `{state: queued/running/done/failed, progress, result: {plan_set_id}}` |
| `GET /api/plan-sets/{id}` | — | `PlanSet` come in orchestration.md §5 |
| `POST /api/plan-sets/{id}/apply` | `{plan_id, scope: "week"\|"day"\|"meal", date?, slot?}` | scrive `planned_meal`/`planned_session` |

**Regola di `apply`.** Sostituisce solo slot **senza diario e non bloccati**. Gli slot già registrati restano invariati e vengono elencati in `skipped_slots` nella risposta.

### 5.4 Alternative per un pasto — «⇄»

`POST /api/plans/meal-alternatives {date, slot}` → job → `PlanSet` con orizzonte un solo pasto.

- Gli altri pasti del giorno sono **bloccati**: il consumato se registrato, altrimenti il pianificato.
- Il budget del pasto è quello che resta del giorno, entro i limiti del pasto.
- La catena è la stessa (diversità, ruoli, diff rispetto al pasto attuale).
- La UI mostra 2–4 card compatte; «Scegli» chiama `apply` con `scope: "meal"`.

### 5.5 Palestra (passo 3.1)

| Endpoint | Corpo | Effetto |
|---|---|---|
| `POST /api/workouts/start` | `{planned_session_id?, session_id, date}` | crea `workout_log`; sessione `in_progress` |
| `POST /api/workouts/{log_id}/sets` | `{exercise_id, set_no, reps?, kg?, seconds?, rir?}` | registra una serie |
| `POST /api/workouts/{log_id}/finish` | `{rpe?, notes?}` | chiude; sessione `done` |
| `POST /api/workouts/skip` | `{planned_session_id}` | sessione `skipped` |

## 6. Errori

```json
{"detail": "Messaggio leggibile in italiano", "code": "slot_already_logged"}
```

Codici previsti: `invalid_input`, `not_found`, `slot_already_logged`, `slot_locked`, `job_running`, `infeasible`, `targets_inconsistent`. Stati HTTP: 400, 401, 403, 404, 409, 422 come oggi.

## 7. Cosa entra in quale passo

| Passo | Contenuto |
|---|---|
| 2.2 (Codex) | tabelle §3 tranne palestra; §4.1, §4.2, §4.4; §5.1, §5.2; §5.3 con piano della settimana dieta |
| 2.3 (Codex) | orchestrazione settimanale dietro `POST /api/plans/week`; §5.4 |
| 2.4 (Claude) | schermata §1 con Oggi, Settimana e i riquadri disponibili; pagina Piano; navigazione nuova |
| 3.1 (Codex) | tabelle palestra, §5.5, `workout` in §4.1 |
| 5.1 (Codex) | §4.3 completo con trend e aderenza definitivi |

Fino al 5.1, `GET /api/stats/summary` può restituire solo peso (da Salute) e allenamenti, con gli altri riquadri `insufficient_data`.

## 8. Test richiesti per il 2.2

1. Confermare un pasto copia esattamente gli item pianificati; ripeterlo non duplica.
2. Togliere, aggiungere o cambiare grammi porta lo stato a `modified`; `reset` torna a `unknown`.
3. Totali del giorno: `eaten` somma solo il diario; `coverage` conta gli slot registrati; slot non registrati non valgono zero.
4. `apply` non tocca slot con diario o bloccati e li elenca in `skipped_slots`.
5. Isolamento: un utente non legge né modifica diario, piani o misure di un altro.
6. CSRF obbligatorio su tutte le mutazioni.
7. Date oltre domani, grammi fuori intervallo e `food` inesistenti sono rifiutati con `invalid_input`.


## Fase 8.1 — Obiettivi personali e proposta di bilancio

GET `/api/goals` e ciascun PUT `/api/goals/body|activity|training|strength-anchors` restituiscono la stessa vista completa (blocchi indipendenti; `{}` e `[]` consentono di saltare). Esempio sintetico:

```json
{"body":{"target_weight_kg":75,"pace":"moderate","circumferences":["waist","hip"]},"activity":{"gym":"maybe","preferred_stores":["Conad","Coop"]},"training_priorities":{"strength":3,"health":2},"strength_anchors":[{"exercise_key":"dumbbell-deadlift","heavy":{"kg":20,"reps":3,"date":"2026-10-05"}}],"missing":[],"warnings":[],"activity_defaults":{"max_session_minutes":90,"max_sessions_per_day":1,"min_gap_hours":4}}
```

`missing` contiene solo domande realmente senza risposta, per esempio `{"field":"body.target_weight_kg","prompt":"Senza peso obiettivo o obiettivo di massa grassa il bilancio resta quello scelto da te."}`. PUT training riceve `{"priorities":{"strength":3}}`; PUT strength-anchors riceve `{"anchors":[...]}`. Valori e limiti: [specifica §1](phase8-spec.md). Al massimo tre priorità 3; conflitti forza/resistenza sono warning. Gli id attività si validano contro il catalogo locale: elenchi vuoti consentiti; se il catalogo manca, id non verificabili rifiutati con `activity_catalog_pending`. Il catalogo revisionato arrivato durante il lavoro rende verificabili gli id, ma la pianificazione delle attività 8.3 resta un passo separato. `gym:no` impedisce richieste con sessioni palestra; resta disponibile la settimana dieta. `preferred_stores` è una lista ordinata di nomi, non una promessa di assortimento.

`PUT /api/profile` conserva `goals` se omesso; se presente sostituisce il campo previa validazione. Carichi manuali `starting_loads_kg` invariati. GET `/api/workouts/config` espone in `settings.strength_anchors` le serie del profilo; sono dati di partenza, senza curva o carichi dedotti (8.4). Date serie non future, heavy 2–6 ripetizioni, light 10–15; almeno una serie. Misure `hip`, `chest`, `arm`, `thigh` via POST `/api/measurements`, unità cm, 10–300; la risposta è DayView con `measurements`, per esempio `{"measurements":[{"date":"2026-10-05","kind":"hip","value":98,"unit":"cm","source":"manual"}]}` oltre ai campi del giorno.

POST `/api/goals/energy-proposal`, corpo `{}`, CSRF. Esempio di risposta:

```json
{"status":"available","proposal":{"id":7,"state_token":"hash-opaco","current_kcal":null,"proposed_kcal":-450,"requested_kcal":-450,"pace_pct_per_week":0.5,"effective_pace_pct_per_week":0.5,"expected_date":"2027-01-10","reasoning":["Bilancio da peso filtrato e ritmo, arrotondato a 50 kcal; i target nutrizionali non cambiano in questo passo."],"uncertainty":["7700 kcal/kg è un’approssimazione; la ricalibrazione del lunedì resta il correttore.","Soglie provvisorie da verificare in 8.2."],"limits_applied":["absolute_balance_1000","weekly_cooldown_7_days"],"weight":{"value_kg":82,"date":"2026-10-05","filter":"progress-v2 scalar Kalman","variance_kg2":0.03},"target_weight_kg":75}}
```

Numeri illustrativi. Almeno due giorni di peso, andamento recente filtrato Kalman; mai l'ultima pesata grezza. Senza peso obiettivo si può suggerire il peso dalla massa magra: almeno due giorni di massa grassa, EMA delle mediane giornaliere alpha 0,5 esplicitamente euristica. Nessun peso suggerito viene salvato automaticamente. `current_kcal:null` indica nessun bilancio precedente: non uno zero inventato. Se il bilancio era già esplicito, la variazione rispetta 100 kcal o 5% del target calorico giornaliero, arrotondata verso un passo sicuro di 50; la prima impostazione resta entro ±1000. Data attesa usa il bilancio proposto dopo i limiti e può essere null se la variazione graduale ha ancora segno opposto all'obiettivo.

Indisponibilità: `{"status":"insufficient_data","reason":"Servono almeno due giornate di peso per un andamento filtrato recente."}`. Nessuna proposta né modifica del profilo in questo caso. I minimi dei target nutrizionali non vengono cambiati: il passo 8.5 proporrà separatamente i target del giorno.

POST `/api/goals/energy-proposal/7/approve|reject`, corpo `{"state_token":"hash-opaco"}`, CSRF, proprietà, transazione atomica e monouso. Risposte:

```json
{"id":7,"status":"approved","balance_changed":true}
```
```json
{"id":7,"status":"rejected","balance_changed":false}
```

409 `goals_state_changed` su dati/profilo/piano/misure/Salute cambiati; 409 su proposta chiusa, scaduta (7 giorni) o cooldown condiviso con ricalibrazione (7 giorni). Rifiuto registrato, nessun target modificato. Un'anteprima più recente sostituisce quella pendente. 404 per id di altro utente; 400 per dati non validi; 403 senza CSRF.

### 8.10 — catalogo locale e prodotti personali

Nessuna richiesta di rete. GET `/api/foods/barcode/{code}` valida GTIN-8/12/13/14 (stringa, zeri iniziali conservati, cifra di controllo) e cerca prima OFF locale, poi le etichette dell'utente. Risposte:

```json
{"status":"found","source":"OFF","food":{"food":{"source":"OFF","id":"8076800195057"},"name":"Pasta","brand":"Barilla","source_label":"Open Food Facts","per_100g":{"kcal":359,"protein_g":12,"fat_g":2,"carbs_available_g":71},"unit_g":null,"composition_provenance":null},"label":{"nutrient_basis":"per_100_g"},"serving_g":null,"package_g":500}
```
```json
{"status":"incomplete","source":"user_label","food":{"food":{"source":"user_label","id":"label_uuid"},"name":"Bevanda","brand":null,"per_100g":{"kcal":null,"protein_g":null,"fat_g":null,"carbs_available_g":null}},"label":{"basis":"per_100ml"},"serving_g":null,"package_g":null,"coherence":{"ok":true},"per_100ml":{"kcal":40,"protein_g":0,"fat_g":0,"carbs_available_g":10}}
```
```json
{"status":"not_found","source":null}
```

POST `/api/foods/personal` crea, PUT `/api/foods/personal/{id}` sostituisce l'etichetta dello stesso prodotto. Input sintetico:

```json
{"name":"Barretta","brand":"Marca","barcode":"96385074","basis":"per_serving","serving_g":40,"kj":686.176,"protein_g":8,"carbs_g":20,"fat_g":4,"fiber_g":8,"package_g":40}
```

Basi ammesse: `per_100g`, `per_100ml`, `per_serving`; kcal oppure kJ (÷4,184), proteine/carboidrati/grassi obbligatori, fibre/zuccheri/sale facoltativi. Per porzione richiede `serving_g`; per ml la conversione richiede `density_g_per_ml`. Senza densità i valori per ml restano disponibili e quelli per 100 g sono null: prodotto escluso dal solver. Conversione riusa `daily_meals.products()`. Risposta POST/PUT:

```json
{"food":{"source":"user_label","id":"label_uuid"},"per_100g":{"kcal":410,"protein_g":20,"fat_g":10,"carbs_available_g":50},"per_100ml":null,"coherence":{"ok":true,"expected_kcal":164,"declared_kcal":164,"deviation_pct":0,"basis":"per_serving"},"solver_eligible":true,"label":{"name":"Barretta","basis":"per_serving","serving_g":40,"kj":686.176,"protein_g":8,"carbs_g":20,"fat_g":4,"fiber_g":8},"serving_g":40,"package_g":40}
```

Coerenza: 4P+4C+9G+2fibre, scarto relativo al valore calcolato >15% segnala `coherence.ok:false` e `solver_eligible:false`. Il prodotto viene conservato per correggere l'etichetta, ma non può essere preferito nel solver. Ricerca `/api/foods/search` include i prodotti personali solo del proprietario. Codice duplicato fra etichette dello stesso utente: 409 `duplicate_barcode`.

DELETE `/api/foods/personal/{id}`:

```json
{"status":"deleted","food":{"source":"user_label","id":"label_uuid"}}
```

409 `food_used` se mai consumato nel diario, anche dopo reset; 409 `food_planned` se ancora referenziato da un piano. 404 per id assente o altrui. La provenienza storica non viene cancellata.

PUT `/api/foods/preferred`, input `{"generic":{"source":"CREA","id":"000800"},"product":{"source":"user_label","id":"label_uuid"}}`, salva un prodotto completo e coerente; `product:null` rimuove la preferenza. Risposta:

```json
{"generic":{"source":"CREA","id":"000800"},"product":{"source":"user_label","id":"label_uuid"},"preferred_products":{"000800":{"source":"user_label","id":"label_uuid"}}}
```

Questa API conserva l'associazione; la sua applicazione ai componenti generici e alla spesa appartiene a 8.11. Tutte le scritture richiedono CSRF e sono atomiche; 400 per GTIN/valori/basi non validi, `incomplete_product` o `incoherent_product` su preferenza non utilizzabile, 403 senza CSRF.

### 8.9 — alternative con sovrapposizione in grammi

Gli endpoint esistenti di generazione giornata, settimana e singolo pasto mantengono le risposte precedenti e aggiungono questi campi. Per il pasto si confronta solo lo slot richiesto; per la settimana si sommano gli ingredienti di tutti i giorni, anche i pasti fissati. Esempio di pool (numeri illustrativi):

```json
{"status":"ok","plans":[{"id":41,"role":"best","rank":1,"overlap_pct":27.5,"constraint_report":{"verified":true,"all_respected":true},"explanation":{"headline":"Il più vicino ai tuoi obiettivi","reasons":["Questa alternativa cambia almeno il 72.5% degli ingredienti in peso; soglia del 10% non raggiunta entro i vincoli e il budget."],"tradeoffs":[]}}],"pool":{"candidates":3,"front":2,"overlap_target":10,"overlap_achieved":27.5,"overlap_scope":"week","overlap_metric":"maximum_both_directed_gram_ratios","canonical_version":"ingredient-overlap-v1","overlap_searches":[{"threshold":0.275,"lower_bound":0.268,"precision_pct":1,"certified":true,"target_feasible":false}],"min_distance":0,"structural":false,"diversity_relaxed":[],"near_optimal_limit":0.04,"near_optimal_enforced":false,"nutritional_constraints_relaxed":false,"within_week_variety":{"scope":"principal_food_id_per_meal","repeat_threshold":2,"excess_weight":0.002,"hard_max":3}},"warnings":[{"code":"overlap_target_unavailable","message":"Sovrapposizione massima minimizzata nei vincoli nutrizionali; certificazione e intervallo nel pool.","overlap_achieved":27.5}]}
```

`plans` nell'esempio è abbreviato a un elemento; ogni piano reale conserva selezioni/prodotti/grammi/nutrienti/diff. `overlap_pct` è il massimo verso tutte le altre alternative mostrate. Le percentuali sono 0–100; le soglie/intervalli di `overlap_searches` sono 0–1. `overlap_achieved:null` quando manca una coppia confrontabile. `certified:false` indica un limite di calcolo, non la prova che la dieta impedisca una diversità maggiore. La UI deve usare questa distinzione nelle spiegazioni, mostrando la sovrapposizione effettiva.

Tre alternative fattibili sono preferite anche se la terza è fuori dal fronte Pareto campionato: viene dichiarato in `explanation.tradeoffs`. Il valore storico `near_optimal_limit` resta il riferimento epsilon, ma non è un vincolo rigido per la ricerca di diversità (`near_optimal_enforced:false`). Tutti i minimi/massimi nutrizionali, porzioni, abbinamenti, blocchi e frequenze restano rigidi. `min_distance`/`diversity_relaxed` sono compatibilità, non la nuova garanzia. I solve diagnostici o interni con `k:1|2` mantengono il conteggio richiesto; i percorsi normali richiedono almeno tre, se fattibili entro il budget. Meno di tre: `limited_alternatives`, con causa esplicita; budget senza certificazione: `status:partial`.

POST `/api/plan-sets/{id}/alternatives`, CSRF, `{}` oppure `{"time_limit":30}` (1–120 secondi). Riusa lo stesso pool e aggiunge vincoli verso **tutti** i piani già mostrati. Nessuna applicazione automatica al diario. Supporta pool dieta di giornata, settimana e pasto; i pool congiunti/palestra richiedono la loro generazione specifica. Profilo cambiato dalla generazione richiede un nuovo pool; 409 se durante il calcolo cambiano profilo, diario, piano o pool. L'estensione salva atomicamente solo alternative con sovrapposizione ≤50% verso tutte le altre, dopo aver cercato il 10% e minimizzato il massimo quando non fattibile.

```json
{"status":"extended","plan_set_id":12,"added_plan_ids":[44,45],"plan_set":{"run_id":"12","status":"ok","plans":[{"id":41,"rank":1,"overlap_pct":27.5},{"id":44,"rank":2,"overlap_pct":27.5},{"id":45,"rank":3,"overlap_pct":22}],"pool":{"overlap_target":10,"overlap_achieved":27.5,"extensions":[{"overlap_searches":[{"threshold":0.275,"lower_bound":0.268,"certified":true}]}]}}}
```

`plan_set` e `plans` qui abbreviati; la risposta effettiva contiene i piani completi come GET `/api/plan-sets/{id}`. Gli id restano applicabili con l'endpoint di apply già esistente. Se non si trova altro, risposta 200 senza scritture:

```json
{"status":"no_more_alternatives","plan_set_id":12,"added_plan_ids":[],"reason":"Non ci sono altre alternative abbastanza diverse: serve almeno il 50% di ingredienti diversi.","pool":{"overlap_target":10,"overlap_achieved":64.8,"overlap_searches":[{"threshold":0.65,"lower_bound":0.643,"precision_pct":1,"certified":true,"target_feasible":false}]}}
```

Se il budget impedisce la conclusione, il motivo precisa che non è stata trovata un'alternativa entro il tempo disponibile e `certified:false`. 403 senza CSRF, 404 per pool assente/altrui, 400 `unsupported_pool` o `empty_pool`, 409 `plan_set_state_changed`, 422 `overlap_not_verified` per un risultato non conforme. Identità canoniche, categorie escluse, limite del minimax e misure aggregate: [audit 8.9](phase8-diversity-audit.md).

### B16 — fattibilità della varietà e calcolo interrotto

Il pool della settimana libera demo può dichiarare un limite analitico, distinto
dalla certificazione del solver. La modalità libera attuale usa 3 amidi, 3 verdure,
7 fonti proteiche e **2 frutti**, non l'intero database. Con un frutto da almeno
100 g in ognuno dei 14 pasti, fra tre alternative una coppia ha supporti di frutta
inclusi uno nell'altro: almeno 1.400 g comuni su al massimo 12.880 g totali, quindi
**10,8696% minimo**. Questo basta a dimostrare che tre settimane sotto il 10%
sono impossibili anche con identità canoniche più strette e senza limite alle
ripetizioni. Il limite non viene esposto con porzioni personalizzate, pasti
bloccati o colazione/spuntini attivi. Non certifica la migliore sovrapposizione.

```json
{"pool":{"overlap_target":10,"overlap_feasibility":{"status":"impossible_for_three","minimum_alternatives":3,"lower_bound_pct":10.8696,"shared_grams_min":1400,"total_grams_max":12880,"candidate_counts":{"starch":3,"vegetables":3,"protein":7,"fruit":2},"reason":"Solo due frutti candidati, obbligatori in 14 pasti: tre alternative hanno almeno il 10,87% di ingredienti comuni. Il catalogo completo non è ancora usato dalla modalità libera."}}}
```

Il messaggio delle alternative usa «ingredienti diversi sotto il 90%». Un limite
di tempo, anche prima del primo tentativo di estensione, **non** prova che non
esistano alternative; `pool.overlap_searches` contiene sempre una voce non
certificata quando questa è la causa dell'arresto:

```json
{"status":"no_more_alternatives","plans":[],"pool":{"overlap_target":10,"overlap_searches":[{"certified":false,"reason":"Tempo di calcolo esaurito."}]}}
```

### B17 — catalogo attività locale

`GET /api/activities` richiede autenticazione (401 senza sessione). Restituisce
il catalogo revisionato in `config/activity-catalog.json`, senza richieste di
rete. Tutte le voci hanno `id`, `name_it`, `met`, `duration_minutes`, `goals`,
codice e fonte Compendium e tipi HealthKit. Il catalogo non è una configurazione
personale e non impone alcuna attività.

```json
{"version":"1.0","source":"2024 Adult Compendium of Physical Activities","checked_on":"2026-10-06","activities":[{"id":"walking_slow","name_it":"Camminata lenta","met":2.8,"duration_minutes":{"min":15,"max":90,"step":5},"goals":[{"goal_id":"health","zone":"light"}],"healthkit_types":["HKWorkoutActivityTypeWalking"],"compendium_code":"17152","compendium_url":"https://pacompendium.com/walking","checked_on":"2026-10-06"}]}
```

### 8.3 — attività nella settimana congiunta e nel diario

`POST /api/plans/joint-week` e `POST /api/plans/workout-week` accettano
`workout.activities` (lista facoltativa di ID del catalogo). Altrimenti usano
le attività gradite coerenti con le priorità; senza priorità non aggiungono
attività automaticamente. Le attività escluse sono rifiutate (400). Con
`goals.activity.gym: "no"` entrano solo attività, e un minimo esplicito di sedute
di forza maggiore di zero è incoerente (400). I limiti settimanali restano hard.
La durata è una variabile intera di passi del catalogo, collegata al selettore
binario; la verifica indipendente controlla anche questa durata.

```json
{"week_start":"2026-10-05","workout":{"activities":["walking_brisk"],"days":{"2026-10-05":30,"2026-10-06":30,"2026-10-07":30,"2026-10-08":30,"2026-10-09":30,"2026-10-10":30,"2026-10-11":30},"sessions_min":0,"sessions_max":7,"strength_sessions_min":0,"strength_sessions_max":0,"cardio_minutes_min":0,"weekly_minutes_max":150}}
```

I normali `day_targets` completi restano richiesti nel percorso congiunto fino
all'approvazione della proposta 8.5. Il piano contiene le attività in
`workout_sessions`, quindi le applica atomicamente insieme ai pasti:

```json
{"workout_sessions":[{"date":"2026-10-06","session_id":"activity:walking_brisk","minutes":30,"duration_seconds":1800,"start_time":null,"session":{"kind":"activity","activity_id":"walking_brisk","additional_activity":true,"energy_estimate":{"status":"available","source":"compendium_met_net","net":true,"weight_kg":80,"met":4.8,"energy_kcal":{"low":106.4,"central":152,"high":197.6},"uncertainty":"Scenari ±30%, euristica in attesa della matrice 8.2; non intervallo di confidenza."}}}]}
```

La fonte preferita è `apple_health_activity_quantiles` con almeno 3 osservazioni
recenti (90 giorni). Senza modello personale: `(MET-1) × peso filtrato × ore`,
scenari ±30% euristici. Senza peso recente la sessione può essere pianificata,
ma `energy_estimate` è `{"status":"unavailable","reason":"Manca un peso filtrato recente per stimare l’energia netta dell’attività."}`:
nessun zero inventato. La base Salute ha già sottratto gli allenamenti osservati;
contiene i passi abituali. Si aggiunge una sola volta l'attività **aggiuntiva**
registrata, mai una quota di passi ordinari.

Con priorità `health`, il MILP premia la copertura di 150 minuti moderati
equivalenti e due giorni di forza, come nelle [raccomandazioni OMS](https://www.who.int/europe/news-room/fact-sheets/item/physical-activity)
(verificate 2026-10-06). Sono obiettivi soft, non nuovi obblighi; con `gym:no`
la parte forza può restare incompleta. `health_progress` riporta il raggiunto e
`explanation.tradeoffs` spiega la copertura parziale nei limiti dell'utente.

`DayView.workouts[]` aggiunge `kind`, `activity_id`, `energy_estimate`.
`POST /api/activities/confirm` registra l'attività fatta in un'unica transazione,
richiede CSRF, è idempotente se già fatta e verifica proprietà e stato (404/409).
L'orario è una dichiarazione dell'utente, con durata pianificata, non una misura
Salute; si conserva `timing_provenance: user_confirmation_assumed_planned_duration`.
Il pulsante «saltata» riusa l'endpoint palestra esistente.

```json
{"planned_session_id":42}
```

Risposta: `DayView` con la voce aggiornata:

```json
{"date":"2026-10-06","workouts":[{"kind":"activity","activity_id":"walking_brisk","planned_session_id":42,"session_id":"activity:walking_brisk","status":"done","minutes":30,"workout_log_id":17,"energy_estimate":{"status":"available","source":"compendium_met_net","net":true,"energy_kcal":{"low":106.4,"central":152,"high":197.6}}}]}
```

Un'attività esplicitamente saltata entra nel rientro B13 come perdita di dispendio
netto, non come cibo ingerito. Una voce non ancora confermata non è uno zero:

```json
{"deviations":[{"date":"2026-10-06","slot":"activity","kind":"activity","planned_session_id":42,"planned_expenditure_kcal":{"min":106.4,"max":197.6},"difference_kcal":{"min":106.4,"max":197.6},"provenance":{"source":"skipped_planned_activity","energy_source":"compendium_met_net","net":true}}]}
```

### 8.4 — carichi, due sedute e poco tempo

Le risposte di `GET /api/workouts/catalog` aggiungono ad ogni esercizio
`load_curve`, `load_prescription`, `load_source`. Un carico manuale dichiarato
resta valido e ha precedenza; in sua assenza il sistema usa la curva e i pesi
disponibili. La curva non inventa il carico degli esercizi a tempo o senza dati.

```json
{"exercise_id":"dumbbell-floor-press","load_kg":20,"load_source":"personal_curve","load_curve":{"status":"available","M":30.4347826087,"k":23,"reference_M":30.4347826087,"week_start":"2026-10-05","parameters":{"version":"load-curve-v1","fallback_k":30,"k_min":10,"k_max":60,"ema_alpha":0.3,"last_sets":12,"winsor_fraction":0.2,"max_weekly_increase":0.05,"evidence":"heuristic_pending_8.2"},"warnings":[]},"load_prescription":{"status":"available","load_kg":20,"estimated_kg":21.2121212121,"reps":8,"rir":2,"rounding":"down"}}
```

Uno o due riferimenti risolvono `carico=M/(1+r/k)`. Con due serie incoerenti o
`k` fuori da **10–60** si torna a 30 e si avvisa. Questo intervallo, il limite
5%, l'EMA 0,3 e la winsorizzazione ±20% sono euristiche in attesa di 8.2.
I registri aggiornano M sulle ultime 12 serie con kg, ripetizioni e RIR/RPE;
il riferimento della settimana conclusa resta fisso durante la settimana.
Un'ulteriore protezione usa l'ultimo carico prescritto nella settimana conclusa:
non si supera il suo 105%, prima dell'arrotondamento. Rigenerare non aumenta il
limite. Una griglia di pesi troppo larga può quindi mantenere il carico invariato.

```json
{"load_prescription":{"status":"unavailable","reason":"Nessun carico disponibile per difetto della stima.","estimated_kg":3.8}}
```

`POST /api/workouts/{log_id}/sets` accetta anche l'RPE della **serie**, salvato
insieme a `RIR=clamp(10-RPE,0,4)`; un RPE presente prevale sul RIR inviato.
Senza entrambi, la serie non alimenta la curva. I registri personali restano
isolati per utente.

```json
{"exercise_id":"dumbbell-floor-press","set_no":1,"reps":8,"kg":20,"rpe":8}
```

Risposta `DayView` invariata; `GET /api/workouts/logs/{id}` espone:

```json
{"sets":[{"exercise_id":"dumbbell-floor-press","set_no":1,"reps":8,"kg":20,"rpe":8,"rir":2}]}
```

I limiti già salvati in `goals.activity` (`max_session_minutes`,
`max_sessions_per_day`, `min_gap_hours`) ora vincolano il MILP. Il limite di
**10 serie per muscolo e seduta** usa il proxy esistente dei protocolli con serie;
non attribuisce serie efficaci inventate ai circuiti a tempo. Non si propone
un limite fisiologico alla durata. Le sessioni registrate sono conservate.

Con due sedute ammesse, `workout.start_times[date]` può essere una coppia di orari.
Il solver controlla il divario fra **fine della prima e inizio della seconda**,
in Europa/Roma anche nel cambio d'ora. Senza una coppia esplicita assegna 09:00
(o l'orario singolo fornito), poi massimo di durata + pausa minima. Se non entra
una seconda fascia nella giornata, resta una sola fascia. Nessun hard bound
viene rilassato; volume soft non raggiunto compare in `volume_coverage.unmet`
e `explanation.tradeoffs`. La tabella conserva due sessioni separate e i loro log.

```json
{"workout":{"start_times":{"2026-10-06":["08:00","14:00"]},"sessions_min":2,"sessions_max":2}}
```

```json
{"workout_sessions":[{"date":"2026-10-06","session_id":"strength_dumbbells","start_time":"08:00","duration_seconds":1380},{"date":"2026-10-06","session_id":"strength_dumbbells","start_time":"14:00","duration_seconds":1380}],"volume_coverage":{"unmet":{},"per_session_hard_sets_proxy_limit":10,"evidence":"heuristic_pending_8.2"}}
```

Il catalogo aggiunge `superset_full_body` («Superserie a corpo intero»,
spinta/trazione alternate poi squat) e `timed_compound_circuit` («Circuito
multiarticolare a tempo»). Durate complete, pause e transizioni sono compilate
come per gli altri protocolli. `efficiency` per sessione e `efficiency_examples`
per protocollo mostrano serie/minuto (null se non definite) e muscoli/minuto,
**proxy, non efficacia**. Con meno di 40 minuti disponibili il costo soft del
solver favorisce questi proxy di efficienza, senza cambiare la durata hard.

```json
{"protocol_id":"superset_full_body","efficiency":{"hard_sets_per_minute":0.4166666667,"muscles_per_minute":0.4861111111,"basis":"dose_proxy_not_effectiveness"}}
```

### 8.5 — proposta dei target quotidiani dall'attività

`POST /api/goals/day-targets/proposal` (CSRF) calcola una proposta **senza cambiare
il profilo né il diario**. La richiesta seleziona le sessioni già applicate della
settimana oppure un piano palestra/congiunto posseduto dall'utente:

```json
{"week_start":"2026-10-05"}
```

```json
{"week_start":"2026-10-05","plan_set_id":12,"plan_id":34,"estimated_non_workout_kcal":1800}
```

`estimated_non_workout_kcal` è facoltativo (1000–6000 kcal, finito). È una base
**senza allenamenti** dichiarata dall'utente. Altrimenti si usa la base Salute
senza allenamenti, scenario centrale. Senza Salute valida, si dichiara la base
stimata dal target di riposo attuale meno il bilancio approvato (oppure dal target
quotidiano se manca quello di riposo): **non è un consumo misurato**. Una stima
esplicitamente approvata resta riutilizzabile per 14 giorni; una vecchia base
Salute non viene resa recente dall'approvazione.

Per ogni data: `requested_kcal = baseline.central_kcal + net_activity_low_kcal +
energy_balance_target_kcal`. Il bilancio deve essere già approvato o dichiarato
manualmente, entro ±1000 kcal. Le proteine sono costanti fra i giorni e per kg
filtrato: il rapporto iniziale deriva dai target proteici già scelti dall'utente,
non da una nuova dose prescritta; dopo l'approvazione si conserva quel parametro.
I grassi restano protetti e i carboidrati assorbono il residuo calorico.

La variazione settimanale del **target quotidiano** è limitata a `min(100 kcal,
5% del target precedente)`, con intervalli del profilo invariati. Restano i minimi
fissi della ricalibrazione: 1400 kcal, 45 g proteine, 25 g grassi, 90 g carboidrati.
Se il profilo o il residuo dei macro non li permettono, nessuna proposta viene
salvata. Una grande differenza viene proposta gradualmente, con `limited:true`.

Risposta (estratto: `days` contiene realmente sette date e nutrienti completi):

```json
{"status":"available","proposal":{"id":8,"state":"pending","state_token":"TOKEN_OPACO","version":"activity-targets-v1","week_start":"2026-10-05","data_source":"applied_diary_sessions","energy_balance_target_kcal":0,"weight":{"value_kg":80,"date":"2026-10-06","filter":"progress-v2"},"baseline":{"status":"available","source":"current_target_minus_approved_balance_estimate","low_kcal":1440,"central_kcal":1800,"high_kcal":2160,"uncertainty":"Base non misurata; ±20% è un intervallo di sensibilità euristico, non un intervallo di confidenza."},"parameters":{"protein_g_per_kg":1.5,"protein_basis":"existing_approved_protein_target_per_filtered_kg","fat_target_g":50,"energy_scenario":"low","maximum_weekly_change_kcal":100,"maximum_weekly_change_fraction":0.05},"days":[{"date":"2026-10-06","day_type":"training","requested_kcal":1906.4,"proposed_kcal":1890,"delta_kcal":90,"net_activity_low_kcal":106.4,"limited":true,"targets":{"kcal_100g":{"min":1400,"target":1890,"max":3000},"protein_g_100g":{"min":45,"target":120,"max":200},"fat_g_100g":{"min":25,"target":50,"max":100},"carbs_available_g_100g":{"min":90,"target":240,"max":400}},"session_energy":[{"session_id":"activity:walking_brisk","status":"available","source":"compendium_met_net","net":true,"energy_kcal":{"low":106.4,"central":152,"high":197.6}}]}],"limits_applied":["fixed_nutrient_floors","existing_nutrient_intervals","maximum_weekly_change_100_or_5pct","constant_protein_per_kg","no_automatic_target_changes"],"reasoning":["Base senza allenamenti + energia netta prudente delle sessioni + bilancio già approvato."],"uncertainty":["MET e intervalli sono stime; dose proteica mantenuta dal profilo, non una nuova prescrizione della matrice 8.2."]}}
```

`day_type_targets.rest/training` contiene la media dei giorni pianificati di quel
tipo, con nutrienti e intervalli completi. Se un tipo non è presente, conserva i
valori già dichiarati. Le quantità per data sono in `days[].targets`.

I MET di fallback palestra sono locali in `config/workout-energy-estimates.json`,
con codici e fonti verificati nel [Compendium 2024, esercizi](https://pacompendium.com/conditioning-exercise/)
e [cyclette](https://pacompendium.com/bicycling/). L'associazione di un protocollo
all'intensità del MET resta **euristica**: si accredita solo la fase di lavoro,
non riscaldamento, pause o transizioni. Fonte `compendium_workout_net_work_phase`,
scenari ±30%. Con almeno tre allenamenti recenti compatibili si preferiscono i
quantili personali sulla durata completa. Nessuna chiamata di rete automatica.

```json
{"session_id":"strength_dumbbells","status":"available","source":"compendium_workout_net_work_phase","compendium_code":"02054","mapping_evidence":"heuristic","work_minutes":2,"net":true,"energy_kcal":{"low":4.6666666667,"central":6.6666666667,"high":8.6666666667}}
```

Indisponibilità (HTTP 200, nessuna riga di proposta e nessun valore zero fittizio):

```json
{"status":"insufficient_data","reason":"Serve una pesata recente per il peso filtrato.","missing":["weight"]}
```

Altri motivi leggibili: bilancio non approvato, bilancio completo disabilitato,
macro incompatibili con i limiti, sessione senza energia/durata verificabile,
importazione in corso oppure variazione dei target già approvata negli ultimi
sette giorni. Sessione o piano di un altro utente: 404; input invalido: 400.

Decisioni (CSRF): `POST /api/goals/day-targets/proposal/{id}/approve` oppure
`.../{id}/reject`. Il token è opaco e va ricopiato dalla proposta:

```json
{"state_token":"TOKEN_OPACO","reason":"Preferisco mantenere i valori attuali"}
```

```json
{"id":8,"status":"approved","targets_changed":true,"diary_changed":false}
```

```json
{"id":8,"status":"rejected","targets_changed":false,"diary_changed":false}
```

L'approvazione verifica di nuovo i limiti e salva atomicamente target per tipo e
per data; il rifiuto registra la motivazione. Dati, profilo, diario, sessioni,
modelli Salute o piano selezionato modificati, token diverso, proposta chiusa o
scaduta (sette giorni): **409**, nessuna modifica parziale.

```json
{"code":"activity_targets_state_changed","detail":"Dati, programma o profilo cambiati: richiedi una nuova proposta"}
```

Un bilancio appena approvato in 8.1 può essere tradotto in target nello stesso
turno; dopo l'approvazione dei target il limite di sette giorni è condiviso con
la ricalibrazione. L'approvazione non riscrive pasti o allenamenti già applicati.

`POST /api/plans/joint-week` può ora omettere `day_targets` e usare quelli
approvati nel profilo. Per le date con la stessa firma delle sessioni pianificate
usa i target puntuali; altrimenti usa i target approvati per tipo. Valori espliciti
nella richiesta hanno precedenza. Se il profilo cambia, non riusa i target per
data o la base stimata precedente e avvisa. Le stime approvate senza Salute
restano riconoscibili dalla loro provenienza anche negli scenari congiunti.

Per la UI mostrare: valore precedente, richiesto e proposto; limite applicato;
base e sua fonte; energia netta prudente delle sessioni; bilancio approvato;
peso filtrato con data; proteine e loro rapporto mantenuto; motivo ed incertezza.
«Usa i valori proposti» invia l'approvazione, poi rigenera il piano; in caso di
409 richiede una nuova proposta. Evitare di presentare gli intervalli euristici
come misure o intervalli di confidenza.

### Matcher: conversioni approvate e spezie in traccia

Interfaccia locale (non HTTP):

```
python scripts/match_recipe_ingredients.py --approve-conversion CANONICO UNITÀ GRAMMI --conversion-source "Fonte verificata" --conversion-by "Autore"
```

File `config/ingredient-unit-conversions.json`, formato:

```json
{"version":"ingredient-unit-conversions-v1","conversions":{"cipolla_cruda":{"piece":{"grams":100,"source":"Fonte verificata","approved_by":"Autore","approved_at":"2026-10-06T10:00:00+00:00"}}}}
```

I grammi sono per unità; la quantità deve essere esplicita e positiva. Fonte e
autore sono obbligatori. Il canonico deve essere già approvato; l'occorrenza deve
anche superare i controlli di compatibilità e non essere esclusa dai batch.
Un riferimento nel dizionario o una proposta di Gemini non è un'approvazione.
L'elenco di tracce (`canonical_ids`, `exact_names`) è estendibile nel file
`config/recipe-special-sources.json`. Sono ammesse solo le tre combinazioni
`salt and pepper`, `salt & pepper`, `salt and black pepper`, con soglia combinata
conservativa invariata; altri composti con `and`/`&` non diventano tracce.

Audit locale prima/dopo: 834 ricette; pesi risolti **300 → 300**, pronte
**26 → 26**. Nessuna conversione nutrizionale è stata approvata in questo turno:
il nuovo registro è vuoto, in attesa della revisione delle fonti e dei pesi.

### 8.11 — Lista della spesa e report A4

`GET /api/week/2026-10-05/shopping-list?include_all=false` (autenticato):
solo pasti applicati da oggi in avanti ancora `unknown`; `include_all=true`
include tutti i pasti del piano della settimana, anche già consumati. Nessuna
scrittura. 404 `week_not_applied` se non esiste una settimana applicata propria.

```json
{"week_start":"2026-10-05","status":"ok","scope":"remaining_unconsumed_meals","as_of":"2026-10-06","included_meals":5,"items":[{"canonical_id":"CREA:000800","food":{"source":"CREA","id":"000800"},"name":"Pasta di semola","grams":500,"occurrences":5,"department":"Pasta, riso e cereali","locations":[{"date":"2026-10-07","slot":"lunch"}],"product":{"source":"OFF","id":"8076800195057"},"product_name":"Spaghetti N°5","brand":"Barilla","package_g":500,"packages":1}],"trace_condiments":[{"name":"Sale e pepe","grams":null,"department":"Condimenti in traccia"}],"unresolved":[],"warnings":[],"identity_rule":"Precise CREA id or unambiguous reviewed recipe ingredient"}
```

Le identità sono specifiche: id CREA oppure associazione non ambigua dei candidati
revisionati della stessa voce di ricetta; i prodotti preferiti sono ricondotti
all'id generico dichiarato. Nessun raggruppamento indiscriminato di tutte le
verdure o tutte le carni. Senza associazione verificata un prodotto conserva
source+id. Le ricette verificate sono scomposte proporzionalmente al peso
selezionato; brodo diluito conta solo il dado effettivo, acqua esclusa.
Reparti assegnati con euristica sul nome; condimenti in traccia separati senza peso.
Le confezioni sono arrotondate per eccesso solo per `quantity` OFF `g`/`kg`
singolo (mai ml o multipack ambiguo), altrimenti `package_g`/`packages`: null.
Un preferito è un suggerimento di acquisto: il piano nutrizionale resta quello
calcolato. Composizione non verificata: `status: partial`, `unresolved[]` con
`food`, `grams`, `reason`, senza inventare ingredienti.

`GET /api/week/2026-10-05/report.pdf?include_all=false`: stessi permessi e
scope della spesa, `application/pdf`, attachment `piano-2026-10-05.pdf`,
`Cache-Control: no-store`. Documento italiano A4 generato con ReportLab locale:
copertina/bilancio, sette giornate, pasti e ingredienti delle ricette, nutrienti,
allenamenti (serie, ripetizioni, carichi, durata), riepilogo e spesa.
Quantità sconosciute indicate «Non disponibile». Nessun servizio esterno.
Dipendenza `reportlab` in requirements; font DejaVu Sans di sistema incorporato.

### 8.6 — Rientro con attività facoltativa

`POST /api/rebalance/preview`, stesso contratto e CSRF del 6.2/B13:

```json
{"date":"2026-10-05","slot":"dinner","preset":{"id":"pizzeria","size":"medio"},"activity":{"mode":"walk","max_minutes_per_day":45}}
```

`activity` è facoltativo, default `none`; `liked` usa solo attività gradite
non escluse nel profilo, `walk` la camminata normale. Durata 5–45 a passi di 5,
poi minimo/massimo del catalogo e durata personale. Non viene aggiunta palestra.
Restano applicazione esplicita, anteprima senza scritture e 409 sullo stato
cambiato; «non compensare» non inserisce sessioni.

Campi aggiunti (numeri illustrativi, non una prescrizione):

```json
{"status":"partial","budget":{"correction_kcal":280,"correction_diet_kcal":180,"correction_activity_kcal":100,"remaining_excess_kcal":{"min":120,"max":300}},"days":[{"date":"2026-10-07","before_kcal":2000,"after_kcal":1910,"reduction_kcal":90,"activities":[{"activity_id":"walking_moderate","minutes":35,"energy_kcal":{"low":91.47,"central":130.67,"high":169.87},"source":"compendium_met_net"}]}],"limits":{"activity":{"maximum_activity_share":0.5,"maximum_added_minutes_per_day":45,"maximum_added_activities_per_day":1,"energy_scenario":"low"}},"workout":{"required":false,"status":"optional","requested_mode":"walk","explanation":"Attività facoltative richieste, conteggiate nello scenario basso; confermale quando svolte.","excluded_days":[]}}
```

I giorni mostrano la **riduzione del cibo**; correzione totale = dieta + energia
bassa aggiuntiva. `after_week_kcal` resta l'energia ingerita, senza sottrarre
l'attività dal cibo. MILP con durate intere: attività <= riduzione dieta
(quindi <=50% del totale effettivo), massimo una/giorno; distribuzione totale
entro 25 kcal, deficit netto massimo 500 kcal, minimi nutrizionali invariati.
Sessioni intense (attività MET>=6) e palestra di intensità non verificabile
escluse prudenzialmente; rispettato il numero personale massimo di sessioni.
Senza peso filtrato/modello energetico verificabile, nessuna attività aggiunta:
il rientro può usare il solo cibo, motivo in `excluded_days`.
Nello scostamento negativo si restituisce cibo senza aggiungere dispendio.
Dopo `apply` le attività sono `chosen`, confermabili via API attività; se saltate,
B13 ripristina una volta il **credito basso realmente utilizzato**, non lo
scenario alto. Budget precedente conserva la correzione totale; il limite
cumulativo del cibo conserva separatamente la riduzione alimentare.
