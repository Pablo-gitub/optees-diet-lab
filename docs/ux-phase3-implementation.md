# Fase 3 · Oggi e registrazione

8 ottobre 2026 · Implementata e verificata su ambiente dimostrativo isolato.

## Risultato

Oggi mette prima il prossimo pasto da registrare e l’attività della giornata. I pasti sono registrabili in qualsiasi ordine; quelli già registrati diventano riepiloghi espandibili, con tutte le azioni ancora disponibili. Quantità, aggiunte, rimozioni e sostituzioni passano da un editor dedicato: aprirlo prepara una bozza e non conferma il piano.

Il percorso è **Oggi → Modifica → bozza → Salva pasto → Oggi aggiornato**. “Annulla modifiche” scarta la bozza senza cambiare il diario; “Conserva bozza e torna” permette di riprenderla anche dopo una ricarica. Le bozze sono salvate per account, data e pasto. Errori e conflitti restano visibili conservando gli input.

Un pasto fuori programma può essere registrato subito come intervallo stimato. La registrazione non avvia il solver e non modifica i giorni futuri. La valutazione del rientro rimane un’azione distinta. Gli intervalli non vengono trasformati in calorie esatte o in grammi fittizi.

La sessione di allenamento mantiene serie registrate e scadenza del recupero dopo una ricarica. Il recupero saltato viene persistito; il completamento parziale dichiara quante serie sono state registrate. “Torna alla giornata” conserva la data di provenienza.

## Contratti e protezioni

- `scripts/meal_drafts.py`: persistenza delle bozze, revisione e impronta del diario di partenza; validazione di tutte le righe prima della sostituzione atomica del pasto. Quantità ammesse: 1–3000 g o 1–20 unità, massimo 100 alimenti.
- API `GET/PUT /api/diary/draft`, `POST /api/diary/draft/commit` e `/discard`: autenticazione, CSRF e isolamento fra account. Il commit usa una transazione; un doppio invio dello stesso contenuto è idempotente, un contenuto diverso con la stessa revisione viene rifiutato.
- Conferma rapida, salto e reset accettano la revisione del pasto: un aggiornamento concorrente non viene sovrascritto silenziosamente. I chiamanti precedenti senza revisione restano compatibili.
- `POST /api/rebalance/register`: registra la stima senza generare o applicare un piano futuro. Il retry della stessa registrazione è idempotente.
- `workout_log.rest_until` conserva la scadenza del recupero; la ripetizione del salvataggio di una serie non riavvia il timer. La conclusione della sessione lo cancella.
- Le migrazioni aggiungono la tabella delle bozze e la colonna del recupero all’avvio dell’app.

Il risultato del salvataggio aggiorna Oggi direttamente dalla risposta del commit. Settimana e statistiche vengono caricate separatamente: un loro errore non impedisce l’uso del diario. La UI distingue obiettivi dell’intera giornata, obiettivi per pranzo/cena e piani precedenti con ambito non dichiarato. Una giornata incompleta non viene presentata come totale definitivo.

Gli hash conservano sezione e contesto: `#oggi?data=…`, `#pasto?data=…&slot=…`, `#sessione?log=…&data=…`. L’uscita dall’editor attende il salvataggio della bozza; il focus torna al pasto aggiornato.

## Verifiche eseguite

**62 test selezionati superati**:

```bash
PYTHONPATH=scripts:tests /home/paolo/anaconda3/envs/optees/bin/python -m unittest test_meal_drafts test_diary_service test_workout_sessions test_meal_rebalance test_workout_api test_taste_onboarding -q
```

Dopo l’ultima protezione sul retry del commit, rieseguiti i **9 test delle bozze**, tutti superati. Superati anche controllo sintattico JavaScript, compilazione Python e `git diff --check`.

Le prove UI hanno usato `/tmp/optees-ux-phase3/demo.sqlite`, dati sintetici e server locale sulla porta 8881. I dati personali non sono stati modificati. Il workout della demo è una fixture esplicitamente dimostrativa, non una nuova generazione reale.

Verificati nell’interfaccia:

- Apertura del pasto previsto senza conferma; conservazione della bozza e recupero dopo ricarica; annullamento senza modifiche al diario.
- Quantità non valida con input conservato; salvataggio della quantità corretta e riepilogo aggiornato.
- Aggiunta e rimozione di un alimento; sostituzione conservando i grammi; annullamento dell’intero gruppo di modifiche.
- Conflitto reale fra due tab: il diario cambia altrove, il salvataggio viene rifiutato, la bozza rimane visibile e può essere scartata per ripartire dal diario aggiornato.
- Registrazione di un pasto fuori programma come intervallo, senza modifica del futuro.
- Serie registrata, ricarica della sessione con recupero residuo, ritorno alla data e conclusione parziale esplicita.
- Desktop e viewport 360/390 px, controlli accessibili per nome e ritorno del focus. Nessun overflow orizzontale nelle viste controllate.

I test coprono inoltre atomicità e rollback, doppio invio, bozza vuota, pasto libero, conflitti delle azioni rapide, isolamento e CSRF.

## Schermate

- [Oggi desktop](screenshots/ux-phase3/oggi-desktop.png)
- [Oggi mobile](screenshots/ux-phase3/oggi-mobile.png)
- [Editor mobile](screenshots/ux-phase3/editor-mobile.png)
- [Conflitto con bozza conservata](screenshots/ux-phase3/conflitto.png)

## Limiti e prossimo blocco

La fase 4 completa Settimana, confronto e applicazione, inclusa la separazione fra parametri di generazione e obiettivi permanenti (rilievo U2). L’editor con salvataggio esplicito risolve il rilievo U1. La navigazione generale conserva le sezioni precedenti finché vengono rimodellate con i rispettivi flussi.

Il nuovo comando di registrazione fuori programma è verificato; non è stato ripetuto un intero ciclo UI di calcolo/applicazione del rientro con il solver reale in questa fase. Il flusso esistente resta coperto dai test selezionati e dalle prove della fase 0. La scansione con fotocamera fisica non è stata verificata.

Grafici energetici, milestone operative e proiezioni restano nella fase 5. Zoom 200%, verifica completa da tastiera, screen reader, contrasto e temi trasversali restano nella fase 6; queste prove non certificano conformità di accessibilità.
