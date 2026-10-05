# Consegna backend — ribilanciamento 6.2 / UI 6.3

Contratto v2 (B13), aggiornato prima dell'implementazione; conserva il percorso preset/custom della versione 1. Nessuna modifica a web/static/.

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

Si conservano tutti i minimi nutrizionali del profilo/piano, con pavimenti aggiuntivi di 1400 kcal, 45 g di proteine, 25 g di grassi e 90 g di carboidrati. La differenza delle riduzioni tra giorni modificabili è al massimo 25 kcal: distribuzione, non compensazione concentrata. Mai si riduce più del surplus **minimo** stimato: l'intervallo protegge dall'eccesso di compensazione. Per questo una stima larga può consentire solo un rientro parziale anche se lo scenario alto sarebbe compensabile. La riduzione massima sicura è un problema MILP, verificato indipendentemente; un risultato senza soluzione verificata non diventa una proposta.

I target personali non cambiano. Si modificano soltanto le porzioni/pasti futuri entro i target approvati. Gli intervalli del consumato restano intervalli nel diario: `eaten` per quei nutrienti è null; `consumed_estimate` conserva la stima e `eaten_range` ne espone i limiti. Le analisi che richiedono calorie esatte dichiarano copertura insufficiente.

## Decisioni

`POST /api/rebalance/{preview_id}/apply` e `POST /api/rebalance/{preview_id}/keep`, corpo `{}`, CSRF obbligatorio. Nel percorso preset/custom entrambi registrano il nuovo pasto come consumato con provenienza; nel percorso dal diario non aggiungono consumi. `keep` lascia invariati tutti i pasti futuri. `apply` è disponibile solo per una proposta verificata (`full`/`partial`). Risposta:

```json
{"decision":"keep","recorded":{"date":"2026-10-05","slot":"dinner"},"changed_days":[],"status":"recorded"}
```

Anteprime in memoria, durata 30 minuti; riavvio/scadenza richiede nuova anteprima. Token riservato al proprietario. `409 stale_preview` se profilo, diario, misure, allenamenti o piano sono cambiati dopo l'anteprima; `404` token sconosciuto/scaduto. Scrittura e verifica nella stessa transazione. Un doppio clic non duplica il pasto. `400 unavailable_preset` per taglie senza dati; `400 invalid_input` per intervalli mancanti/invertiti/non finiti; `409 slot_already_logged` per un pasto già consumato.

## Campi da mostrare

Mostrare stima min–max e fonte, surplus min–max, correzione proposta e residuo min–max, date e porzioni cambiate, limiti applicati, motivo del rientro parziale/indisponibilità. Etichette consigliate: «Pasto fuori programma», «Rientro possibile», «Lascia il piano com'è». Nessun messaggio punitivo; nessuna promessa di peso perso derivata da un singolo pasto.

Il budget espone anche `reference_week_kcal` e `after_week_kcal` come intervalli: consumi registrati quando disponibili, altrimenti pasti pianificati (`reference_scope`). Il residuo riguarda lo scostamento settimanale aggregato dei pasti registrati e del nuovo pasto eventuale, al netto dei rientri già applicati.

Un profilo con spuntino pomeridiano disattivato resta una giornata intera: la completezza si valuta sui pasti previsti dal profilo, senza inventare pasti o nutrienti mancanti.

## B12 — Cambiamenti minimi (portion-first-v1)

Il solver prova nell'ordine: porzioni degli alimenti già pianificati (marca e codice conservati), sostituzioni dei soli pasti principali, infine colazione e spuntini. Una soluzione sicura con soli grammi ha precedenza anche quando il rientro è parziale: la proposta non forza sostituzioni per recuperare le ultime calorie. Entro il primo livello fattibile massimizza il rientro sicuro e minimizza poi il costo dei cambiamenti. I livelli successivi si usano quando il precedente non permette alcuna correzione verificata.

Porzioni: passi di 5 g rispetto alla porzione originale, entro ±20%; si rispettano anche i limiti configurati quando contengono la porzione originale. Un piano precedente con porzioni fuori dai nuovi limiti conserva il riferimento originale e il limite ±20%: non viene riscritto per adeguarlo alla nuova configurazione. Prodotti contati in confezioni restano fissi nel primo livello. Minimi nutrizionali, deficit, massimi e distribuzione restano vincoli rigidi.

`change_policy` dichiara versione, livello scelto (`grams`, `main_meals`, `all_meals`), passo, flessibilità, costo delle sostituzioni (10000 per alimento nuovo), costo aggiuntivo delle modifiche agli spuntini (100000) e codici esclusi. All'interno del livello si penalizzano anche il numero di alimenti modificati e la distanza in grammi. `days[].changes` comprende solo pasti realmente cambiati; applicare la proposta scrive solo questi pasti. Il preset pizzeria esclude tutte le pizze del catalogo dai pasti modificabili successivi. Senza identificazione del piatto (valori liberi senza nome/codice), il backend non può inferirne l'identità dai soli macro; non inventa un'associazione.

Prima/dopo e distinzione fra osservazione UI e prova riproducibile: [audit B12](rebalance-b12-audit.md).

## B13 — Contratto v2: scostamenti settimanali e rientro simmetrico

Prima dell'implementazione: la stessa anteprima può partire dal diario già registrato. Corpo esclusivo (senza slot, preset o custom):

```json
{"date":"2026-10-05","from_diary":true}
```

Si sommano gli scostamenti consumato − previsto dei pasti registrati fino a oggi nella settimana corrente. Un pasto saltato è un consumo zero esplicitamente registrato, un pasto sconosciuto non è zero e non entra nel conto. Un pasto aggiunto senza previsione ha previsto zero, con provenienza esplicita. Macro/calorie mancanti in un pasto registrato rendono l'analisi indisponibile. Le stime restano intervalli. Anche il percorso preset/custom include gli altri scostamenti già registrati; il nuovo pasto viene contato una volta soltanto.

La soglia minima è **100 kcal settimanali garantite**: fino a 100 inclusi, oppure con intervallo che attraversa zero, `unchanged`. Uno scostamento positivo permette una riduzione, uno negativo una restituzione. Il segno di `correction_kcal` e `days[].reduction_kcal` segue la riduzione: positivo = togliere kcal, negativo = aggiungerle. Restituire non supera mai il deficit garantito (estremo negativo più vicino a zero), 200 kcal/giorno o i massimi dei target approvati. La differenza fra correzioni giornaliere resta al massimo 25 kcal, con gli stessi minimi protetti. Nessun allenamento obbligatorio.

Esempio ridotto di restituzione (gli array reali includono i prodotti e tutti i nutrienti):

```json
{"preview_id":"token","status":"full","source":"diary","estimate":{"date":"2026-10-05","from_diary":true},"deviations":[{"date":"2026-10-05","slot":"dinner","planned_kcal":650,"consumed_kcal":{"min":300,"max":300},"difference_kcal":{"min":-350,"max":-350},"provenance":{"source":"diary"}}],"budget":{"excess_kcal":{"min":-350,"max":-350},"previous_correction_kcal":0,"correction_kcal":-350,"remaining_excess_kcal":{"min":0,"max":0}},"limits":{"minimum_weekly_deviation_kcal":100,"maximum_daily_reduction_kcal":200,"maximum_daily_addition_kcal":200,"maximum_reduction_spread_kcal":25},"days":[{"date":"2026-10-06","before_kcal":1800,"after_kcal":1860,"reduction_kcal":-60,"changes":[{"slot":"lunch","before":[],"after":[]}]}]}
```

Esempio sotto soglia:

```json
{"status":"unchanged","source":"diary","budget":{"excess_kcal":{"min":70,"max":70},"correction_kcal":0,"remaining_excess_kcal":{"min":70,"max":70}},"days":[],"explanation":"Lo scostamento settimanale garantito non supera 100 kcal: il piano resta invariato."}
```

`apply`/`keep` mantengono endpoint, corpo `{}`, CSRF e controllo atomico 409. Sul percorso `from_diary`, **non si registra nuovamente alcun pasto**: `keep` chiude soltanto l'anteprima; `apply` modifica esclusivamente il diff dei pasti futuri. Risposta:

```json
{"decision":"keep","recorded":null,"changed_days":[],"status":"closed","week_start":"2026-10-05","correction_kcal":0}
```

I rientri già applicati nella stessa settimana/piano sono conservati nel registro delle decisioni e sottratti dallo scostamento: ripetere l'analisi può considerare soltanto il residuo, senza compensare due volte il totale. Anche il limite giornaliero di 200 kcal resta cumulativo rispetto al piano prima dei rientri, non si riparte da zero a ogni clic. `previous_correction_kcal` rende esplicito questo conto. Una decisione è monouso anche quando `keep` non modifica il diario; un secondo clic risponde 409. Un vecchio rientro privo di quantità verificabile rende indisponibile una nuova compensazione, invece di inventare il recupero già effettuato.

La UI deve mostrare «Calorie da recuperare» per il segno positivo e «Calorie da restituire» per quello negativo, quantità garantita/intervallo, soglia, residuo e motivo dell'indisponibilità. `deviations` espone le fonti dei pasti utilizzati. Il budget `after_week_kcal` conta i consumi già registrati una sola volta. `change_policy` resta quella di B12.


## B14 — Risultati non verificabili

Gli errori nella verifica del vettore Optees (prima ottimizzazione e minimo cambiamento), nella decodifica settimanale/giornaliera e nei controlli finali di sicurezza restituiscono **HTTP 200**, `status: "unavailable"`, `reason` leggibile, `days: []`, correzione zero e nessun piano applicabile. Anche un risultato incompleto, non finito o un errore di calcolo viene rifiutato. L'anteprima non scrive nel database e l'azione `apply` su questo risultato risponde 400. CSRF e conflitti 409 restano invariati.

Esempio ridotto:

```json
{"status":"unavailable","reason":"Il risultato di Optees non è verificabile: una quantità o variabile è fuori dai limiti ammessi.","days":[],"budget":{"correction_kcal":0},"verification":{"status":"failed","stage":"grams","phase":"result","code":"variable_out_of_bounds","error_type":"ValueError","variables":[{"name":"d0_locked_q3","value":155,"lower":100,"upper":150,"integrality":"C","date":"2026-10-06","slot":"lunch","food_id":"000800","reference_grams":125}]}}
```

`verification` offre diagnostica limitata (massimo 12 variabili); per valori mancanti/non finiti `value` è null. Non è una deroga ai vincoli: la soluzione rimane rifiutata. La UI mostra `reason`, senza trattare il risultato come un'anteprima applicabile.

### Indagine del limite e doppio rientro

Il ±20% si calcola sulle porzioni **attualmente** pianificate, quindi dopo un rientro usa il riferimento aggiornato; non sulle porzioni del primo piano della settimana. I limiti delle variabili di quantità vengono ora espressi direttamente sugli estremi raggiungibili a passi di 5 g, identici nel modello settimanale e nelle verifiche giornaliere. Una porzione preesistente inferiore a 5 g resta fissa se non ammette un passo; non si genera un intervallo invertito. Restano fermi i limiti calorici cumulativi e i target approvati.

La copia della settimana di prova della UI, con target personali abilitati e scenari Salute sintetici, permette due applicazioni consecutive con Optees reale senza violare il margine aggiornato. Il test HTTP riproducibile parte da pasta 45 g fuori dagli attuali limiti configurati (simulazione del piano pre-B12), registra due scostamenti e applica entrambi i rientri; verifica ±20%, passi di 5 g, limiti cumulativi e anteprime senza scritture. Il risultato originale che generò «Variabile fuori limite» non è conservato: non si attribuisce quella specifica violazione al margine senza poter osservare il vettore. La nuova diagnostica conserva nome, valore, limiti e riferimento per identificarla se ricompare. Non si allargano le tolleranze di verifica per accettare un risultato fuori limite.
