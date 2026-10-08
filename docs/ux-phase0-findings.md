# Fase 0 — base verificata e contratti del redesign

7 ottobre 2026. Stato: fase 0 conclusa per l'inventario e i percorsi rilevanti al redesign. Analisi e verifiche: nessuna modifica al frontend o ai dati personali. Il seguito della verifica è riportato nella sezione «Seconda sessione».

## Ambiente ed evidenze

Demo su `http://127.0.0.1:8877`, database `/tmp/optees-ux-phase0/demo.sqlite`, profilo sintetico `ux_demo`. Runtime Python dell'ambiente `optees`, cataloghi del progetto. Il database è stato prepopolato con un utente tecnico senza impostazioni personali prima di importare l'app: l'inizializzazione di un database vuoto crea altrimenti il profilo storico e copia preferenze personali. Nessuna importazione Salute personale eseguita.

Le evidenze hanno tre livelli: **UI** (interazione nel browser), **HTTP/test** (servizi eseguiti con dati sintetici), **codice** (contratto letto, senza prova visuale completa). Le prove API non dimostrano usabilità o accessibilità.

| Percorso | Risultato e livello |
|---|---|
| Nuovo profilo e accesso | Registrazione HTTP riuscita; UI entra direttamente in Oggi. Nessun questionario iniziale. |
| Gusti dal Profilo | UI: nascosti in Impostazioni avanzate. Note, cucine, esclusioni e abitudini nello stesso grande form. HTTP: note e cucina `italian` salvate e rilette. |
| Settimana dieta | HTTP con Optees reale: job completato, una proposta, applicazione riuscita. UI: pranzo e cena compaiono in Oggi. |
| Alternative di un pasto | Test end-to-end con Optees reale superato: settimana → applicazione → alternative → applicazione; cena conservata, nessuna registrazione alimentare implicita da parte dell'API di applicazione. |
| Correzione del pasto | UI: aprire Modifica sul pranzo previsto porta da 0/2 a 1/2 pasti registrati e mostra Come previsto prima di premere Fine. La registrazione implicita è confermata. |
| Quantità nell'editor | Codice: `onchange` invia PATCH immediata. Primo tentativo browser di cambiare 100→120 g non ha prodotto persistenza; tentativo con input nativo interrotto da timeout dello strumento. Il salvataggio immediato delle quantità resta da confermare nella UI; PATCH e reset coperti dai contratti esistenti. |
| Fuori piano | HTTP e UI: banana sintetica registrata senza piano, resa come Fuori piano. Il percorso completo del dialogo Fuori programma e del rientro resta da verificare visualmente; contratti rientro coperti dai test selezionati. |
| Allenamento | HTTP: avvio rifiutato senza attrezzatura compatibile; dopo configurazione cyclette, avvio e conclusione riusciti. Test delle sessioni superati. Timer e ripresa visuale non verificati. |
| Check-in | HTTP: lunedì 5 ottobre, peso sintetico, analisi restituita. Richieste senza data rifiutate correttamente. Test Progressi superati; nessuna ricalibrazione personale applicata. |
| Congiunto e conflitti | Test con solver SciPy su fixture: target e snapshot energetici applicati; registrare un pasto dopo la generazione rende la proposta obsoleta, applicazione rifiutata con 409 `planning_state_changed`. Non è una prova del solver congiunto Optees reale. |

**53 test superati**: 51 nei moduli `test_profile_defaults`, `test_progress_api`, `test_workout_sessions`, `test_meal_matches`, `test_recipe_intents`, `test_personal_goals`, `test_rebalance_diary`; 1 in `test_week_meal_e2e`; 1 scenario selezionato in `test_joint_api`. Non è stata eseguita l'intera suite. Avvisi di deprecazione Starlette/httpx presenti, nessun fallimento nelle tre esecuzioni concluse. Primi tentativi nel sandbox rimasti bloccati; esecuzioni successive concluse fuori dal sandbox. Una prima invocazione Progressi senza `PYTHONPATH=scripts:tests` non importava il modulo; corretta prima dell'esecuzione valida.

Comandi riproducibili, con il Python configurato dal progetto:

```bash
PYTHONPATH=scripts:tests python -m unittest test_profile_defaults test_progress_api test_workout_sessions test_meal_matches test_recipe_intents test_personal_goals test_rebalance_diary -q
PYTHONPATH=scripts:tests python -m unittest test_week_meal_e2e -v
PYTHONPATH=scripts:tests python -m unittest test_joint_api.JointAPI.test_generate_apply_context_targets_and_stale_diary_rejection -v
```

Log della sessione in `/tmp/optees-ux-phase0/`: `checks-escalated.log`, `solver.log`, `joint.log`, `live.log`, `follow.log`. Sono temporanei; questo documento conserva i risultati rilevanti.

## Matrice domanda → dato → effetto → modifica

| Domanda o scelta | Dato salvato | Effetto verificato nel codice | Dove si modifica oggi / implicazione |
|---|---|---|---|
| Quali cucine preferisci? | `users.profile.preferred_cuisines` | Filtro Ricette con `preferred=true`; nessun lettore di questo campo nei solver in `scripts/`. | Profilo avanzato; dichiarare effetto sul catalogo, oppure aggiungere un collegamento prima di promettere piani personalizzati per cucina. |
| Note sulle abitudini | `preference_note` | Testo conservato; nessun lettore nei solver. Non interpreta automaticamente il linguaggio naturale. | Profilo avanzato; non presentarlo come istruzione operativa al motore. |
| Quali alimenti escludere? | `excluded_crea_ids` | Esclusione per ID nei modelli dieta/ricetta, nelle opzioni aggiuntive e negli Abbinamenti. | Profilo avanzato, elenco tecnico; sostituire con ricerca e nomi. Non equivale a un filtro allergeni completo. |
| Quali ricette preferisci? | Tabella `recipe_preference` per utente | Ricette materializzabili diventano opzioni con bonus morbido e limiti settimanali. Una ricetta del catalogo può essere preferita ma non pronta per il solver. | Cuore in Ricette; aggiungere riepilogo nel Profilo, stato utilizzabile/non ancora utilizzabile. |
| Ti piace questo abbinamento? | `meal_match_vote` e payload | Like/love favoriscono combinazioni ammesse; dislike aggiunge penalità alla combinazione. Non esclude automaticamente tutti gli ingredienti. | Abbinamenti; conservare annullamento e distinguere voto sul piatto da esclusione alimento. |
| Questo ingrediente non ti piace? | `meal_match_question`; con sì aggiornamento `excluded_crea_ids` | Domanda dopo scarti ripetuti; sì introduce un'esclusione esplicita, no silenzia la domanda per un periodo. | Abbinamenti; rendere conseguenza e possibilità di modifica nel Profilo evidenti. |
| Colazione e spuntini inclusi? | `daily_meals` | Cambia l'ambito dei target e abilita scelte dedicate. Opzioni correnti molto specifiche: prodotto personale e banana, seconda barretta, frutto pomeridiano. | Profilo avanzato; non descriverlo come un catalogo generale di colazioni già disponibile. |
| Quale prodotto confezionato usi? | `food_preferences.products`, `preferred_products` | Etichetta valida e idonea utilizzabile; preferenza prodotto nell'approvvigionamento/materializzazione; prodotti con soli volumi o dati inadatti non idonei al solver. | Barcode/prodotti; riepilogo nel Profilo da progettare. Preferenza generico→prodotto distinta dall'abitudine per slot. |
| Quanto tempo hai per cucinare? | Nessun contratto generale individuato | Nessun vincolo operativo generale verificato. | Rinviare dal questionario minimo finché manca il collegamento. |
| Allergie, vegetariano, vegano? | Nessun modello completo verificato | Esclusioni per codice e ingredienti revisionati non garantiscono queste restrizioni sull'intero catalogo. | Non offrire interruttori con promessa di copertura completa. Progettare prima dati e regole di compatibilità. |
| Quale obiettivo corporeo e ritmo? | `goals.body` | Generazione di proposta energetica; modifica dei target subordinata alle decisioni previste. Non esiste una sequenza di milestone. | Profilo/calorie e Corpo; mantenere distinto dai gusti. |
| Attrezzatura e tempo di allenamento? | `workout_configuration`, `goals.activity` | Compatibilità sessioni, durata massima, frequenza e distanze; priorità allenamento nel congiunto. | Allenamento e Profilo; indicare quali campi sono operativi per ogni modalità. |

Fonti principali: `web/app.py` (`update_profile`, `make_config`, catalogo Ricette); `scripts/daily_meals.py`; `scripts/plan_diet_day.py`; `scripts/recipe_intents.py`; `scripts/meal_matches.py`; `scripts/personal_foods.py`; `scripts/workout_service.py`; `scripts/joint_orchestration.py`. La matrice distingue effetto letto nel codice da risultati runtime: non ogni singola preferenza è stata confrontata in due solve identici.

## Grafici, misure e milestone: ciò che c'è già

| Informazione | Base disponibile | Lavoro necessario |
|---|---|---|
| Assunzione prevista | Nutrienti dei pasti e dei piani applicati; snapshot pasti, ricette e input del `plan_set`. | Serie uniforme per giorno con ambito, versione e copertura. Un piano pranzo+cena non è assunzione dell'intera giornata. |
| Assunzione registrata | Diario, nutrienti esatti o intervalli per stime, stati pasti, copertura; assenza distinta da zero. | Aggregazione grafici che conserva intervalli e parzialità, senza inferire deficit dal diario incompleto. |
| Dispendio previsto | Scenari baseline e allenamenti; congiunto salva `progress_forecast` nel contesto giornaliero. | Esporre serie e provenienza; confrontare soltanto ambiti compatibili. |
| Dispendio Salute | Report giornaliero, energia attiva/a riposo, copertura e fonti; dati privati per profilo. | Usare totale senza aggiungere nuovamente calorie workout. Verifica in demo con fixture Salute sintetica ancora da eseguire visualmente. |
| Peso e trend | Misure manuali/Salute, filtro e trend settimanale. Check-in con giorni completi e dati sufficienti. | Vista coerente fra punti registrati, trend e intervalli. |
| Previsione peso settimanale | `expected_week`: contabilità energetica a breve orizzonte dal piano congiunto applicato, solo con ancora e scenari completi validi. | Non convertirla automaticamente in data certa di raggiungimento a lungo termine. |
| Obiettivi | Peso, massa grassa, circonferenze selezionate; priorità e carichi allenamento. | Specificare quali criteri hanno misure e modello utilizzabile. Mancano milestone ordinate, stati, conferme di salto e adapter dell'obiettivo attivo. |
| Data di raggiungimento | Proposta energetica con stima semplice; non un sistema generale di proiezioni condizionali per ogni metrica. | Modello per metrica, dati minimi, finestre, versioni e stato non stimabile. |

Il report Salute applica soglie di copertura/freschezza: almeno 7 giorni utili e riferimento non più vecchio di 14 giorni per la baseline. Questo limite riguarda l'uso predittivo, non autorizza a nascondere tutta la storia registrata. La previsione peso esistente è dichiarata `short_horizon_energy_accounting_not_physiological_prediction`.

## Rilievi UX confermati e nuovi

1. **Registrazione implicita confermata (U1)**: Modifica registra prima di aprire l'editor. Progettare bozza, Salva e Annulla con contratti coerenti.
2. **Gusti poco raggiungibili, confermato**: primo login senza raccolta; impostazioni avanzate espongono una lunga lista di cucine insieme a target e abitudini. Progettare percorso breve e riepilogo nel Profilo.
3. **Promessa di personalizzazione troppo generica**: note e cucine sono affiancate a testi che suggeriscono influenza sui calcoli, ma non hanno entrambi un effetto nel solver. Esplicitare effetto reale.
4. **Ambito energetico ambiguo, nuovo rilievo**: Bilancio della giornata mostra 1135 kcal come bersaglio in modalità solo pranzo+cena e include una registrazione nello spuntino. Separare ambito del piano e totale registrato; prioritario prima dei grafici.
5. **Settimana non allineata, caso osservato**: generazione API con inizio mercoledì 7 ottobre applicata correttamente ai pasti, mentre Oggi mostra calendario 5–11 ottobre e Nessun piano attivo per questa settimana. Il caso nasce da un inizio non lunedì: verificare/normalizzare il contratto di inizio settimana e progettare un calendario che esponga la settimana applicata. Non è stato dimostrato che il form corrente produca quel caso.
6. **Vincoli attrezzatura effettivi**: avvio senza cyclette rifiutato. Presentare configurazione e motivo prima dell'azione; preservare il rifiuto del servizio.
7. **Navigazione confermata**: passare da Oggi a Profilo lascia URL `/`; ricaricare riporta a Oggi. Definire URL e ritorni nel prototipo.

U2 (Genera congiunto salva prima gli obiettivi), dipendenza del diario da caricamenti secondari, accessibilità dei marcatori e densità mobile restano rilievi da codice fino a prove dedicate. Nessuna conclusione di conformità accessibile o miglioramento quantitativo.

## Decisioni per la fase 1 e verifiche residue

La base consente di iniziare i flussi: domanda solo quando il dato ha uno scopo dichiarato; gusti separati da obiettivi; bozze distinte da applicazioni; grafici sempre con fonte, ambito e copertura. Conservare i contratti di protezione del diario e approvazione dei target.

Al termine della prima sessione mancavano prove visuali di Fuori programma/rientro, editor quantità, timer/ripresa allenamento, congiunto e Salute; responsive e tastiera. La seconda sessione sotto integra queste evidenze. La verifica approfondita di accessibilità, tutti i breakpoint e le regressioni resta nella fase 6.

Nessuna modifica applicativa effettuata. Le modifiche preesistenti in `web/static/matches.js` e `web/static/style.css` sono rimaste intatte.

## Seconda sessione — completamento delle prove residue

Tre profili distinti nel database demo: `ux_demo` per la modalità base; `ux_full` per giornata completa, Salute e generazione congiunta; `ux_rientro` per un piano completo di fixture. Le credenziali sono sintetiche e non sono salvate in questo documento. Salute contiene un export XML sintetico, importato con il parser reale: 42 record, 14 giorni, energia attiva/a riposo e pesate. Il piano di `ux_rientro` deriva dalla struttura di `test_meal_rebalance`, applicata tramite il servizio del progetto: non è una settimana generata dal solver. I flag di conferma dei target appartengono solo alla fixture.

| Prova | Evidenza osservata | Conseguenza per il redesign |
|---|---|---|
| Quantità prima di Fine | Il tasto di incremento cambia la pasta da 40 a 41 g; subito compare Modificato, cambiano le calorie e il dato resta dopo la chiusura. I precedenti tentativi con `fill` non provavano il comportamento di un input reale. | U1 confermato anche per le quantità: bozza e salvataggio esplicito. |
| Fuori programma senza piano completo | Pizzeria → Medio → stima 842–1020 kcal; anteprima non calcolabile con motivo leggibile. Lascia il piano com’è registra comunque il pasto a intervallo; il diario mostra conferma e totali non esatti. | Separare visivamente Registra pasto e Modifica piano. Il nome dell'azione corrente non esplicita la registrazione. |
| Target dimostrativi | Anche su un piano completo, il rientro richiede target personali confermati. | Esporre il prerequisito e il collegamento per completarlo prima del calcolo. |
| Rientro con piano e target completi | Fixture con target confermati: anteprima parziale, 180 kcal distribuite sui quattro giorni futuri, dettaglio prima/dopo. Accetta il rientro registra la pizza a intervallo e cambia i quattro giorni; UI conferma Pasto registrato · 4 giorni ribilanciati. | Conservare anteprima e approvazione; distinguere consumo stimato e modifica dei pasti futuri. |
| Calcolo concorrente | Anteprima rientro rifiutata mentre il congiunto usa il solver: Optees sta già calcolando. Ripetere la selezione dopo la conclusione permette di riprovare. | Stato globale del calcolo, nuovo tentativo esplicito e input conservati. |
| Allenamento | Da catalogo → Forza con manubri → Inizia oggi → prima serie Fatto: timer Recupero 3:00. Ricarica → Oggi → Continua: prima serie ancora registrata. Concludi restituisce Fatto e 1 serie registrata. | Conservare la ripresa dei log; introdurre ritorno al giorno di provenienza. |
| Recupero dopo ricarica | La serie rimane, il timer non è più visibile. | Definire persistenza dell'istante finale e ripresa del recupero, oppure rendere esplicita l'interruzione. |
| Congiunto con prerequisito assente | Genera con colazione/spuntini disattivi: messaggio con Apri il profilo. Lettura del DB demo conferma che `day_type_targets` è già salvato. | U2 confermato runtime: generazione e obiettivi permanenti devono avere azioni distinte. |
| Congiunto reale dalla UI | Generazione avviata da Piano, 3 proposte persistite, stato `partial`, circa 164 secondi nella sessione. Non è una misura prestazionale rappresentativa. Nuovi log/serie successivi rendono l'applicazione obsoleta: HTTP 409 `configuration_changed`. | Conservare controlli di conflitto e spiegare come rigenerare. |
| Ricarica durante il congiunto | Il job continua sul server; tornando a Piano dopo reload, attesa e proposte non vengono recuperate. Il risultato è leggibile via API. | Persistenza del job per profilo e recupero delle proposte pendenti. |
| Salute completa | Progressi mostra fonte Apple Salute, 14/28 giorni, ultimo giorno, energia attiva/a riposo/totale, scenari e trend del peso. | Riutilizzare copertura e provenienza nei grafici nuovi. |
| Modello energia workout mancante | Nel congiunto il giorno con cyclette ha scenari indisponibili perché manca un modello recente specifico; baseline generale disponibile non basta. | Distinguere energia giornaliera disponibile da previsione attività non stimabile. |
| Schermo 390 px | Oggi entro la larghezza disponibile nel caso osservato; sette destinazioni nella barra inferiore restano dense. | Riduzione della navigazione coerente con la proposta a quattro sezioni. |
| Schermo 360 px | Piano ha `documentElement.scrollWidth=479` con viewport 360; contenuti e controlli tagliati a destra. La barra nav arriva a 352 px e non è la causa principale. | Correggere contenitori e griglie del form; non limitarsi a ridurre la barra. |
| Progressi 360 px | Larghezza documento 360, grafico leggibile nel caso sintetico; tabelle più ampie scorrono nel proprio contenitore. | Conservare scorrimento locale delle tabelle e verificare scoperta dello scorrimento. |
| Tastiera e URL | Tab dai selettori del grafico passa da 4 sett. a 8 sett.; Enter su Profilo cambia schermata ma focus resta sul pulsante e URL resta `/`. Reload riporta a Oggi. | Route/hash e focus alla destinazione; test completi da tastiera in fase 6. |

Ulteriori **16 test superati** nei moduli `test_apple_health` e `test_joint_energy`, per unità, sovrapposizioni, copertura, freschezza e conteggio energetico. Totale delle esecuzioni selezionate: **69 test superati**, senza esecuzione dell'intera suite.

Nota sulla fixture: l'import del modulo applicativo per preparare il terzo profilo ha temporaneamente marcato interrotto il job demo già in corso, perché `initialize()` esegue quel ripristino. Lo stato è stato rimesso a running mentre il processo originale continuava; il job ha poi scritto done e le proposte. Questa interferenza riguarda la preparazione della demo e non è presentata come guasto della UI. La prova di perdita del contesto dopo reload è stata osservata prima di quell'interferenza.

Evidenze salvate in [screenshots/ux-phase0](screenshots/ux-phase0): `oggi-390.png`, `piano-360.png`, `progressi-360.png`, `rientro-applicato.png`. Tutti i dati nelle immagini sono sintetici. L'override del viewport è stato ripristinato. Screenshot e misure dimostrano questi casi, non conformità generale o assenza di problemi in ogni sezione.

## Esito e ingresso alla fase 1

La fase 0 è conclusa come base del redesign: i contratti principali e gli stati pertinenti sono inventariati, i comportamenti critici hanno prove riproducibili o limiti espliciti. Non equivale a una certificazione dell'app corrente: regressioni complete, zoom 200%, tutti i percorsi da tastiera, contrasto e movimento ridotto restano verifiche della fase 6. Il successo dell'applicazione congiunta è coperto dalla precedente fixture API, mentre nella prova Optees reale di questa sessione l'applicazione è stata intenzionalmente verificata nello stato di conflitto dopo nuove registrazioni.

Priorità vincolanti del prototipo:

1. Primo accesso breve, facoltativo e riprendibile; Profilo con riepilogo gusti ed effetto reale di ogni risposta.
2. Oggi con editor in bozza, Salva/Annulla; fuori programma con registrazione distinta dalla modifica del piano.
3. Settimana con parametri di bozza, job recuperabile dopo reload e approvazione separata dei target.
4. Grafici che espongono ambito giornaliero/pranzo+cena, fonte, copertura, intervalli e previsioni indisponibili.
5. Sessione riprendibile, recupero conservato e ritorno al giorno di provenienza.
6. Form a 360/390 px senza scorrimento orizzontale dell'intera pagina; destinazioni con URL e focus prevedibili.

Le milestone e le finestre di raggiungimento seguono la [specifica dedicata](ux-energy-and-milestones.md): nessuna sequenza operativa o salto automatico esiste già nel codice attuale.
