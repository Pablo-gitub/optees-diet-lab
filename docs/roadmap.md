# Roadmap dell'app personale

## Obiettivo e confini

Una web app locale per consultare storico e giorni futuri, registrare alimentazione e attività, confrontare misurazioni e obiettivi, generare alternative con Optees. Il progetto rimane indipendente dal core di Optees.

Prima versione: un utente, SQLite, browser locale, nessun account o sincronizzazione cloud. Dati personali ed export originali esclusi da Git. Si procede per sezioni verticali utilizzabili, evitando di costruire tutta l'interfaccia prima del primo piano funzionante.

## Organizzazione dell'interfaccia

### Oggi e calendario

Pagina iniziale con riepilogo della giornata: pasti previsti e registrati, attività prevista ed eseguita, totali nutrizionali e ultima misurazione disponibile. Calendario settimanale per aprire giorni passati e futuri. Stati espliciti: proposto, scelto, eseguito, saltato. Un dato mancante non significa zero.

### Alimentazione

Diario per giorno e pasto, ricerca di alimenti e ricette, porzioni modificabili, azione rapida «conferma come consumato» e possibilità di registrare variazioni. Storico e programma usano lo stesso calendario ma conservano separatamente previsto ed effettivo. Per i giorni futuri: poche alternative confrontabili, con macro, tempo di preparazione, ripetizioni e motivazione della proposta.

### Attività

Movimento importato da Apple Salute e sessioni di palestra registrate: esercizi, serie, ripetizioni, carichi, durata e sforzo percepito facoltativo. Programma futuro con opzioni compatibili con attrezzatura e tempo disponibile. La prima versione propone routine da template; l'ottimizzazione completa di progressione, recupero e carichi viene dopo.

### Andamento

Grafici di peso, altre misure disponibili, sonno e attività; valori originali e trend su finestre dichiarate. Distinguere obiettivo scelto, previsione del modello e osservazione. Finché non esiste un modello calibrato, mostrare una traiettoria obiettivo senza presentarla come previsione. Successivamente mostrare intervalli e scostamenti, non una promessa puntuale. Nessuna deduzione causale sul singolo alimento da semplici correlazioni.

### Pianificazione e analisi

Menu a tendina con tre modalità definite in `config/planning-modes.json`: **Dieta sedentaria** (versione più recente indicata dall'utente), **Dieta palestra**, **Algoritmo libero**. Le prime due applicano calendario e abbinamenti del proprio programma di 14 giorni; la terza elimina questi vincoli mantenendo target nutrizionali, esclusioni personali, limiti di porzione e disponibilità. La modalità alimentare è distinta dalla configurazione degli allenamenti. La mappa alimentare ha un'impostazione separata, senza esclusioni automatiche derivate dai suoi punteggi.

Cambiare selezione prepara una nuova generazione e non modifica piani salvati o consumi. Ogni candidato ed esecuzione conserva modalità e versione della dieta. Il vecchio programma sedentario resta archiviato come fonte, senza una quarta opzione nel menu iniziale. Non confondere il primo test MILP degli allenamenti con un pianificatore alimentare libero già implementato: quest'ultimo resta da costruire.

Pulsante «Genera alternative» per un giorno o una settimana. Mostra stato del job, candidati, obiettivi Pareto, scenari robusti e vincoli non soddisfatti. Selezionare un piano richiede un'azione esplicita; rigenerare non sovrascrive storico o piano scelto. Possibilità di bloccare pasti, giornate e appuntamenti già decisi.

### Dati e preferenze

Import Apple Salute, riepilogo della copertura e degli errori, cataloghi e relative fonti. Target configurati dall'utente, preferenze alimentari, esclusioni, attrezzatura, orari e tempo disponibile. Un catalogo importato ampio può alimentare una lista di preferiti piccola senza reinserimento manuale.

## Architettura proposta

- Backend Python con FastAPI, SQLite e servizi separati per importazione, diario, analisi e pianificazione.
- Interfaccia HTML con template, HTMX e una libreria di grafici locale: evitare una seconda applicazione frontend nella prima versione.
- Un comando `plan` e il pulsante web chiamano lo stesso servizio di orchestrazione. Il browser invia parametri validati, non comandi shell.
- Adapter Optees isolato. Prima integrazione con il server MCP STDIO già verificato; processo riutilizzato e ambiente configurabile. Nessuna modifica al motore.
- Esecuzione dei job fuori dalla richiesta web, con stato persistito, errori leggibili e annullamento. Un solo job di pianificazione attivo nella prima versione.
- Server su loopback; dipendenze grafiche servite localmente. Nessun export sanitario inviato a servizi esterni.

Entità principali: alimenti, ricette e ingredienti; esercizi e template di routine; pasti pianificati e consumati; sessioni pianificate ed eseguite; campioni sanitari e riepiloghi giornalieri; target e preferenze; esecuzioni del pianificatore, candidati, scelte e feedback.

## Flusso algoritmico

1. Fotografare stato, target, vincoli, cataloghi e versione del modello; definire giorni bloccati e budget di tempo.
2. Preparare un insieme gestibile di ricette e porzioni discrete. Usare MILP per selezioni discrete e vincoli nutrizionali; LP dove bastano quantità continue. Validare i payload secondo i descrittori reali di Optees prima di inviarli.
3. Generare candidati variando pesi e limiti degli obiettivi. Eliminare duplicati e soluzioni dominate; non promettere che una somma pesata trovi tutta la frontiera Pareto discreta.
4. Confrontare scostamenti nutrizionali, praticità, varietà e tempo. Costo solo se esistono prezzi utilizzabili. Normalizzazioni e priorità visibili.
5. Valutare scenari dichiarati di incertezza e ordinare per perdita peggiore. All'inizio Min-Max valuta candidati già fattibili; questa graduatoria non equivale a un'ottimizzazione robusta globale. Integrare `scenario.linear.min_max_loss` solo quando la formulazione rispetta il contratto lineare disponibile.
6. Presentare 3–5 alternative e salvarne spiegazioni, scenari e risultati. La scelta umana aggiorna il programma, non il diario effettivo.
7. Registrare esecuzione, aderenza e feedback. Il bandit sceglie fra poche strategie di alto livello, non fra migliaia di ricette; partire da una simulazione e da reward di gradimento/aderenza. Non assegnare risultati ai piani non provati. Peso e composizione corporea hanno ritardi e variabilità: non usarli subito come reward giornaliero.

Ogni esecuzione conserva input, versioni, seed ove applicabile, risultati, tempi e verifiche. Se il problema è impossibile, mostrare i vincoli coinvolti e chiedere una modifica; non allentarli silenziosamente.

## Dataset e importazioni

### CREA — disponibile

832 alimenti importati con provenienza. Controllare copertura dei nutrienti per il sottoinsieme usato: valori mancanti o simbolici non diventano automaticamente zero. Distinguere peso crudo e cotto.

### Ricette — da selezionare e scaricare

Nella trascrizione sono citati Weighed-Meal Reference Set, un dataset di 333 ricette, UniTools Recipes e RecipeNLG. Sono candidati da verificare alle fonti originali: identificazione esatta, disponibilità, licenza, quantità, porzioni e mapping. Non sono ancora dataset approvati o importati.

Preferire un piccolo catalogo strutturato con grammi e porzioni. Se usa identificativi USDA, scegliere tra importare gli alimenti USDA necessari e creare un mapping verificato a CREA; non sostituire automaticamente alimenti solo perché il nome somiglia. Conservare macro dichiarati dal dataset e macro ricalcolati con fonte distinta. Annotare resa di cottura quando disponibile. Le ricette con quantità ambigue restano consultabili ma escluse dall'ottimizzazione finché risolte.

### Palestra — da selezionare e scaricare

Free Exercise DB come primo candidato; wger come alternativa o fonte di routine. Verificare licenze dei dati e dei media separatamente. Importare metadati prima delle immagini, filtrare per attrezzatura disponibile e creare template di sessioni. Questi cataloghi descrivono esercizi: non definiscono da soli una progressione personale.

Adult Compendium come eventuale fonte di MET, dopo verifica delle condizioni d'uso. Le stime MET sono facoltative: evitare di sommarle a calorie Watch che descrivono la stessa attività.

### Apple Salute e misure corporee — export in preparazione

Parser XML in streaming, import ripetibile con deduplicazione e provenienza. Conservare timestamp, fuso, unità, sorgente e tipo. Gestire sovrapposizioni iPhone/Watch, intervalli di sonno e confini giornalieri; non sommare indiscriminatamente tutti i campioni. Conservare gli originali e ricostruire i riepiloghi con regole versionate. Iniziare da passi, energia attiva, allenamenti, sonno e peso; supportare le misure Withings presenti nell'export, senza presumere che ci siano.

## Fasi e criteri di completamento

| Fase | Risultato verificabile | Stima di lavoro |
| --- | --- | --- |
| 1. Cataloghi e schema | Ricette ed esercizi identificati, licenze annotate, campione importato; schema SQLite e dati dimostrativi | 4–7 h |
| 2. Import sanitario | Export reale importabile due volte senza duplicati; copertura, unità e riepiloghi verificati su giorni campione | 3–6 h |
| 3. Prima sezione utilizzabile | Calendario, pasti previsti/consumati, sessioni e grafico del peso; dati persistenti | 5–8 h |
| 4. Primo piano Optees | Comando riproducibile e pulsante con stato job; piano fattibile per un giorno, poi settimana con blocchi | 4–7 h |
| 5. Alternative e robustezza | 3–5 candidati, filtro Pareto, scenari Min-Max, scelta esplicita e tracciabilità | 4–7 h |
| 6. Bandit e revisione | Simulazione, poche strategie, feedback sull'eseguito, revisione settimanale | 3–5 h |

Totale indicativo: 23–40 ore per tutte queste fasi, con margine aggiuntivo se i dataset richiedono molto mapping o pulizia. Le prime tre fasi danno già un diario utile; l'orchestrazione diventa operativa con la quarta. Il tempo necessario a raccogliere osservazioni per valutare il bandit è distinto dalle ore di sviluppo. Le stime vanno riviste dopo il primo import reale.

## Prossime azioni

1. Verificare le fonti originali dei cataloghi ricette ed esercizi e importare un campione rappresentativo.
2. Disegnare schema SQLite e preparare una settimana dimostrativa, marcata chiaramente come sintetica.
3. Appena pronto l'export Apple, controllare tipi presenti e qualità prima di implementare tutti gli importatori.
4. Costruire calendario e diario con un primo caso Optees piccolo, estendendoli senza rifare l'architettura.

Rimandare riconoscimento dei pasti da foto, integrazioni live Apple/Withings, account, cloud, prezzi automatici e ottimizzazione fine della progressione dei carichi.
