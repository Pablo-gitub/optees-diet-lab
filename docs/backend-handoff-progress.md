# Contratto backend Progressi — T10 / frontend 5.3

Estende `api-contract.md` §4.3. Implementazione T10: B6, B7, 5.1 e 5.2; nessuna modifica a `web/static/`. Tutti gli endpoint richiedono il cookie del profilo e non restituiscono dati di altri utenti. Mutazioni: `X-CSRF-Token`, stesso controllo di origine del diario.

## 5.1 — serie e aderenza

- `GET /api/stats/summary`: conserva i quattro riquadri del contratto, aggiunge copertura e motivi di indisponibilità.
- `GET /api/stats/progress?weeks=8`: `as_of`, peso grezzo/EMA/Kalman, serie attesa e settimane (1–52, corrente inclusa).
- `POST /api/progress/check-in {date,weight_kg}`: data di lunedì, non futura. Registra una pesata manuale e analizza la settimana appena conclusa. Più pesate del giorno sono conservate; il filtro ne usa la mediana. Non cambia target.

Parametri versionati: EMA con emivita 7 giorni e passi temporali reali; Kalman scalare sul risultato EMA, rumore di processo 0,01 kg²/giorno, osservazione 0,16 kg², varianza iniziale 0,25 kg². Buchi oltre 14 giorni riavviano i filtri. Non si creano pesate per riempire i buchi. La varianza del filtro non è una confidenza clinica. Punti grezzi degli ultimi 365 giorni, incluse ripetizioni; priorità alle misure manuali per l'aggregazione del giorno, altrimenti mediana Salute.

Aderenza dieta: quota dei pasti pianificati `as_planned` o entro il 10% delle kcal previste, nei soli giorni passati con tutti i pasti pianificati registrati e nutrienti noti. Minimo 5 giorni completi su 7. Giorni completi per kcal giornaliere richiedono un piano di giornata intera. Allenamento: sessioni pianificate concluse / pianificate, con almeno 5 giorni trascorsi e stato noto di tutte le sessioni passate; `skipped` è una mancata esecuzione esplicita, sessioni senza registro non valgono zero. Le sessioni libere sono conteggiate separatamente.

Serie attesa: scenari del piano congiunto effettivamente applicato, mai un piano solo generato. La previsione viene invalidata se cambia il piano; dati storici incompleti restano indisponibili. Proiezione locale dell'energia con equivalenza contabile dichiarata 7700 kcal/kg; non è il modello fisiologico dinamico NIH e non viene usata per obiettivi di peso a lungo termine. Il [NIDDK spiega perché le regole caloriche lineari non descrivono l'adattamento del peso](https://www.niddk.nih.gov/health-information/professionals/diabetes-discoveries-practice/nih-body-weight-planner). Il confronto distingue piano non seguito, risposta diversa dalla stima e compatibilità con l'incertezza; nessuna attribuzione causale al metabolismo.

## 5.2 — proposta (contratto prima dell'implementazione)

Il check-in restituisce anche `recalibration` con stato e proposta, oppure motivo di indisponibilità. `GET /api/progress/recalibrations` legge la cronologia. `POST /api/progress/recalibrations/{id}/approve` e `/reject` richiedono CSRF e non accettano target dal client; 409 se dati/profilo/piani/Salute sono cambiati oppure la proposta è già chiusa. Il rifiuto si registra; l'approvazione aggiorna esclusivamente i target futuri del profilo, senza riscrivere settimane o diario. Il contenuto concreto dei limiti e i JSON di esempio sono completati alla chiusura 5.2.

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
