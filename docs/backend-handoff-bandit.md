# Bandit contestuale 6.1 — backend v2

`POST /api/plans/{id}/feedback` mantiene `{rating: 1..5, tried: true}` e CSRF. Aggiunge `learning` con `status`, `reason`, `parameters` e `trials`. Il voto viene conservato anche se i dati non permettono ancora di apprendere.

La dichiarazione deve essere successiva all'applicazione e non precedente alla data della giornata provata. L'applicazione salva solo provenienza, contesto e componenti realmente applicati. Generazione e selezione non creano ricompense. Il diario completo e i log collegati alle sessioni consentono di valutare l'aderenza; componenti saltati valgono zero solo quando almeno un altro componente del piano è stato effettivamente provato. Mancanti e stime a intervallo restano insufficient_data.

Ricompensa: metà voto normalizzato `(rating-1)/4`, metà aderenza. Aderenza dieta = media della vicinanza nutrizionale dei pasti applicati, `max(0, 1 - media(abs(consumato-atteso)/max(atteso,1)))` sui quattro nutrienti. Aderenza allenamento = sessioni concluse / sessioni applicate (log collegato, fine registrata e stato done). Quando sono presenti entrambi, media delle due componenti. Il peso corporeo non entra nella ricompensa.

`GET /api/bandit/summary`, autenticato, espone `parameters`, `eligible_days`, `pending_days`, `contexts` e `trials`. Esempio semplificato:

```json
{"parameters":{"version":"contextual-bandit-v2","rating_weight":0.5,"adherence_weight":0.5,"policy":"UCB1"},"eligible_days":1,"pending_days":0,"contexts":{"hash-opaco":{"observations":3,"arms":["starch:pasta","structure:components","protocol:cardio_continuous"]}},"trials":[{"plan_id":12,"date":"2026-10-05","context":"hash-opaco","rating_normalized":1,"adherence":0.5,"reward":0.75,"status":"eligible","reason":null}]}
```

I contesti includono versione v2, programma, tipo di giornata (training/rest), target e ambito. I piani settimanali/congiunti hanno `bandit_features` per giornata; dieta e protocolli utilizzano caratteristiche e ricompense nel contesto corrispondente. Lo storico di un giorno di riposo non diventa una ricompensa per una giornata di allenamento. Il ruolo preferred compare solo in presenza di osservazioni pertinenti. UCB1 sceglie l'esplorazione tra i candidati Pareto fattibili, senza cambiare vincoli o target.

Aggiornare un voto sostituisce il voto del piano: non crea prove duplicate. Le ricompense sono ricalcolate dai registri attuali: azzerare un pasto, sostituire il piano o rendere incompleti i dati revoca l'eleggibilità. Le vecchie valutazioni senza traccia di applicazione v2 rimangono nello storico e non alimentano il bandit.

Per la UI, mostrare «Valutazione salvata» e, se learning è insufficiente, il motivo; evitare «algoritmo aggiornato» finché non ci sono dati eleggibili. Nessuna modifica frontend in questo turno.
