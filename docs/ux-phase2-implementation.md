# Fase 2 · Primo accesso e preferenze nel Profilo

8 ottobre 2026 · Implementazione locale. Verificata con database sintetico isolato; dati personali non modificati dalle prove.

## Comportamento implementato

I nuovi profili vedono al primo login un percorso facoltativo in tre passi: cucine ed esclusioni, abitudini supportate, riepilogo. “Non ora” conserva la bozza per account e non ripropone automaticamente il questionario. Oggi offre un invito discreto; il Profilo permette ripresa e modifica.

Le modifiche alla bozza sono salvate sul server dopo una breve pausa o un cambio di campo. Navigazione e logout attendono il salvataggio; se fallisce, la schermata conserva gli input e mostra il motivo. Una chiusura prima della conferma di salvataggio richiama la protezione del browser per le modifiche pendenti. La persistenza non dipende da localStorage.

Bozza e impostazioni applicabili sono distinte. Un intervallo banana incompleto può essere rimandato e ripreso; il salvataggio finale richiede valori validi. Nessuna modifica a obiettivi, modalità, etichette personali, piani o diario durante i passi. Il completamento applica solo i campi supportati, con validazione prima del commit.

I profili esistenti ricevono uno stato iniziale opzionale ricavato dai dati attuali, senza riapertura forzata o cancellazioni. Versione 1 e revisioni sono materializzate nel JSON dell’account al primo aggiornamento. I campi legacy di prodotti, preferenze specifiche e obiettivi restano conservati.

Il Profilo ora mostra prima Gusti e abitudini, poi accessi ad attività/attrezzatura e dati/misure. Obiettivi e calorie hanno una sezione distinta dalle impostazioni avanzate. Affinamento dei gusti tramite gli Abbinamenti esistenti; dopo il completamento sono disponibili revisione obiettivi e preparazione del piano. Navigazione generale e diario restano quelli attuali, da rifare nelle fasi successive.

## Effetti dichiarati e reali

| Risposta | Persistenza finale | Effetto |
|---|---|---|
| Cucine | `preferred_cuisines` | Filtro catalogo; nessuna promessa di ordinamento del solver |
| Esclusioni ricercate | `excluded_crea_ids` | Vincoli sui codici CREA dei nuovi calcoli; nomi leggibili in UI; nessuna verifica generale allergeni |
| Frutto pomeridiano | `daily_meals.afternoon_fruit` | Presenza dello spuntino nei piani dell’intera giornata |
| Seconda barretta | `daily_meals.allow_second_bar` | Seconda unità facoltativa, se il prodotto personale ha un’etichetta compatibile |
| Porzioni banana | `daily_meals.banana_min_g/max_g` | Limiti del ramo banana nei piani dell’intera giornata |
| Nota | `preference_note` | Promemoria, non istruzione interpretata dal motore |

La giornata intera non è attivata dal questionario. Se è disattivata, la UI spiega che le abitudini vengono conservate per il successivo utilizzo. Se attiva, il completamento verifica che la formulazione abbia scelte ammissibili, per esempio dopo un’esclusione della banana. Questo controllo non promette che esista una soluzione ottima per tutti i vincoli: il solver resta responsabile della generazione.

Le domande generali sui tempi di cucina o su restrizioni non coperte non sono aggiunte con effetti fittizi. I giudizi sui piatti restano nel flusso Abbinamenti, raggiungibile dal Profilo; non sono trasformati automaticamente in esclusioni di ingredienti.

## Contratti e concorrenza

`PUT /api/profile/tastes`: CSRF e identità dell’account, versione del questionario e revisioni ottimistiche, azioni `draft`, `defer`, `complete`. Il servizio rilegge il profilo sotto transazione SQLite prima di modificare soltanto i campi pertinenti. Bozza non valida per l’applicazione non diventa configurazione attiva. Campi extra, codici non presenti e cucine inventate vengono rifiutati.

Due sessioni con revisioni diverse ricevono 409, senza sovrascrittura. La UI conserva gli input e permette di scegliere la bozza salvata oppure conservare esplicitamente quella locale sulla nuova revisione; anche in quest’ultimo caso si salva una bozza, non si applicano preferenze senza riepilogo. L’editor avanzato del Profilo invia la revisione e non può sovrascrivere una bozza più recente. L’aggiornamento generale usa inoltre un confronto sul JSON letto per rilevare modifiche durante il salvataggio.

File principali: [servizio preferenze](../scripts/taste_onboarding.py), [API](../web/app.py), [interfaccia](../web/static/taste-setup.js), [test](../tests/test_taste_onboarding.py).

## Fondazione delle milestone

[goal_milestones.py](../scripts/goal_milestones.py) definisce il contratto versione 1: lista ordinata, identità univoche, metrica, target, confronto, stato, data desiderata e finestra del criterio. Metriche iniziali: peso, massa grassa, sessioni settimanali. Stati persistibili: pending/achieved/skipped; “attiva” è derivata dalla prima pending.

L’adapter `active_definition` sceglie la prima milestone ancora da perseguire. Una successiva raggiunta non salta la precedente. Non converte automaticamente gli obiettivi legacy, non calcola ETA e non cambia il solver corrente. Persistenza operativa, proposta di salto e collegamento al pianificatore restano nella fase 5B, secondo la [specifica](ux-energy-and-milestones.md). La fase 2 prepara schema e adapter prima dell’integrazione in Settimana.

## Verifiche

26 test selezionati superati: `test_taste_onboarding`, `test_profile_defaults`, `test_daily_meals`, `test_personal_goals`. Comprendono primo profilo, logout/login, migrazione legacy, CSRF, isolamento, validazione, bozze incomplete, conflitti tra editor, mancata mutazione dei piani e passaggio delle abitudini alla formulazione. La seconda barretta compare fra le scelte del motore e lo spuntino pomeridiano scompare quando richiesto; i target restano identici. Due test verificano il contratto delle milestone.

Nel browser: primo login; passo successivo; rinvio; logout/login senza riapertura automatica; ripresa della nota; ricerca ed esclusione di “Banane, fresche”; errore con input conservati; rinvio dell’intervallo incompleto; correzione e salvataggio; focus sui titoli dei passi e sul riepilogo del Profilo; ingresso con Enter; conflitto tra due tab e recupero esplicito della bozza. Schermate del riepilogo e del Profilo a 360 px senza overflow orizzontale globale; resa desktop verificata.

Sintassi Python/JavaScript e controllo whitespace superati. Non è stata rieseguita l’intera suite; accessibilità completa, screen reader e regressioni trasversali restano nella fase 6. I test della formulazione non equivalgono a una nuova generazione end-to-end con Optees.

Anteprime: [riepilogo 360](screenshots/ux-phase2/riepilogo-360.png), [Profilo 360](screenshots/ux-phase2/profilo-360.png), [Profilo desktop](screenshots/ux-phase2/profilo-desktop.png). La demo locale usa `/tmp/optees-ux-phase2/demo.sqlite` e il profilo sintetico `ux_phase2`; l’installazione personale non è stata avviata o migrata durante le prove.

Prossimo blocco: fase 3, Oggi e registrazione con bozza coerente del pasto e sessione riprendibile, usando i flussi della fase 1.
