# Roadmap del redesign UI/UX

8 ottobre 2026 · Stato: fasi 0–5 implementate nel perimetro descritto nei rapporti; grafici energetici, milestone a un criterio e finestre sul peso disponibili. Prossimo blocco fase 6, verifica trasversale.

## Obiettivo

Rendere comprensibile il percorso dal primo accesso al piano personale, semplificare la registrazione quotidiana e organizzare le funzioni esistenti intorno ai compiti dell'utente. Conservare stack, identità visiva e motore di pianificazione; introdurre cambiamenti nei servizi solo dove necessari per preferenze, bozze e salvataggi coerenti.

Base: [mappa e revisione UX](ux-map-and-redesign.md), [wireframe iniziali](ux-redesign-wireframes.html). La revisione deriva dal codice e da screenshot precedenti: la prima fase deve confermare i comportamenti nell'app. Questa roadmap riguarda il redesign; non ripropone le fasi di costruzione iniziale descritte nella [roadmap generale](roadmap.md).

## Decisioni di partenza

- Al primo accesso proporre domande brevi e facoltative sui gusti; risposte sempre modificabili in Profilo → Gusti e abitudini.
- Separare restrizioni ed esclusioni esplicite da preferenze e giudizi sui piatti. Una proposta scartata non esclude automaticamente ogni ingrediente.
- Rendere visibile quali informazioni influenzano davvero il piano. Non promettere che una risposta viene applicata finché il collegamento al motore non è verificato.
- Separare preparazione, salvataggio e applicazione: aprire un editor o generare una bozza non deve cambiare implicitamente il diario o gli obiettivi permanenti.
- Mostrare grafici di dispendio e assunzione previsti, confrontati con stime Apple Salute e diario alimentare; rendere tangibili gli avanzamenti verso gli obiettivi.
- Organizzare gli obiettivi in milestone ordinate: il solver usa la prima ancora da perseguire. Il raggiungimento anticipato di una successiva propone una scelta, senza saltare automaticamente le precedenti.
- Architettura di lavoro proposta: Oggi, Settimana, Cucina, Progressi; Profilo nell'header. Allenamento conserva una schermata dedicata con accesso da Oggi e Settimana. La sua eventuale voce autonoma resta una decisione da verificare nel prototipo.
- Ipotesi: uso quotidiano da telefono, pianificazione anche da desktop. Nessuna stima di tempo finché non sono chiarite le dipendenze di salvataggio e preferenze.

## Sequenza e risultati attesi

| Fase | Risultato da consegnare | Criterio per passare alla successiva |
|---|---|---|
| 0 · Confermare la base | Inventario corrente e prove dei percorsi in un ambiente dimostrativo isolato | Comportamenti, stati e contratti rilevanti verificati; limiti documentati |
| 1 · Disegnare flussi e navigazione | Mappa aggiornata, wireframe completi del primo uso e dei due compiti principali | Ogni funzione esistente ha una destinazione; ingressi, ritorni e salvataggi sono comprensibili |
| 2 · Gusti iniziali e Profilo | Percorso iniziale facoltativo, riprendibile, con impostazioni persistenti | Nuovo utente e utente esistente conservano e modificano le risposte senza ripetizioni o perdita di dati |
| 3 · Oggi e registrazione | Diario essenziale, editor con bozza, sessione raggiungibile e feedback persistente | Registrazione/correzione/annullamento ed errori funzionano su desktop e telefono |
| 4 · Settimana e confronto | Calendario come centro della pianificazione; confronto, applicazione, spesa e rientro | Generare non modifica gli obiettivi; applicare mostra l'ambito e rispetta gli elementi protetti |
| 5 · Cucina, Progressi e coerenza | Ricette/gusti collegati ai pasti; grafici energia, milestone e stime di raggiungimento; componenti coerenti | Dati e stime distinguibili; milestone ordinate rispettate; nessun salto automatico |
| 6 · Verifica finale | Prove trasversali, correzioni e documentazione della UI effettiva | Scenari critici superati e limitazioni residue esplicite |

Le fasi di design definiscono il percorso completo; l'implementazione procede per sezioni utilizzabili, con verifiche in ogni fase. U1 è risolto nella fase 3 e U2 nella fase 4: editor e generazione distinguono ora bozze, salvataggi e impostazioni permanenti.

## 0 · Confermare la base

- Avviare l'app con database dimostrativo isolato, senza modificare dati personali.
- Ripercorrere: nuovo profilo, impostazione gusti, generazione/applicazione settimana, correzione pasto, fuori programma, sessione di allenamento e check-in.
- Verificare come interagiscono i generatori dieta, allenamento e congiunto, inclusi conflitti e pasti già registrati.
- Inventariare le risposte già memorizzate e il loro utilizzo nei servizi: cucine, preferiti, giudizi degli Abbinamenti, esclusioni e abitudini.
- Inventariare serie energetiche, snapshot dei piani, misure e trend disponibili; verificare quali obiettivi hanno criteri misurabili e un collegamento operativo al solver.
- Verificare supporto dei cataloghi alle restrizioni. Non equiparare un'esclusione per codice alimentare a una verifica completa di allergeni o ingredienti.

Consegna: integrare nella revisione quali rilievi sono confermati runtime e quali rimangono ipotesi; matrice “domanda → dato salvato → effetto sul piano → modifica dal Profilo”.

Risultati: [rapporto fase 0 e matrice dati/effetti](ux-phase0-findings.md). Demo isolata con tre profili sintetici, generazione dieta/congiunto con Optees reale, prove visuali editor/rientro/sessione/Salute e responsive 360/390 px; 69 test selezionati superati. Il rapporto distingue prove UI, HTTP/test e codice. Verifica completa di accessibilità e regressioni resta nella fase 6.

## 1 · Disegnare flussi e navigazione

Disegnare prima questi tre percorsi, compresi gli stati vuoti e gli errori:

1. Primo accesso → gusti e abitudini → riepilogo → preparazione del primo piano.
2. Oggi → registra/correggi pasto → salvataggio → riepilogo aggiornato; accesso alla sessione e ritorno.
3. Settimana → modifica vincoli → genera bozza → confronta → applica → calendario e spesa.

La configurazione degli obiettivi resta distinta dal questionario sui gusti. Il riepilogo indica se si usano dati dimostrativi o obiettivi personali e come completarli. Produrre wireframe desktop e mobile, poi un prototipo navigabile con dati sintetici chiaramente dichiarati.

Definire URL o hash per sezione, tab e data, comportamento Indietro, ritorno dall'editor e focus. Preparare una tabella di ricollocazione di tutte le funzioni attuali: nessuna capacità deve diventare irraggiungibile nel riordino.

Consegna: prototipo reviewabile e scelte motivate, inclusa la posizione dell'Allenamento. Aggiornare i wireframe esistenti, evitando versioni contraddittorie.

Risultato: [flussi, inventario delle destinazioni e limiti della fase 1](ux-phase1-design.md), con [prototipo navigabile](ux-redesign-wireframes.html) aggiornato al posto dei wireframe statici. Verificati percorsi principali, errori simulati, ricarica, decisione milestone e layout 360/390 px. Funzioni secondarie rappresentate come destinazioni, non implementate.

## 2 · Gusti iniziali e Profilo

Domande proposte, da adattare ai dati realmente supportati:

| Passo | Contenuto | Regola di interazione |
|---|---|---|
| Esclusioni e restrizioni | Cosa evitare e per quale motivo, dove supportato | Distinguere vincoli espliciti e scarso gradimento; dichiarare eventuali limiti di copertura |
| Gusti | Alimenti, piatti e cucine preferiti o poco graditi | Poche scelte concrete; selezione neutra distinta da “non mi piace” |
| Abitudini | Colazione, spuntini, tempo per cucinare, pasti fuori | Chiedere solo informazioni utilizzabili; opzioni personali specifiche nel contesto pertinente |
| Riepilogo | Risposte ed effetto dichiarato sulla pianificazione | Modifica, completa o rimanda; ingresso al primo piano |

Ogni passo offre “Non ora”. Distinguere completato, parziale e rimandato con stato persistente per profilo, indipendente dal browser. Una nuova sessione non ripropone automaticamente il percorso dopo un rinvio: mostrarne l'accesso nel Profilo o in un invito discreto. Un'interruzione permette di riprendere senza perdere risposte.

Gli utenti esistenti mantengono preferenze e piani; ricevono un invito facoltativo a completare i dati mancanti. Non inferire risposte negative dai campi vuoti. Le modifiche indicano se valgono per nuove generazioni; non alterano automaticamente una settimana già applicata.

Abbinamenti diventa affinamento successivo dei gusti, accessibile da Cucina e Profilo. Il Profilo distingue Gusti e abitudini, Obiettivi, Attività e attrezzatura, Dati e account; mostra riepiloghi prima dei dettagli avanzati.

Dipendenze: schema/versione del questionario, persistenza, riuso dei dati correnti, contratti delle preferenze nel solver. Se una risposta non ha effetto operativo, rinviare quella domanda o dichiararne chiaramente lo scopo senza promettere personalizzazione.

Verifiche: primo accesso; rinvio; ripresa dopo logout; modifica dal Profilo; migrazione di un profilo esistente; errore di salvataggio; isolamento fra profili; prova riproducibile che preferenze e vincoli supportati raggiungono il pianificatore.

Risultato: [implementazione e verifiche della fase 2](ux-phase2-implementation.md). Percorso facoltativo con persistenza per account, migrazione non distruttiva, effetti supportati dichiarati e recupero dei conflitti. 26 test selezionati superati e prove UI su demo isolata. Schema/adapter milestone definiti; integrazione operativa nella fase 5B.

## 3 · Oggi e registrazione

- Dare priorità ai pasti da registrare e alla sessione; tutti i pasti restano raggiungibili e registrabili in qualsiasi ordine.
- Separare il riepilogo del giorno dai dettagli della settimana e dai grafici estesi.
- Implementare bozza del pasto, Salva e Annulla. Il semplice ingresso nell'editor non conferma il previsto; uscita con modifiche rende chiaro cosa viene conservato.
- Definire un salvataggio coerente per quantità, aggiunte, rimozioni e sostituzioni; evitare applicazioni parziali non rappresentate in UI.
- Mantenere conferma rapida, alternative, pasto saltato e annullamento della registrazione.
- Separare la registrazione fuori programma dalla decisione sul rientro futuro; conservare stime e anteprima delle conseguenze.
- Rendere il diario utilizzabile anche senza piano; errori persistenti con nuovo tentativo e dati secondari caricabili indipendentemente.
- Sessione dedicata: avvio, serie, recuperi, completamento e ritorno al giorno di provenienza.

Dipendenze: editor transazionale o strategia equivalente verificata; contratti diario; eventuale separazione registrazione/rientro nel servizio esistente.

Verifiche: apertura senza mutazioni; annullamento; quantità/sostituzione; salvataggio fallito; doppio invio; aggiornamento concorrente; stime; assenza del piano; ripresa dell'allenamento e timer.

Risultato: [implementazione e verifiche della fase 3](ux-phase3-implementation.md). Bozze per account, commit atomico, conflitti con input conservato, registrazione stimata separata dal rientro e recuperi persistenti. 62 test selezionati superati, con prove UI desktop e 360/390 px.

## 4 · Settimana e confronto

- Mostrare prima la settimana attiva, con calendario dieta e attività e accesso alla spesa/PDF.
- Riunire disponibilità e pianificazione in un luogo coerente; mantenere percorsi dieta sola, attività sola e congiunto con ambito esplicito.
- Preparare una bozza conservando vincoli e piatti decisi; mostrare obiettivi correnti con fonte e data.
- Separare parametri della bozza da modifiche permanenti degli obiettivi. “Genera” non salva implicitamente il Profilo.
- Confrontare alternative attraverso differenze utili e criteri effettivamente disponibili; dettaglio per giorno e informazioni tecniche consultabili.
- Prima di applicare mostrare cosa viene sostituito, pasti protetti e ambito dieta/allenamento. Dopo, rendere riconoscibile il piano attivo.
- Gestire nessuna soluzione, una sola proposta, calcolo interrotto, dati cambiati e conflitto senza perdere configurazione e contesto.

Dipendenze: chiarire precedenze fra generatori, snapshot degli input, API di applicazione e protezione dei consumi; eventuali parametri nuovi devono mantenere le regole del motore.

Verifiche: fallimento del calcolo lascia obiettivi invariati; applicazione dieta sola/congiunta; consumi protetti; conflitto; piatti fissati; corrispondenza fra piano, calendario, spesa e PDF.

Risultato: [implementazione e verifiche della fase 4](ux-phase4-implementation.md). Calendario attivo, tre ambiti di pianificazione, confronto, revisione delle sostituzioni/protezioni e applicazione atomica con ricevuta. Parametri della bozza separati dal Profilo; 54 test selezionati superati e prove UI con Optees reale su dieta, congiunto e allenamento.

## 5 · Cucina, Progressi e coerenza

Cucina raggruppa catalogo, preferiti, gusti e adattamento. Collegare un piatto al pasto e alla settimana, spiegando compatibilità e disponibilità; distinguere ricetta consultabile da ricetta utilizzabile dal solver.

Progressi mette insieme andamento, misure e check-in. Nel check-in rendere visibili freschezza/copertura dei dati e ingresso all'importazione. Le ricalibrazioni mostrano prima/dopo e richiedono approvazione esplicita; dati mancanti non diventano zero.

La specifica [Grafici energetici e milestone](ux-energy-and-milestones.md) dettaglia la nuova parte di prodotto. Implementare in tre incrementi: **5A**, confronto energia prevista/registrata; **5B**, milestone persistenti e obiettivo attivo per il solver; **5C**, proiezioni condizionali e finestre di raggiungimento. Disegnare tutti e tre già nella fase 1; definire schema e adapter delle milestone nella fase 2, prima dell'integrazione in Settimana. Il solo spostamento delle schermate non completa questa fase.

Consolidare componenti di stato, form, riepiloghi, azioni e messaggi sugli attuali token. Rifinire gerarchia, densità, tema scuro e profondità dopo i flussi: ombre selettive e microinterazioni discrete, nessun 3D operativo senza utilità concreta.

Verifiche: ricetta → pasto della settimana; preferenza → Profilo; ritorno al contesto; check-in con dati assenti/vecchi/parziali; proposta pendente dopo ricarica; nessuna funzione persa rispetto all'inventario.

Verifiche aggiuntive: diario incompleto non appare come deficit; dispendio Salute senza doppio conteggio; piano previsto conserva la versione applicata; proiezione non disponibile senza dati sufficienti; milestone successiva raggiunta prima dell'attiva produce una proposta persistente e non cambia l'obiettivo del solver senza conferma; rifiuto/rinvio non ripete la richiesta a ogni accesso.

Risultato: [implementazione e verifiche della fase 5](ux-phase5-implementation.md). Cucina → pasto futuro, energia prevista/registrata con copertura e versioni, milestone ordinate con conferma e adapter, finestre condizionali sul peso. Modello attuale a un criterio per milestone; altre metriche senza data stimata. Limiti e verifiche residue espliciti nel rapporto.

## 6 · Verifica finale e completamento

Ripercorrere nuovo utente e uso ricorrente con dati sintetici. Controllare desktop, 360/390px, testo lungo, zoom 200%, tastiera, focus, contrasto e movimento ridotto. Verificare caricamenti, vuoti, errori, conflitti e permessi pertinenti; aggiungere test comportamentali sulle nuove logiche di persistenza, bozza e applicazione, oltre ai controlli esistenti appropriati.

Il redesign è completo quando l'utente può:

- Rimandare o completare i gusti, ritrovarli nel Profilo e capire il loro effetto.
- Registrare e correggere senza salvataggi impliciti o perdita di input.
- Distinguere una proposta da una settimana applicata e trovare la spesa.
- Confrontare alternative senza leggere obbligatoriamente tutti gli ingredienti.
- Eseguire l'allenamento e fare il check-in conservando contesto e controllo.
- Confrontare assunzione e dispendio previsti/registrati, riconoscendo giorni incompleti e fonti delle stime.
- Vedere l'andamento e una finestra di raggiungimento quando stimabile, mantenendo distinta la data desiderata.
- Gestire milestone ordinate e decidere esplicitamente ogni salto proposto.

Aggiornare mappa, screenshot e documentazione alla UI implementata. Documentare limiti residui; non dichiarare conformità o miglioramenti quantitativi senza prove. Non aggiungere analytics o pubblicazione come parte implicita del redesign.

## Primo blocco di lavoro

Prima della verifica finale, consolidare le lacune emerse nel [registro di bug e lacune](registro-lacune.md): navigazione, ricette utilizzabili, configurazione attrezzatura e copertura effettiva del solver. Le fasi segnate come implementate non certificano la completezza del prodotto.

Il prossimo risultato concreto è la **verifica trasversale della fase 6**: nuovi utenti e uso ricorrente, generazione reale con milestone attiva, approvazione calorie, copertura Salute, responsive e accessibilità. Verificare inoltre il limite attuale di un criterio per milestone.

## Avanzamento

- [x] Revisione iniziale, mappa e tre wireframe statici.
- [x] Roadmap con raccolta iniziale dei gusti.
- [x] Fase 0: verifica nell'app e matrice dati/effetti.
- [x] Fase 0: demo sintetica isolata, matrice preferenze, inventario energia/misure e prove dei contratti principali.
- [x] Fase 0: percorsi visuali e verifiche responsive residue, con limiti documentati nel rapporto.
- [x] Fase 1: flussi completi, ricollocazione delle funzioni e prototipo navigabile con dati sintetici.
- [x] Fase 2: primo accesso, bozze per account, Profilo e fondazione schema/adapter milestone.
- [x] Fase 3: Oggi, editor con bozza e salvataggio atomico, fuori programma e sessione persistente.
- [x] Fase 4: Settimana, confronto, parametri di bozza e applicazione con revisione/receipt.
- [x] Fase 5: Cucina, Progressi e componenti.
- [x] Fase 5A: grafici energetici e copertura.
- [x] Fase 5B: milestone ordinate, persistenza e integrazione solver.
- [x] Fase 5C: proiezioni e finestre di raggiungimento.
- [ ] Fase 6: verifica trasversale e documentazione finale.
