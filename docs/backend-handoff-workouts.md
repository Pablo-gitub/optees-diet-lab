# Consegna backend palestra — passi 3.1 e 3.3

Le scritture del §5.5 di `api-contract.md` restituiscono il DayView aggiornato. Avvio, serie e conclusione aggiungono `workout_log_id`; cookie e `X-CSRF-Token` sono obbligatori. Le tabelle SQLite sono migrate automaticamente e separate dal diario alimentare. Nessun dato personale è versionato.

## Catalogo e letture per il passo 3.2

- `GET /api/workouts/catalog`: `templates`, `exercises`, `protocols`, `unavailable_sessions`. Ogni sessione espone nome, obiettivi compatibili, protocollo, serie/ripetizioni o secondi, recuperi, `timeline` completa, durata e `pending_configuration`. Media degli esercizi dal file di configurazione esistente, con attribuzioni, immagini locali e video.
- `GET /api/workouts/sessions/{session_id}`: dettaglio del template.
- `GET /api/workouts/planned/{planned_session_id}`: piano salvato con `session` immutabile rispetto a successive configurazioni personali.
- `GET /api/workouts/logs?start=YYYY-MM-DD&end=YYYY-MM-DD`: sessioni effettivamente avviate, incluse quelle aperte, nell'intervallo (massimo 366 giorni).
- `GET /api/workouts/logs/{log_id}`: sessione al momento dell'avvio, timestamp ISO con fuso, RPE, note e serie registrate. Carico/ripetizioni/secondi/RIR mancanti rimangono `null`.
- `GET /api/day` espone `workout` come nel §4.1, più `workout_log_id`, `demo`, `pending_configuration`; `GET /api/week` espone stato per giorno e conteggi. Statistiche palestra sulla settimana civile corrente, lunedì–domenica.

## Settimana palestra

`POST /api/workouts/week` → 202 `{job_id}` → endpoint job e PlanSet già esistenti. Esempio (date sintetiche):

```json
{
  "week_start": "2026-10-05",
  "days": {"2026-10-05":40,"2026-10-06":25,"2026-10-07":40,"2026-10-08":0,"2026-10-09":40,"2026-10-10":25,"2026-10-11":0},
  "excluded_days": ["2026-10-08"],
  "start_times": {"2026-10-05":"18:30"},
  "demo": true,
  "sessions_min":3,"sessions_max":4,
  "strength_sessions_min":1,"strength_sessions_max":2,
  "cardio_minutes_min":40,"weekly_minutes_max":110,"strength_gap_days":1
}
```

Minuti obbligatori per tutte le sette date, zero = indisponibile. Opzionali `goal`, `allowed_protocols`, `muscle_targets_proxy`, `allow_high_intensity_demo` (false di default). Limiti omessi dai default dichiaratamente demo di `config/demo-week.json`. Non sono target clinici personali. Il solver comune `plan_workout_week.formulate` verifica minuti completi (riscaldamento/recuperi inclusi), frequenza, recupero e lavoro cardio effettivo. Due obiettivi: meno tempo e copertura muscolare euristica. Nessuna previsione calorica inventata; l'ottimizzazione congiunta e i ruoli con bandit sono nel passo 4.1.

Il PlanSet ha `kind: "workout"`; i piani contengono `workout_sessions: [{date,session_id,minutes,start_time,session}]`. `POST /api/plan-sets/{id}/apply {plan_id,scope:"week"}` scrive esclusivamente sessioni pianificate; non modifica pasti o consumato. Sostituisce le sessioni non avviate e rimuove quelle non più presenti nella nuova settimana. Sessioni avviate, concluse o saltate sono protette e segnalate in `skipped_slots`. Nessuna applicazione automatica alla generazione.

## Registro (§5.5)

- Avvio con piano: `{planned_session_id,session_id,date}`; senza piano: `{session_id,date}`. Riavvio dello stesso piano aperto restituisce lo stesso log. Giorno registrabile fino a domani, come il diario.
- Serie: `{exercise_id,set_no,reps?,kg?,seconds?,rir?}`. Occorrono ripetizioni o secondi. `kg:0` è esplicito corpo libero; un carico sconosciuto resta `null`. Stesso esercizio/numero di serie aggiorna la riga durante una sessione aperta. Un esercizio deve appartenere alla sessione avviata.
- Conclusione `{rpe?,notes?}`: `done`, timestamp finale. Ripetere la richiesta non crea un secondo log né altera un log chiuso.
- Salto `{planned_session_id}`: idempotente prima dell'avvio; dopo avvio o conclusione restituisce 409.
- Dopo la conclusione le serie sono chiuse. Ogni lettura/scrittura controlla il proprietario; riferimenti a log o piani altrui restituiscono 404.

Le bozze dei protocolli restano indicate come demo. M1 richiede ancora l'interfaccia di Claude (3.2) e QA media (3.4).

## Verifica passo 3.1

166 test verdi; audit con Optees reale: due candidati di settimana, 67,83 e 106 minuti entro 110, giorno escluso rispettato. I test API verificano stati, idempotenza, validazione, CSRF, proprietario, serie senza carico, protezione delle sessioni avviate e separazione dal diario.
