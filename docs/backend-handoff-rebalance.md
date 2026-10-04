# Consegna backend — ribilanciamento 6.2 / UI 6.3

Contratto v1, scritto prima dell'implementazione. Nessuna modifica a web/static/.

## Endpoint e flusso

`GET /api/rebalance/presets` restituisce il catalogo con `available` per taglia. Una taglia con uno qualsiasi dei quattro intervalli nutrizionali null è indisponibile, mai equivalente a zero.

`POST /api/rebalance/preview` richiede autenticazione e `X-CSRF-Token` come le altre mutazioni, ma non scrive nel database. Esempio:

```json
{"date":"2026-10-05","slot":"dinner","preset":{"id":"pizzeria","size":"medio"}}
```

Alternativa libera (kcal e macro obbligatori; numeri singoli sono intervalli esatti):

```json
{"date":"2026-10-05","slot":"dinner","custom":{"kcal":{"min":1100,"max":1300},"protein_g":{"min":30,"max":40},"fat_g":{"min":35,"max":45},"carbs_available_g":{"min":140,"max":160}}}
```

Data non futura, nella settimana corrente; pasto non già registrato. Il piano deve coprire la giornata intera. Il pasto sostituisce la previsione di quel pasto, senza cancellare altri consumi. Per un'aggiunta, usare uno slot non ancora consumato: non viene sovrascritto alcun consumo.

```json
{"preview_id":"token-opaco","status":"partial","estimate":{"nutrients":{"kcal":{"min":1100,"max":1300}},"provenance":{"source":"preset","preset_id":"pizzeria","size":"medio","catalog_version":"1.1","sources":[]}},"budget":{"planned_week_kcal":12600,"excess_kcal":{"min":500,"max":700},"correction_kcal":420,"remaining_excess_kcal":{"min":80,"max":280}},"limits":{"maximum_daily_reduction_kcal":200,"maximum_energy_deficit_kcal":500,"minimum_kcal":1400,"minimum_protein_g":45,"maximum_reduction_spread_kcal":25},"days":[{"date":"2026-10-06","before_kcal":1800,"after_kcal":1730,"reduction_kcal":70,"changes":[{"slot":"lunch","before":[],"after":[]}]}],"explanation":"È possibile un rientro parziale entro i limiti. Puoi anche lasciare invariato il piano.","workout":{"required":false,"status":"optional","explanation":"Nessun allenamento aggiunto automaticamente."}}
```

L'esempio omette gli altri intervalli e giorni solo per brevità. Le risposte reali comprendono tutti i nutrienti. Stati: `full`, `partial`, `unchanged`, `unavailable`. Ogni indisponibilità ha `reason`, mai valori nutrizionali inventati. Il diff riporta prodotti, grammi e nutrienti prima/dopo.

## Limiti e incertezza

Si riottimizzano con Optees i giorni successivi fino a domenica. Oggi e i giorni precedenti restano intatti. Pasti consumati, saltati o bloccati nei giorni successivi restano bloccati. La riduzione massima rispetto al piano esistente è 200 kcal/giorno; il deficit energetico massimo è 500 kcal/giorno rispetto allo scenario **basso** del consumo da Salute salvato nel piano. Senza quel dato non si propone una riduzione (indisponibilità esplicita). Non si fa doppio conteggio dell'allenamento e non si aggiunge palestra obbligatoria.

Si conservano tutti i minimi nutrizionali del profilo/piano, con pavimenti aggiuntivi di 1400 kcal e 45 g di proteine. La differenza delle riduzioni tra giorni modificabili è al massimo 25 kcal: distribuzione, non compensazione concentrata. Mai si riduce più del surplus **minimo** stimato: l'intervallo protegge dall'eccesso di compensazione. Per questo una stima larga può consentire solo un rientro parziale anche se lo scenario alto sarebbe compensabile. La riduzione massima sicura è un problema MILP, verificato indipendentemente; un risultato senza soluzione verificata non diventa una proposta.

I target personali non cambiano. Si modificano soltanto le porzioni/pasti futuri entro i target approvati. Gli intervalli del consumato restano intervalli nel diario: `eaten` per quei nutrienti è null; `consumed_estimate` conserva la stima e `eaten_range` ne espone i limiti. Le analisi che richiedono calorie esatte dichiarano copertura insufficiente.

## Decisioni

`POST /api/rebalance/{preview_id}/apply` e `POST /api/rebalance/{preview_id}/keep`, corpo `{}`, CSRF obbligatorio. Entrambi registrano il pasto come consumato con provenienza; `keep` lascia invariati tutti i pasti futuri. `apply` è disponibile solo per una proposta verificata (`full`/`partial`). Risposta:

```json
{"decision":"keep","recorded":{"date":"2026-10-05","slot":"dinner"},"changed_days":[],"status":"recorded"}
```

Anteprime in memoria, durata 30 minuti; riavvio/scadenza richiede nuova anteprima. Token riservato al proprietario. `409 stale_preview` se profilo, diario, misure, allenamenti o piano sono cambiati dopo l'anteprima; `404` token sconosciuto/scaduto. Scrittura e verifica nella stessa transazione. Un doppio clic non duplica il pasto. `400 unavailable_preset` per taglie senza dati; `400 invalid_input` per intervalli mancanti/invertiti/non finiti; `409 slot_already_logged` per un pasto già consumato.

## Campi da mostrare

Mostrare stima min–max e fonte, surplus min–max, correzione proposta e residuo min–max, date e porzioni cambiate, limiti applicati, motivo del rientro parziale/indisponibilità. Etichette consigliate: «Pasto fuori programma», «Rientro possibile», «Lascia il piano com'è». Nessun messaggio punitivo; nessuna promessa di peso perso derivata da un singolo pasto.

Il budget espone anche `reference_week_kcal` e `after_week_kcal` come intervalli: consumi registrati quando disponibili, altrimenti pasti pianificati (`reference_scope`). Il residuo riguarda questo pasto, non compensa retroattivamente scostamenti di altri pasti.
