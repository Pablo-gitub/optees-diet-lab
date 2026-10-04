# Contratto backend Progressi — T10 / frontend 5.3

Estende `api-contract.md` §4.3. Implementazione T10: B6, B7, 5.1 e 5.2; nessuna modifica a `web/static/`. Tutti gli endpoint richiedono il cookie del profilo e non restituiscono dati di altri utenti. Mutazioni: `X-CSRF-Token`, stesso controllo di origine del diario.

## 5.1 — serie e aderenza

- `GET /api/stats/summary`: conserva i quattro riquadri del contratto, aggiunge copertura e motivi di indisponibilità.
- `GET /api/stats/progress?weeks=8`: `as_of`, peso grezzo/EMA/Kalman, serie attesa e settimane (1–52, corrente inclusa).
- `POST /api/progress/check-in {date,weight_kg}`: data di lunedì, non futura. Registra una pesata manuale e analizza la settimana appena conclusa. Più pesate del giorno sono conservate; il filtro ne usa la mediana. Non cambia target.

Parametri `progress-v2` (B9): Kalman scalare direttamente sulle mediane giornaliere, rumore di processo 0,01 kg²/giorno, osservazione 0,04 kg², varianza iniziale 0,25 kg². L’EMA con emivita 7 giorni resta una serie separata facoltativa, non alimenta il Kalman. Buchi oltre 14 giorni riavviano i filtri. Non si creano pesate per riempire i buchi. La varianza del filtro non è una confidenza clinica. Punti grezzi degli ultimi 365 giorni, incluse ripetizioni; priorità alle misure manuali per l'aggregazione del giorno, altrimenti mediana Salute.

Aderenza dieta: quota dei pasti pianificati `as_planned` o entro il 10% delle kcal previste, nei soli giorni passati con tutti i pasti pianificati registrati e nutrienti noti. Minimo 5 giorni completi su 7. Giorni completi per kcal giornaliere richiedono un piano di giornata intera. Allenamento: sessioni pianificate concluse / pianificate, con almeno 5 giorni trascorsi e stato noto di tutte le sessioni passate; `skipped` è una mancata esecuzione esplicita, sessioni senza registro non valgono zero. Le sessioni libere sono conteggiate separatamente.

Serie attesa: scenari del piano congiunto effettivamente applicato, mai un piano solo generato. La previsione viene invalidata se cambia il piano; dati storici incompleti restano indisponibili. Proiezione locale dell'energia con equivalenza contabile dichiarata 7700 kcal/kg; non è il modello fisiologico dinamico NIH e non viene usata per obiettivi di peso a lungo termine. Il [NIDDK spiega perché le regole caloriche lineari non descrivono l'adattamento del peso](https://www.niddk.nih.gov/health-information/professionals/diabetes-discoveries-practice/nih-body-weight-planner). Il confronto distingue piano non seguito, risposta diversa dalla stima e compatibilità con l'incertezza; nessuna attribuzione causale al metabolismo.

## 5.2 — proposta e decisioni

Il check-in restituisce anche `recalibration` con stato e proposta, oppure motivo di indisponibilità. `GET /api/progress/recalibrations` legge la cronologia. `POST /api/progress/recalibrations/{id}/approve` e `/reject` richiedono CSRF e non accettano target dal client; 409 se dati/profilo/piani/Salute sono cambiati oppure la proposta è già chiusa. Il rifiuto si registra; l'approvazione aggiorna esclusivamente i target futuri del profilo, senza riscrivere settimane o diario. I limiti fissi e gli esempi sono riportati sotto.

## Esempio 5.1 (dati sintetici)

```json
{
  "as_of": "2026-09-21",
  "weight": {
    "status": "available", "value": 79.8, "unit": "kg", "trend_7d": -0.07,
    "raw_points": [{"date":"2026-09-14","kind":"weight","value":80,"unit":"kg","source":"manual"}],
    "points": [["2026-09-14",80],["2026-09-21",79.93]],
    "ema_points": [["2026-09-14",80],["2026-09-21",79.9]],
    "daily_points": [{"date":"2026-09-14","value":80,"filtered_kg":80,"raw_count":1,"source":"manual","reset":true}]
  },
  "expected_weight": {"status":"available","segments":[{
    "week_start":"2026-09-14","status":"available",
    "model":"short_horizon_energy_accounting_not_physiological_prediction",
    "points":[{"date":"2026-09-14","low_kg":80,"central_kg":80,"high_kg":80},
              {"date":"2026-09-21","low_kg":79.6,"central_kg":79.8,"high_kg":80}]
  }]},
  "weeks":[{"week_start":"2026-09-14","status":"available",
    "diet":{"status":"available","value":0.94,"coverage":{"complete_days":7,"required_days":5}},
    "training":{"status":"available","value":0.5,"planned":2,"done":1,"skipped":1,"unknown":0,"free_done":0},
    "comparison":{"status":"available","classification":"plan_not_followed","response_assessment":"not_assessed"}
  }]
}
```

Esempio abbreviato: nel JSON reale ci sono tutti i punti e tutti i parametri. `points` è la serie filtrata; usare `raw_points` per la vista dei dati originali, `ema_points` facoltativa. La serie attesa è composta da segmenti: non connettere settimane prive di previsione. Mostrare `status`, `reason`, copertura e provenienza accanto ai grafici. Non disegnare `null` come zero. Il confronto della risposta richiede sette giornate intere; grandi scostamenti energetici ed allenamenti liberi sono differenze di esecuzione anche quando la quota di pasti aderenti è alta.

## Prerequisiti e limiti 5.2

Servono target personali confermati (`daily_meals.enabled:true`, `targets_demo:false`), quattordici giornate intere consecutive note, aderenza dieta e allenamento almeno 80%, senza allenamenti liberi aggiuntivi e senza scarti calorici giornalieri oltre il 10%. Almeno sei date distinte di peso nei quattordici giorni, entrambe le pesate dei lunedì agli estremi, nessun buco oltre sette giorni. Salute deve avere consumo completo e recente sulle stesse quattordici giornate. Un bilancio esplicito del profilo o coerente fra le previsioni applicate è necessario; `null` non significa zero.

La stima usa la mediana delle pendenze fra pesate distanti almeno sette giorni (ogni data conta una volta). Stima contabile = apporto medio − 7700 × pendenza kg/giorno; stima provvisoria personale = 75% consumo medio Salute + 25% stima contabile. Si usa il totale Salute senza aggiungere calorie workout. Variazioni oltre 0,15 kg/giorno o consumi fuori 1000–6000 kcal/giorno non generano proposte. Incertezza dichiarata: intervallo di sensibilità almeno ±200 kcal, ampliato da rumore del peso e disaccordo con Salute, non intervallo clinico di confidenza.

Limiti operativi fissi della ricalibrazione (non requisiti individuali validati):

- Variazione comune delle kcal bersaglio: massimo **100 kcal e 5%** di ciascun target; si usa il limite più piccolo per giornata standard, riposo e allenamento. Passi di 5 kcal, senza oltrepassare gli intervalli del profilo.
- Minimi ammessi: **1400 kcal, 45 g proteine, 25 g grassi, 90 g carboidrati**. I minimi esistenti non vengono abbassati; profili già sotto i limiti richiedono revisione e non ricevono una proposta. Macro bersaglio e tutti i min/max restano invariati. Coerenza energia/macro entro 10% verificata anche dopo la variazione.
- Una sola approvazione negli ultimi **sette giorni effettivi**, anche attraversando una nuova settimana di calendario. Proposta valida solo nella settimana del check-in (meno di sette giorni dalla pesata).
- Il server ricontrolla i limiti all'approvazione; il client non può inviare propri target o limiti.

## Flusso UI e JSON 5.2 (sintetico, abbreviato)

1. Se manca il bilancio, la UI può salvarlo con `PUT /api/profile` completo, aggiungendo `energy_balance_target_kcal` (−1000…1000, oppure `null`); non assegnare automaticamente zero. `day_type_targets` può essere salvato nello stesso endpoint, con `rest` e `training` completi.
2. `POST /api/progress/check-in {"date":"2026-09-21","weight_kg":80}` restituisce `date`, `analysis` (serie e settimane), `previous_week` e `recalibration`.
3. Con dati sufficienti:

```json
{
  "recalibration": {
    "status": "available",
    "proposal": {
      "id": 12, "status": "pending", "checkin_date": "2026-09-21",
      "state_token": "sha256-dello-stato",
      "rationale": "Due settimane complete e aderenti permettono una stima provvisoria; proponiamo una variazione piccola, da approvare.",
      "data_used": {
        "start": "2026-09-07", "end": "2026-09-21", "complete_intake_days": 14, "weight_days": 15,
        "eaten_average_kcal": 1420, "health_average_kcal": 2300, "weight_slope_kg_per_day": 0,
        "day_type_target_sources": {"rest":"profile_daily_baseline","training":"profile_daily_baseline"}
      },
      "expenditure": {"status":"provisional","value_kcal":2080,"low_kcal":1640,"high_kcal":2520,"no_workout_calories_added":true},
      "energy_balance_target_kcal": 0,
      "requested_delta_kcal": 280, "applied_delta_kcal": 90,
      "allowed_delta_kcal": {"min":-90,"max":90},
      "changes": {
        "daily": {
          "before": {"kcal_100g":{"min":1400,"target":1800,"max":2400}},
          "after": {"kcal_100g":{"min":1400,"target":1890,"max":2400}},
          "delta_kcal":90
        }
      },
      "limits_applied": ["weekly_change_cap","existing_profile_intervals","fixed_nutrient_floors","macro_targets_and_bounds_preserved","energy_macro_consistency"],
      "uncertainty": {"kind":"sensitivity_range_not_confidence_interval","half_width_kcal":440,
        "limitations":["Idratazione, diario e stima del dispositivo influenzano il risultato."]}
    }
  }
}
```

Il JSON reale contiene tutti e quattro i nutrienti in `before/after`, i gruppi `daily/rest/training`, i punti di peso usati, le date di consumo, l'aderenza delle due settimane e `safety_limits`. Le provenienze dei target per tipo di giornata distinguono profilo esplicito, ultimo piano applicato e baseline giornaliera del profilo.

4. `POST /api/progress/recalibrations/12/approve {"state_token":"…"}` oppure `/reject {"state_token":"…","reason":"Preferisco attendere"}`, con `X-CSRF-Token`. Risposta `{id,status:"approved"|"rejected",targets_changed,profile}`. Il rifiuto è registrato e non modifica target. L'approvazione salva `daily_meals.targets`, `day_type_targets`, il bilancio e `personal_expenditure_estimate`, senza riscrivere piani/diario/misure.
5. Dopo approvazione aggiornare il profilo in memoria e i target `rest/training` di `diet-joint-settings`: **non riutilizzare i vecchi target memorizzati nel browser**. I piani congiunti continuano a richiedere target espliciti: una nuova richiesta può scegliere altri valori, mentre una settimana già applicata conserva i propri. La stima personale è un dato provvisorio salvato nel profilo; non viene aggiunta come ulteriore consumo ai totali Salute.
6. `GET /api/progress/recalibrations` restituisce la cronologia del solo utente (massimo 100), inclusi `pending`, `approved`, `rejected`, `superseded`, `created`, `decided`, `decision_reason`.

Mostrare all'utente: `rationale`, periodo e copertura in `data_used`, calorie prima/dopo e `applied_delta_kcal`, intervallo `expenditure.low_kcal/high_kcal`, `uncertainty.limitations` e il limite che ha ridotto la variazione richiesta. `state_token`, fingerprint e verifica matematica restano dettagli tecnici. Tono della motivazione: stima provvisoria, proposta da scegliere; non dichiarare che il metabolismo è stato misurato.

## Casi di indisponibilità e conflitto

```json
{"recalibration":{"status":"insufficient_data","reason":"Servono quattordici giornate intere registrate con aderenza dieta almeno 80%."}}
```

Altri motivi: pesate insufficienti o ripetute solo nello stesso giorno, estremi mancanti, Salute incompleta/stale, target demo o minimi non ammessi, bilancio non indicato, allenamenti sconosciuti, approvazione recente, check-in retroattivo o importazione Salute in corso. Nessuna riga di proposta viene creata in questi casi. `status:"no_adjustment", proposal:null` significa che il target è già vicino alla stima oppure i limiti impediscono una variazione; mostrare `reason` e nessun pulsante Approva.

409: `progress_state_changed` (diario, peso, piani, configurazione o Salute cambiati; aggiornare analisi/ripetere il check-in), `proposal_closed`, `proposal_expired`, `recalibration_cooldown`, `unsafe_proposal`, `health_import_running`. Vale anche per il rifiuto quando lo stato è cambiato. 403 senza CSRF; 404 per proposte di altri utenti. Niente scritture parziali: decisione e aggiornamento del profilo sono nella stessa transazione.

## Verifica e ambiente

Suite finale: 221 test unittest verdi. Coperti rumore e buchi, misure ripetute, nutrienti mancanti, snapshot/invalidazione della previsione, conteggi degli allenamenti odierni, aderenza sconosciuta distinta da zero, limiti con richieste estreme, approvazione e rifiuto, scadenza, limite mobile attraversando il lunedì, isolamento e conflitti di stato. Eseguito il comando richiesto `set -a; . ./.env; set +a; PYTHONPATH=scripts:tests:. python -m unittest discover -s tests` con il Python dell'ambiente Optees indicato da `DIET_PYTHON` in `.env` (PATH dell'ambiente attivato). Il Python base non contiene FastAPI.

Il turno frontend 5.3 può partire da questo contratto; il backend non include modifiche a `web/static/`.

Il `trend_7d` v2 è la pendenza ai minimi quadrati dei punti filtrati negli ultimi sette giorni, moltiplicata per sette; richiede punti agli estremi e non interpola i buchi.

B10: il lunedì `/api/stats/summary` usa l’ultima settimana conclusa per aderenza, kcal e allenamenti. Tutti e tre i riquadri hanno `week_start`; il peso rimane aggiornato a oggi. Dati mancanti nella settimana conclusa restano insufficient_data.
