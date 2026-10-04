# Primo pianificatore settimanale

`scripts/plan_workout_week.py` legge configurazione e catalogo, interroga il descrittore MILP di Optees via MCP STDIO, valida ogni payload, avvia i job e salva risposte, verifiche e riepiloghi. Il servizio asincrono `run` è richiamabile dalla futura interfaccia; il browser non dovrà inviare comandi shell. Percorso del server configurabile.

```bash
python scripts/build_workout_catalog.py
python scripts/plan_workout_week.py --config config/demo-week.json
```

Richiede un Python con le dipendenze di requirements.txt. Il server `optees-mcp` viene cercato accanto al Python in uso, oppure indicato con `OPTEES_COMMAND`. Output in `data/personal/workout_week.json`, escluso da Git. Nessun piano viene automaticamente scelto o registrato come eseguito.

La configurazione demo è marcata `demo: true`: giorni in ordine lunedì–domenica, disponibilità, massimo settimanale, numero minimo/massimo di sessioni, quota cardio, distanza fra sessioni di forza e target di copertura muscolare euristica. Non sono obiettivi personali già concordati. La futura schermata deve chiedere all'utente di configurarli prima di generare un piano personale.

Due risoluzioni sotto gli stessi vincoli: minimizzare i minuti e massimizzare la somma delle frazioni di target raggiunte, ciascuna limitata a 1. Il riepilogo ricalcola la copertura dagli esercizi selezionati: le variabili ausiliarie non ottimizzate nella modalità tempo possono essere zero e non descrivono la copertura reale.

Limiti: soltanto cinque template dimostrativi, nessuna progressione dei carichi, disponibilità senza appuntamenti, recupero entro la singola settimana (confini con settimane precedenti da aggiungere), nessuna preferenza o aderenza appresa. Le due soluzioni sono estremi esplorativi, non una frontiera Pareto completa. Min-Max e bandit non sono ancora collegati.

Il server dichiara che MILP non supporta cancellazione: il limite solver è 15 secondi, il polling client 60 secondi. L'interfaccia dovrà distinguere interruzione dell'attesa da cancellazione effettiva. Problemi impossibili restano segnalati senza allentare i vincoli.
