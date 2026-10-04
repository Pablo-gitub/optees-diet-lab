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

## Configurazione personale — passo 3.3

`GET /api/workouts/config` restituisce `settings`, `missing_fields` (campo, domanda, scelte quando disponibili), `equipment_options`, `variant_options`, protocolli e stato per sessione (`equipment_feasible`, `personal_configuration_complete`, `pending_configuration`). La UI può chiedere solo i campi elencati nella sessione/protocollo scelto. La conferma per alta intensità è opzionale e riguarda solo `cardio_hiit`.

`PATCH /api/workouts/config` salva solo il proprio profilo e restituisce il DayView di oggi con `workout_configuration` nello stesso formato. Esempio sintetico, **non carichi personali consigliati**:

```json
{
  "level":"beginner",
  "equipment":["manubri"],
  "available_loads_kg":[4,6,8],
  "starting_loads_kg":{"dumbbell-floor-press":4,"dumbbell-deadlift":6},
  "variants":{
    "dumbbell-floor-press":{"variant":"standard","executable":true},
    "dumbbell-deadlift":{"variant":"standard","executable":true}
  },
  "intensity_confirmed":true,
  "protocol_overrides":{"strength_sets":{"sets":2,"reps":4,"rest_seconds":120}}
}
```

- Livelli ammessi: `beginner`, `intermediate`, `advanced`; `null` = non dichiarato. Il livello non inventa carichi o progressioni.
- `equipment:null` = non ancora configurato, `[]` = solo corpo libero; i nuovi profili non ereditano l'inventario personale di Paolo. Una sola volta, l'inventario locale già dichiarato in `data/personal/equipment.json` viene trasferito al profilo personale originario `paolo`, se abilitato alle diete personali. Configurazioni esistenti non vengono sovrascritte. Livello, carichi, varianti e intensità restano da dichiarare.
- Kg per **singolo manubrio**: il carico di partenza deve comparire in `available_loads_kg`. Nessun riempimento automatico dei carichi mancanti. `0` è accettato come carico esterno esplicitamente dichiarato per esercizi a corpo libero; non è un manubrio disponibile.
- Mappe annidate (`variants`, `starting_loads_kg`, `protocol_overrides`) sono sostituzioni complete della mappa inviata; i campi di primo livello omessi restano invariati. Per cancellare una mappa inviare `{}`. Per aggiornare un solo esercizio la UI unisce la mappa corrente prima di inviarla.
- Varianti: push-up standard, ginocchia o mani rialzate (panca); squat standard o assistito con sedia; trazioni australiane `feet_on_floor`, con barra disponibile e `australian_pullups_setup_verified:true`. Le altre varianti del catalogo sono `standard`. Le dichiarazioni `executable:false` e gli attrezzi mancanti escludono la sessione anche in modalità demo.
- Override dei soli parametri del protocollo; la timeline viene ricompilata e l'EMOM deve conservare il recupero minimo. Un aggiornamento non valido viene rifiutato interamente. Riscaldamento e defaticamento demo non vengono trasformati in una prescrizione personalizzata.
- Il catalogo mostra anche i template indisponibili con ragioni; il solver li esclude. Aqua bag e aqua tank sono salvabili come inventario ma restano in `pending_custom_equipment`, senza protocolli verificati.
- `demo:false` nella richiesta settimanale richiede la configurazione personale completa per ogni candidato. **Le sessioni e il PlanSet conservano `demo:true`**, perché i protocolli derivano ancora dalle bozze: il PlanSet aggiunge `require_personal_configuration:true`. Nessuna certificazione automatica dell'efficacia individuale.
- Gli intervalli richiedono sia `high_intensity_ready:true` nel profilo sia `allow_high_intensity_demo:true` nella richiesta, oltre ai vincoli di disponibilità. Non vengono selezionati per default.
- Configurazione in tabella privata separata: un salvataggio del profilo dieta non la cancella. I log e i piani già applicati conservano la sessione salvata. Un candidato generato prima di una modifica della configurazione non può essere applicato: 409 `configuration_changed`, rigenerare la settimana.

## Verifica passo 3.1

166 test verdi; audit con Optees reale: due candidati di settimana, 67,83 e 106 minuti entro 110, giorno escluso rispettato. I test API verificano stati, idempotenza, validazione, CSRF, proprietario, serie senza carico, protezione delle sessioni avviate e separazione dal diario.

## Verifica passo 3.3

175 test verdi. Audit Optees reale: settimana isometrica con profilo sintetico completamente dichiarato e `demo:false` nella richiesta; candidato verificato, `demo:true` conservato nei template e nel PlanSet. Test di assenza di carichi dedotti, separazione dei profili, migrazione dell'inventario una sola volta, invalidità atomica degli override, barra australiana, varianti, filtro HIIT, snapshot immutabile, candidati obsoleti. Raffinamento B4 verificato sul catalogo reale: query «mela» include «Mele, fresche» CREA con dati completi prima delle corrispondenze meno pertinenti. Nessuna modifica a `web/static/`.

## Commit e prossimo turno

- B1–B5: `9e45ae0` (con ulteriore regressione reale mela/mele in `dd599f5`).
- 3.1: `18ab5c6`.
- 3.3: `dd599f5`.

Prossimo lavoro frontend: passo 3.2, usare questi endpoint e le domande di configurazione per completare il profilo; poi QA media 3.4. Non aggiungere calorie allenamento ai target: collegamento Salute e ottimizzazione congiunta appartengono a 4.1. I lavori Gemini non relativi a questi passi restano fuori dai commit di Codex.
