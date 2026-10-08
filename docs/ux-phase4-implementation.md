# Fase 4 · Settimana, confronto e applicazione

8 ottobre 2026 · Implementata e verificata.

## Percorso realizzato

**Settimana attiva → prepara bozza → confronta → rivedi applicazione → applica → calendario e spesa aggiornati.**

Prima il Piano apriva direttamente i controlli di generazione. La settimana congiunta salvava obiettivi e bilancio nel Profilo prima di conoscere l’esito del calcolo (U2). Ora Settimana apre il calendario applicato, distingue una proposta dal piano attivo e raccoglie la configurazione in “Prepara una nuova bozza”.

Il calendario mostra pasti, registrazioni, blocchi e attività; ogni giorno conduce a Oggi mantenendo la data. Spesa e PDF derivano dalla settimana applicata. Il rientro resta raggiungibile per la settimana corrente pertinente. L’esplorazione di una singola giornata conserva il proprio tab.

L’ambito è esplicito: **solo alimentazione**, **alimentazione e allenamento**, **solo allenamento**. La generazione degli allenamenti parte dallo stesso luogo; Allenamento mantiene sessioni, configurazione e catalogo libero, con un ingresso alla pianificazione centrale.

## Parametri della bozza e Profilo

`jointRequest()` invia target e bilancio al calcolo senza chiamare il salvataggio del Profilo. Anche “Genera alternative” della giornata invia il programma come parametro della richiesta senza salvarlo nel Profilo. Sono disponibili un ingresso distinto al Profilo e “Riparti dai valori del Profilo”. Fonte e data di approvazione degli obiettivi sono mostrate quando disponibili; le proposte riportano data del calcolo e parametri espliciti usati.

Disponibilità, attività extra, limiti delle sessioni/cardio e obiettivi della bozza possono essere modificati senza alterare le impostazioni permanenti. Minimi e massimi sono validati; gli input non validi non diventano silenziosamente zero. Per la dieta è possibile scegliere quante proposte cercare, entro i limiti del motore. Nessun vincolo nutrizionale viene rilassato dalla UI.

I campi della configurazione sono conservati nel browser con chiave per account, anche se temporaneamente non validi. Calcoli e proposte completate sono memorizzati sul server per account. La pagina riprende un calcolo in corso e recupera una proposta tramite `#settimana?data=…&bozza=…`. La configurazione ancora non calcolata non viene sincronizzata fra dispositivi.

## Confronto e applicazione

Le schede sintetizzano le differenze; ingredienti, dettagli dei sette giorni e verifiche restano espandibili. Il confronto accoglie fino a tre proposte e usa solo criteri presenti: calorie medie, sessioni, minuti, indice di varietà, robustezza e preparazione. Un valore assente è “Non disponibile” o “Non valutato”. La robustezza mantiene visibili i requisiti dei dati Salute. Una sola proposta o nessuna soluzione hanno uno stato dedicato.

“Rivedi e applica” legge dal server cosa verrà aggiunto/sostituito e quali pasti o giornate di attività sono protetti. Il riepilogo chiarisce ambito e periodo; l’applicazione è un’azione successiva. Una proposta applicata riceve l’etichetta “Applicata in precedenza”: il calendario è la fonte del piano attuale, anche dopo modifiche successive.

L’API `POST /api/plan-sets/{id}/review` produce un token riferito al candidato e allo stato corrente. `apply` ricontrolla il token dentro una transazione `BEGIN IMMEDIATE`; applicazione e ricevuta sono atomiche. Il retry della stessa richiesta restituisce la ricevuta senza ripetere le modifiche. Il token non può essere riusato per un altro candidato o ambito.

`scripts/planning_review.py` confronta Profilo, configurazione, piani, diario, stime, sessioni, serie, misure, piatti fissati e preferenze pertinenti. Le nuove generazioni conservano lo stato di partenza; modifiche successive richiedono una nuova bozza. I pasti registrati/bloccati e le attività avviate rimangono protetti. Anche la generazione del solo allenamento passa le sessioni già avviate come vincoli al solver.

Un’applicazione parziale conserva la precedente fotografia dei target del giorno e invalida previsioni/distribuzione dei nutrienti divenute obsolete. Il Profilo non viene riscritto dall’applicazione. Le vecchie chiamate dell’API allenamento senza token mantengono la protezione dei registri e il comportamento precedente; il nuovo percorso UI usa sempre la revisione.

Migrazione: nuova tabella `plan_application` per le ricevute. `GET /api/planning/recent` restituisce esclusivamente calcoli e metadati del proprietario. `GET /api/week` aggiunge i dati del calendario senza rimuovere il contratto precedente.

## Verifiche

**54 test selezionati superati**, in 38,449 secondi:

```bash
PYTHONPATH=scripts:tests /home/paolo/anaconda3/envs/optees/bin/python -m unittest test_planning_review test_diary_service test_workout_api test_joint_api test_plan_set_alternatives test_week_report test_week_orchestration -q
```

Dopo l’ultima correzione dell’invalidazione delle previsioni nelle applicazioni parziali, rieseguiti i 14 test di revisione e API congiunta, tutti superati. Controllati sintassi JavaScript, compilazione Python e `git diff --check`.

I test comprendono: revisione senza scritture; commit con pasti protetti; doppio invio; token riferito a un altro ambito; modifica fra revisione e applicazione; rollback con alimento non valido nell’ultimo giorno; isolamento/CSRF; parametri diversi del calcolo fallito senza modifica del Profilo; target/previsioni nelle giornate parziali; sessioni avviate passate al solver; corrispondenza fra applicazione, calendario, spesa e report. Le prove delle API congiunte e delle ricette usano anche fixture e solver controllati; non sono tutte sessioni UI con Optees reale.

### Prove nell’interfaccia

Demo `/tmp/optees-ux-phase4/demo.sqlite`, copia della demo sintetica della fase 3; dati personali non utilizzati o modificati. Server locale sulla porta 8882. Per la prova congiunta la fixture è stata preparata esplicitamente con pasti completi e banana disponibile; l’allenamento resta dimostrativo.

Verificati con **Optees reale**:

- Dieta: due proposte, confronto, revisione, applicazione di 14 pasti; calendario e spesa aggiornati.
- Congiunto: prerequisito assente senza salvataggio del bilancio di bozza; stato senza soluzioni; correzione dei limiti; una proposta, revisione e applicazione di 35 pasti e una sessione.
- Solo allenamento: due proposte, confronto e applicazione; confronto dei record SQLite conferma tutti i pasti invariati.
- Lettura del DB sintetico conferma il Profilo invariato dopo calcolo/applicazione congiunti e dopo l’errore con bilancio di bozza diverso.
- Ricarica con recupero del calcolo/proposta e indicazione della precedente applicazione; Indietro/Avanti fra settimane; nuovo tentativo dopo interruzione della connessione.
- Proposta obsoleta dopo applicazione di un’altra alternativa: rifiuto esplicito e ritorno ai parametri conservati.
- Desktop, calendario a 390 px, parametri/intervalli a 360 px; overflow corretto, campi e azioni raggiungibili. Tab attraversa i campi della bozza e la revisione porta il focus al proprio titolo.

## Schermate

- [Settimana desktop](screenshots/ux-phase4/settimana-desktop.png)
- [Settimana mobile](screenshots/ux-phase4/settimana-mobile.png)
- [Confronto desktop](screenshots/ux-phase4/confronto-desktop.png)
- [Parametri e intervalli mobile](screenshots/ux-phase4/parametri-mobile.png)
- [Revisione congiunta](screenshots/ux-phase4/review-congiunto.png)
- [Recupero della proposta obsoleta](screenshots/ux-phase4/conflitto-mobile.png)

## Limiti e seguito

U2 è risolto insieme alla separazione delle azioni; U1 era stato risolto nella fase 3. Il motore mantiene i propri limiti, gli stati dimostrativi e la possibilità di non certificare l’ottimo entro il tempo disponibile. Questa fase non certifica accessibilità completa: zoom 200%, screen reader e verifica trasversale di temi/contrasto restano nella fase 6.

La fase 5 completa Cucina e Progressi, compresi grafici energia, milestone operative e proiezioni. La UI non anticipa date di raggiungimento o valori energetici assenti.
