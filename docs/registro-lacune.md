# Registro di bug e lacune

Aggiornato: 8 ottobre 2026. Raccolta delle evidenze emerse durante il redesign e dei feedback del proprietario. Non è un audit completo dell’app né del solver. «Implementato» nelle fasi indica il perimetro consegnato, non l’assenza di difetti o la completezza del prodotto.

## Stati e priorità

- Aperto: problema osservato o limite confermato nel codice.
- Da verificare: rischio o percorso non ancora verificato; non dichiarato bug.
- Corretto, verificato nel perimetro: modifica presente nella working tree con verifiche indicate; non implica rilascio o verifica completa.
- Alta: salvataggi, funzionalità promesse ma inutilizzabili, coerenza tra UI e solver.
- Media: orientamento, configurazione e accessibilità.

## Elenco operativo

| ID | Tipo / priorità | Evidenza e conseguenza | Stato | Correzione e criterio di chiusura |
|---|---|---|---|---|
| UX-01 | Navigazione / alta | La bottom bar mantiene sette voci; a 360/390 px alcune aree misurate sono larghe 28–39 px. Non è stata applicata la ricollocazione della fase 1. | Aperto | Applicare la proposta più recente: Oggi, Settimana, Allenamento, Cucina; appbar con avatar e menù personale. Verificare leggibilità, aree di tocco, tastiera e ritorni da schermate secondarie. |
| UX-02 | Architettura / media | Profilo e Abbinamenti sono ancora nella navigazione principale; Esci e tema occupano l’header. La nuova proposta include anche Progressi nel menù personale. | Aperto | Menù avatar: Profilo, Progressi, Gusti e abbinamenti, Impostazioni, Esci separato. Tema nelle Impostazioni. Collegamento ai progressi anche da Oggi. Menù utilizzabile con tastiera, focus ed Escape. |
| UX-03 | Accessibilità / media | I pulsanti della navigazione usano la classe active, ma nella demo manca aria-current. | Aperto | Comunicare la pagina corrente semanticamente e mantenere un orientamento chiaro nelle destinazioni secondarie; verificare focus e navigazione. |
| FOOD-01 | UI / disponibilità solver / alta | Cucina mostra ricette catalog_only e unavailable insieme alle ready. L’utente può apprezzare una ricetta che non può aggiungere al piano. | Aperto | Nel catalogo principale mostrare soltanto ricette utilizzabili; allineare ricerca, filtri e preferiti. Spiegare eventuali preferiti divenuti indisponibili senza cancellare il gusto. Verificare ricetta → bozza → solver → piano applicato. |
| WORK-01 | Salvataggio / alta | Con carico iniziale di 40 kg e pesi disponibili 2, 4, 5, 6, 12 il server rifiuta correttamente l’intera configurazione. Il toast temporaneo e il conteggio del salvato fanno sembrare ignorati tutti gli input. | Corretto, verificato nel perimetro | Aggiunti validazione, errore persistente associato al campo, unità per manubrio, stato delle modifiche e conservazione input. Verificati rifiuto di 40, salvataggio di 12, completezza dopo ricaricamento, resa mobile; 8 test configurazione passati. La pagina già aperta richiede ricaricamento. |
| WORK-02 | Catalogo / solver incompleto / alta | workout_sessions definisce la sessione con pesi usando solo dumbbell-floor-press e dumbbell-deadlift. Bilanciere e panche sono selezionabili nell’inventario, ma non hanno un percorso equivalente nei programmi con carichi. La UI comunica una copertura più ampia dell’effettiva. | Aperto | Esporre chiaramente il supporto effettivo; completare esercizi, protocolli, requisiti e carichi per gli attrezzi supportati. Chiudere con generazione reale e registrazione dei movimenti aggiunti, non solo con checkbox o nomi nel catalogo. |
| WORK-03 | Modello attrezzatura / alta | available_loads_kg è una lista per manubrio; manca un modello di barre vuote, manubri componibili, dischi con quantità e compatibilità condivisa. Gli stessi pesi sono usati nella prescrizione corrente. | Aperto | Distinguere manubri fissi, componibili e bilancieri. Inventario unico dei dischi con peso e quantità, compatibilità e limiti; derivare carichi montabili con montaggio simmetrico e risorse sufficienti per due manubri. Migrare i dati esistenti senza inventare dotazioni. Verificare quantità limitate, pesi condivisi e unità diverse. |
| WORK-04 | Configurazione / media | L’utente deve elencare manualmente i pesi e indicare in anticipo carichi per due esercizi; non comprende perché proprio questi. | Aperto | Preset modificabili per l’inventario; carico personale chiesto nel contesto del movimento e ultimo valore disponibile nelle sessioni successive. Esplicitare sempre peso per manubrio o totale sulla barra. Non dedurre capacità personale dal possesso dell’attrezzo. |
| GOAL-01 | Funzionalità incompleta / media | La fase 5 supporta un solo criterio per milestone e proiezioni temporali solo sul peso. | Aperto, limite documentato | Chiarire il limite nella UI; progettare criteri multipli e relative regole prima dell’estensione. Nessuna data stimata per metriche prive di modello adeguato. |
| QA-01 | Verifica trasversale / alta | Mancano le verifiche della fase 6: tutti i nuovi percorsi con generazione reale, milestone attiva, approvazione calorie e copertura Salute. I test selezionati non dimostrano la completezza dei solver. | Da verificare | Matrice per funzione: input UI → persistenza → vincolo del solver → output → applicazione → ricaricamento. Documentare casi non supportati, fallimenti e risultati. Aprire bug specifici solo quando riprodotti. |
| QA-02 | Layout adattivo / media | Sono state controllate alcune schermate a 360/390 px; zoom, tastiera e flussi secondari non sono stati verificati sistematicamente. | Da verificare | Verifica mobile, finestra intermedia e desktop, zoom 200%, testo lungo, focus, sovrapposizioni e recupero errori. Layout adattivo con navigazione coerente, senza nascondere funzioni essenziali. |

## Ordine di lavoro proposto

1. Consolidare salvataggi e messaggi persistenti; WORK-01 è corretto, altri form vanno verificati.
2. Riallineare navigazione e disponibilità delle ricette (UX-01/02/03, FOOD-01).
3. Ridisegnare inventario e unità dei carichi, poi ampliare il supporto effettivo degli esercizi (WORK-02/03/04).
4. Eseguire la matrice UI–solver e la verifica adattiva; aggiornare questo registro con nuovi bug riproducibili.

Per ogni nuovo bug registrare: schermata, passi, input, atteso, ottenuto, persistenza dopo ricaricamento, ambiente e verifica della correzione. Non usare dati sanitari personali nei fixture o negli screenshot di verifica.

## Riferimenti

- [Roadmap UX](ux-redesign-roadmap.md)
- [Perimetro e limiti della fase 5](ux-phase5-implementation.md)
- Codice: web/static/index.html, web/static/style.css, web/static/workout.js, scripts/workout_configuration.py, scripts/workout_sessions.py.

## Tappa 1 · Contratto backend del catalogo (10 ottobre 2026)

FOOD-01: parte backend corretta, integrazione e verifica UI ancora da completare.

- `GET /api/recipes`: `ready_only=true` per default; ricerca, cucina e cucine preferite operano sul sottoinsieme pronto per il profilo. Filtro prima di conteggio e paginazione. `ready_only=false` consente una consultazione esplicita del catalogo completo.
- `GET /api/cuisines`: opzioni e conteggi delle sole ricette pronte per il profilo.
- `GET /api/recipes/preferences`: preferiti conservati, compresi quelli `catalog_only` o `unavailable`, con `solver_reason` e il precedente campo `reason` coerenti. Nessuna scrittura durante la lettura.
- `preferred=true` continua a indicare le cucine preferite, non le singole ricette salvate.
- Disponibilità solver distinta dalla compatibilità strutturale con i pasti: nessuna modifica agli stati `compatible`, `needs_complements`, `needs_review`.
- Verifica: 29 test passati fra `test_recipe_diet_compatibility` e `test_web`, inclusi paginazione, ricerca, filtri, conteggi, motivi, isolamento dei preferiti e conservazione nel database temporaneo. Verifica browser e suite completa della tappa ancora da eseguire insieme all’interfaccia.
