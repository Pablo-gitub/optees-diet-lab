# Contratto API e modello dati — Oggi, Settimana, Diario, Statistiche

Stato: **bozza da approvare** (passo 2.1 di [development-plan.md](development-plan.md)). Implementazione: passo 2.2 (Codex) per diario e settimana, 3.1 per la palestra, 5.x per le statistiche complete. La generazione dei piani segue [orchestration.md](orchestration.md).

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

- Il trend del peso fino al passo 5.1 è una media mobile semplice dichiarata.
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
