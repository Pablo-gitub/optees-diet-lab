# Diagnosi della varietà · T-007

La causa principale è il **dominio effettivamente utilizzabile**, insieme alla scelta sequenziale dei riferimenti. Nella libera audit l’ampliamento sperimentale di frutti, verdure e amidi passa dal **59,46% al 25,48%** di sovrapposizione. Il secondo valore raggiunge il limite dimostrabile del dominio ampliato a porzioni fisse. Il 10% resta impossibile in quel dominio con le frequenze proteiche attuali. Questi numeri hanno certificazione M/B descritta sotto, budget 5 s/solve e 60 s/ricerca; non sono risultati Optees di produzione.

## Ambito, fonti e certificazione

Analisi del 12 ottobre 2026. Nessun file di produzione modificato, nessun download e nessun database letto dalla diagnosi. Input: `dataset/crea/foods.csv`, `config/demo-diet-day.json`, `config/recipe-diet-food-groups.json`, template e politiche delle ricette presenti nel repository. SciPy/HiGHS è diagnostico; Optees non è stato invocato. SHA-256 CREA: `f9052b7d93b143c008bcb26ea3c7ad58fa89c65a75d37d7612ddc6a792456f0e`.

Le regole e i calendari dell’audit storico per sedentaria/palestra sono sotto `data/personal/`, quindi non sono stati letti. Il proprietario ha autorizzato quattro **sostituti sintetici**, non repliche delle sue diete. I risultati di questi sostituti non certificano le diete reali. Le sole letture automatiche della suite sono state autorizzate separatamente; nessun dato della suite entra nell’analisi.

Ogni numero nelle tabelle eredita il codice della tabella/colonna:

- **I · budget solver 0 s:** conteggio o proprietà deterministica di sorgenti pubbliche, configurazione o formula combinatoria; non è una misura clinica.
- **M · 5 s/solve, 60 s/ricerca alternative:** quantità misurata su un pool fattibile verificato. Il budget alternative parte **dopo** il riferimento; il tempo effettivo è riportato. Tre alternative richieste; nessuna garanzia di equivalenza tra macchine/carichi.
- **L · stesso budget M:** minimax certificato numericamente entro 1 punto percentuale, solo rispetto ai riferimenti già scelti. Non certifica l’ottimo simultaneo delle tre settimane. `partial` significa riferimento nutrizionale non certificato entro il tempo; i piani rimangono verificati.
- **B · fino a 5 s per LP, senza ricerca di pool:** limite inferiore valido ottenuto da rilassamenti LP ottimali e argomento sui supporti. Non è il minimo esatto, salvo chiusura del divario indicata esplicitamente. Margine conservativo di 10⁻⁶ g sui minimi numerici; prova numerica a tolleranze HiGHS, non verifica razionale formale.
- **E · budget solver 0 s:** stima o obiettivo per una futura scheda, senza garanzia misurata; costi qualitativi basso/medio/alto. I costi di sviluppo non sono preventivi temporali.

## Scenari riproducibili

Libera: configurazione pubblica dell’audit, con porzioni sintetiche fisse. Per ciascun pasto principale: amido 50 g, verdura 100 g, proteina/legume 120 g, frutto 100 g (I); olio escluso dalla metrica. Gli altri valori fissi del precedente audit restano nel file diagnostico.

I sostituti usano gli stessi gruppi pubblici di candidati, porzioni standard e target demo di giornata intera. Nessun prodotto preferito: il comportamento attuale aggiunge solo banana nei tre pasti aggiuntivi. Tutte le giornate hanno pranzo A e cena B. Nella S1 A/B hanno gli stessi quattro gruppi; nella S2 B ammette solo riso come amido. Nei sostituti palestra B restringe anche la verdura a zucchine/pomodori. Questi nomi sono etichette di confronto, non una ricostruzione delle prescrizioni. La settimana statica di esperimento inizia il 5 ottobre 2026 (I).

### Scomposizione della coppia peggiore · M/L

La metrica è il massimo dei due rapporti direzionali di grammi canonici condivisi. Per la coppia peggiore si usa **un solo denominatore**, quello della direzione peggiore: i contributi sotto sono punti percentuali, non percentuali relative di categoria. Gli ingredienti dei pasti aggiuntivi sono attribuiti a colazione/spuntini, senza contarli nuovamente come frutta; le ricette sono attribuite a ricette, ma la condivisione continua a usare gli ingredienti scomposti. Condimenti esclusi secondo la produzione.

| Categoria · pp M | Libera audit | Sedentaria S1 · sintetica | Sedentaria S2 · sintetica | Palestra S1 · sintetica | Palestra S2 · sintetica |
|---|---:|---:|---:|---:|---:|
| Frutta | 27.03 | 15.32 | 22.38 | 23.14 | 21.63 |
| Verdura | 0.00 | 0.00 | 32.34 | 35.87 | 34.25 |
| Amidi | 0.00 | 17.94 | 8.58 | 0.00 | 8.88 |
| Proteine animali | 18.53 | 7.00 | 5.42 | 6.32 | 8.43 |
| Proteine vegetali | 13.90 | 10.72 | 3.32 | 3.46 | 3.83 |
| Latticini | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| Colazione/spuntini | 0.00 | 22.98 | 23.57 | 18.15 | 18.93 |
| Ricette | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| Altro | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| **Totale** | **59.46** | **73.96** | **95.61** | **86.93** | **95.94** |

La somma coincide con il totale prima dell’arrotondamento; lo script lo verifica con un’asserzione. La frutta domina nella libera; nei sostituti dominano i pasti aggiuntivi o la verdura a seconda della coppia, come mostrano i contributi, non un conteggio di nomi.

| Pasto · pp M | Libera audit | Sedentaria S1 · sintetica | Sedentaria S2 · sintetica | Palestra S1 · sintetica | Palestra S2 · sintetica |
|---|---:|---:|---:|---:|---:|
| Colazione | 0.00 | 7.66 | 6.48 | 5.98 | 6.31 |
| Spuntino mattino | 0.00 | 7.66 | 6.64 | 5.98 | 6.31 |
| Pranzo | 29.73 | 26.15 | 34.95 | 32.41 | 35.51 |
| Spuntino pomeriggio | 0.00 | 7.66 | 10.44 | 6.19 | 6.31 |
| Cena | 29.73 | 24.84 | 37.09 | 36.38 | 41.51 |

| Scenario | Coppia peggiore M | Grammi condivisi M | Denominatore g M | Massimo % M | Media % M | Stato M | Ricerca L | Tempo pool s M |
|---|---|---:|---:|---:|---:|---|---|---:|
| Libera audit | 1–2 | 3080.00 | 5180.00 | 59.46 | 57.14 | ok | sì,sì | 16.36 |
| Sedentaria S1 · sintetica | 1–3 | 6760.00 | 9140.00 | 73.96 | 70.22 | partial | sì,sì | 22.46 |
| Sedentaria S2 · sintetica | 2–3 | 12090.00 | 12645.00 | 95.61 | 84.36 | partial | sì,sì | 22.64 |
| Palestra S1 · sintetica | 2–3 | 10180.00 | 11710.00 | 86.93 | 78.04 | partial | sì,sì | 24.37 |
| Palestra S2 · sintetica | 2–3 | 10645.00 | 11095.00 | 95.94 | 83.03 | partial | sì,sì | 22.24 |

Il rapporto storico `docs/phase8-diversity-audit.md` resta l’unica fonte degli scenari reali sedentaria/palestra. È evidenza storica a budget 5 s/solve e 120 s/generazione, non un risultato ricalcolato qui; non si può ricostruirne la scomposizione dai soli massimi pubblicati. Il risultato libero coincide con quello storico, ma questo non rende rappresentativi gli altri sostituti.

## Dominio effettivo e limiti inferiori

**Un candidato dichiarato non è necessariamente utilizzabile.** `formulate` esclude ogni alimento con uno dei quattro nutrienti vuoto. Mele `007120`: grassi vuoti; uova `181100`: carboidrati disponibili vuoti (I, budget 0, lettura del CSV pubblico). Non sono zeri approvati e non sono stati riempiti. Nei gruppi base restano **un frutto e sei fonti proteiche** utilizzabili (I), anziché due e sette dichiarati. Aggiungere tempo non reinserisce questi alimenti.

### Prova sul dominio libero a porzioni fisse · I/B

La massa non esclusa è esattamente 14 × (50+100+120+100) = **5.180 g**. Tutte le settimane contengono **1.400 g di pera**, quindi quella massa è comune a ogni coppia. Ogni settimana richiede 14 porzioni proteiche e ciascuna fonte compare al massimo tre volte: servono almeno cinque delle sei identità. Un’altra settimana può ometterne al massimo una; nella prima tale fonte pesa al massimo 3×120=360 g. Pertanto almeno **1.680−360=1.320 g** di proteine sono comuni a qualunque coppia. Queste due masse si possono sommare, perché valgono per la stessa coppia: **(1.400+1.320)/5.180 = 52,51%**.

La frutta contribuisce almeno 27,03 pp; le proteine complessivamente almeno 25,48 pp (I/B). Non si divide quest’ultimo minimo tra animali e vegetali senza una prova ulteriore: può cambiare la categoria che lo realizza. Per verdura/amidi non emerge un minimo positivo universale di identità, anche se le loro masse totali sono obbligatorie. «Verdura obbligatoria» non implica «stessa verdura obbligatoria».

Con l’ampliamento i frutti utilizzabili diventano quattro: sparisce il minimo della pera, ma resta quello proteico **1.320/5.180 = 25,48%**. Il pool trovato raggiunge quel valore in tutte le coppie: il limite inferiore e il risultato fattibile chiudono il divario dell’ottimo globale delle tre alternative **per questo solo esperimento a porzioni fisse**, entro la tolleranza numerica. La certificazione globale deriva da questa prova esterna, non dal flag minimax L.

Il limite B16 ≥10,87% riguardava intervalli di porzione standard e non va sostituito numericamente con quello della demo a porzioni fisse: sono domini diversi. La sua conclusione qualitativa sull’insufficienza dei candidati resta coerente.

### Minimi certificati nei sostituti · B

Si massimizza in LP la massa non esclusa e si minimizza in LP la massa di ogni identità obbligatoria. La rilassazione include i vincoli nutrizionali e di frequenza, ma toglie l’integralità: massimi LP sono limiti superiori del MILP, minimi LP sono limiti inferiori. Alla massa obbligatoria si aggiunge solo il contributo proteico che non è già contato, valido per ogni coppia. Non si sommano minimi che valgono soltanto per coppie differenti.

| Scenario | Massa totale ≤ g B | Masse inevitabili I/B | Sovrapposizione ≥ % B | Massimo osservato % M | Divario non spiegato pp M−B |
|---|---:|---|---:|---:|---:|
| Libera audit | 5180.00 | CREA:007260: 1400 g; proteine ≥ 1320 g | 52.51 | 59.46 | 6.95 |
| Sedentaria S1 · sintetica | 17017.43 | CREA:007260: 1400 g + CREA:007510: 2100 g; proteine ≥ 370 g | 22.74 | 73.96 | 51.22 |
| Sedentaria S2 · sintetica | 16919.08 | rice: 280 g + CREA:007260: 1400 g + CREA:007510: 2100 g; proteine ≥ 370 g | 24.53 | 95.61 | 71.08 |
| Palestra S1 · sintetica | 17017.43 | CREA:007260: 1400 g + CREA:007510: 2100 g; proteine ≥ 370 g | 22.74 | 86.93 | 64.19 |
| Palestra S2 · sintetica | 16919.08 | rice: 280 g + CREA:007260: 1400 g + CREA:007510: 2100 g; proteine ≥ 370 g | 24.53 | 95.94 | 71.42 |

Nei sostituti banana ≥2.100 g e pera ≥1.400 g sono comuni a tutte le alternative; nella S2 il riso aggiunge ≥280 g. Il contributo proteico universale è ≥370 g con le porzioni variabili. Questi valori hanno stato I/B, budget LP fino a 5 s per problema. Latticini e ricette hanno contributo zero nel dominio base perché non sono candidati di questi scenari; non perché siano vietati in ogni dieta reale.

Il divario M−B **non misura una quota sicuramente evitabile**: il limite B può essere lasco. Le ricerche L sono invece certificate verso i riferimenti fissati, quindi a quei riferimenti aggiungere tempo non può migliorare oltre la loro fascia certificata. Cambiare i riferimenti cambia la domanda: invertendo solo l’ordine dei candidati, S2 sedentaria scende da 95,61% a 80,31%, mentre la libera sale da 59,46% a 66,02% (M/L, stessi budget). È una prova di sensibilità all’ordine, non la soluzione ottima della terna.

## Esperimenti sui vincoli · M/L

Un solo intervento per riga, rispetto alla baseline dello stesso scenario. Nessuna somma dei benefici fra righe: le interazioni non sono state misurate. Tutti i pool riportati hanno tre alternative e vincoli verificati per il proprio modello sperimentale; una frequenza o una porzione rilassata non è conforme ai vincoli originali. Un aumento del massimo osservato non significa aumento dell’ottimo matematico: il riferimento/tie-break del solver è cambiato.

| Scenario | Intervento | Massimo % M | Variazione pp M | Stato M | Minimax L | Tempo effettivo s M |
|---|---|---:|---:|---|---|---:|
| Libera audit | Ampliare frutti, verdure e amidi | 25.48 | -33.98 | ok | sì,sì | 34.19 |
| Libera audit | Identità più fini per la verdura | 59.46 | +0.00 | ok | sì,sì | 16.56 |
| Libera audit | Frequenza massima 3 → 14 | 43.24 | -16.22 | ok | sì,sì | 13.08 |
| Libera audit | Porzioni sintetiche fisse → intervalli standard | 100.00 | +40.54 | partial | sì,sì | 15.35 |
| Libera audit | Fissare un pranzo della settimana | 93.05 | +33.59 | ok | sì,sì | 14.43 |
| Sedentaria S2 · sintetica | Ampliare frutti, verdure e amidi | 58.51 | -37.10 | partial | sì,sì | 49.23 |
| Sedentaria S2 · sintetica | Identità più fini per la verdura | 96.11 | +0.50 | partial | sì,sì | 25.84 |
| Sedentaria S2 · sintetica | Frequenza massima 3 → 14 | 69.30 | -26.32 | partial | sì,sì | 18.20 |
| Libera audit | Invertire l’ordine dei candidati | 66.02 | +6.56 | ok | sì,sì | 16.72 |
| Sedentaria S2 · sintetica | Invertire l’ordine dei candidati | 80.31 | -15.30 | partial | sì,sì | 22.45 |
| Sedentaria S2 · sintetica | Griglia 5 g → 1 g | 96.32 | +0.71 | partial | sì,sì | 28.86 |
| Sedentaria S2 · sintetica | Rimuovere il solo obbligo di riso a cena | 73.96 | -21.65 | partial | sì,sì | 32.29 |
| Sedentaria S2 · sintetica | Rimuovere i pasti aggiuntivi, stessi target complessivi | 73.98 | -21.63 | partial | sì,sì | 25.62 |
| Sedentaria S1 · sintetica | Ampliare frutti, verdure e amidi | 60.62 | -13.34 | partial | sì,sì | 50.84 |
| Palestra S1 · sintetica | Ampliare frutti, verdure e amidi | 62.03 | -24.90 | partial | sì,sì | 46.13 |
| Palestra S2 · sintetica | Ampliare frutti, verdure e amidi | 63.43 | -32.51 | partial | sì,sì | 38.35 |
| Libera audit | Griglia 5 g → 1 g | 59.46 | +0.00 | ok | sì,sì | 24.65 |
| Libera audit | Aggiungere quattro ricette CREA-only | 77.27 | +17.81 | partial | no,no | 54.85 |

Dettagli metodologici: la griglia da 1 g conserva l’integralità e cambia solo gli step da 5 g; una precedente prova continua non è utilizzabile nei sostituti perché il decoder richiede grammi interi, ed è esclusa dalle tabelle. Nella libera a porzioni fisse cambiare griglia non cambia l’insieme fattibile. Il pranzo bloccato è costruito da un riferimento sintetico, non da un diario. Rimuovere le abitudini elimina colazione/spuntini ma mantiene gli stessi target complessivi: è una sensibilità del modello, non una proposta di saltare pasti. La prova sugli abbinamenti elimina solo il riso obbligatorio a cena nella S2 sintetica.

## Leve, inventario e costo

### Candidati pubblici · I, budget solver 0 s

Il test di ampliamento aggiunge i seguenti candidati, mantenendo la metrica canonica corrente e senza nutriente imputato:

| Gruppo | Dominio dichiarato base → ampliato I | Dominio utilizzabile ampliato I | Aggiunte CREA I |
|---|---:|---:|---|
| Frutta | 2 → 5 | 4 | `007000` albicocche fresche; `007050` fichi freschi; `007330` peschenoci fresche |
| Verdura | 3 → 6 | 6 | `005110` broccolo crudo; `005680` sedano crudo; `005220` cetrioli freschi |
| Amidi | 3 → 6 | 6 | `000020` farro perlato crudo; `000045` couscous crudo; `000090` orzo perlato |

Le verdure aggiunte non hanno tutte identità distinte: sedano/cetrioli confluiscono nel gruppo `vegetable`. La base, però, non collassa tutte le verdure: pomodori `006600` e lattuga `005410` mantengono già ID CREA, soltanto zucchine `005730` usano `vegetable` (I). Questo spiega perché il raffinamento isolato non è la leva principale; con un catalogo ampliato una tassonomia coerente per specie/sottogruppo torna necessaria. Non contare come nuovi ingredienti marca, cultivar o stato crudo/cotto senza una decisione verificata sulle identità.

Per le proteine, con 14 porzioni da 120 g e frequenza massima tre, consentire al massimo il 10% di 5.180 g comuni richiede che una settimana possa evitare almeno quattro fonti dell’altra. Poiché ogni settimana usa almeno cinque fonti, **almeno nove identità proteiche utilizzabili** sono una condizione necessaria (I, prova combinatoria), non sufficiente per la fattibilità delle tre settimane o dei macro. Significa almeno tre fonti aggiuntive rispetto alle sei effettive. Il catalogo contiene, per esempio, `110020` bresaola, `110400` prosciutto cotto e `166000` formaggio grana, già riconosciuti da `family`; sono candidati tecnici da valutare con porzioni/compatibilità appropriate, non raccomandazioni alimentari né tre scelte già autorizzate per le diete. Altre specie/categorie richiedono anche classificazione della fonte principale e frequenze, non solo l’inserimento di un ID.

### Ricette e abitudini · I/M/E

La configurazione pubblica contiene **25 template** (I, conteggio statico), non un certificato del numero complessivo di ricette `ready`. Il controllo senza OFF, usando solo CREA e fonti speciali dichiarate, materializza **quattro** template: pasta al pomodoro demo, `foodose:R315`, `foodose:R054`, `foodose:R270` (I, ricalcolo deterministico, solver 0 s). Questa disponibilità condizionata non può essere attribuita a un profilo reale o al catalogo OFF. I candidati OFF non sono stati aperti né dedotti dai nomi.

Le quattro ricette sono inserite come preferite **nel solo profilo sintetico libero**, sfruttando il percorso già esistente. Il pool raggiunge 77,27%, dunque non migliora la baseline in questa prova (M; minimax non certificato). La composizione viene scomposta e condimenti/acqua esclusi: titoli differenti non producono falsa diversità. La selezione automatica di tutte le ricette pronte non è oggi il comportamento di `prepare`, che usa preferite e piatti bloccati. Costi futuri: compatibilità, porzioni, nutrizione completa e frequenze; effetto sul catalogo intero non misurato.

Le barrette non sono presenti negli input base perché `food_preferences` è vuoto. Il codice offre una barretta solo se esiste un prodotto preferito con etichetta completa; la banana rimane un’alternativa. Non si può quindi misurare una “barretta obbligatoria dell’utente” senza dati personali. Per una confezione realmente fissa di massa b consumata n volte, il contributo inevitabile è n·b/M, dove M è la massa non esclusa (I/E, formula, solver 0 s). Per mantenere il frutto pomeridiano senza imporre la banana, servono almeno tre identità di frutto completo fra le alternative (condizione di supporto I, non sufficienza nutrizionale).

| Leva | Evidenza e effetto | Costo E | Valutazione |
|---|---|---|---|
| Ampliare il dominio effettivo di frutta/verdura/amidi | M: 59,46 → 25,48% libera; 95,61 → 58,51% S2 sedentaria. Non separata l’efficacia dei tre gruppi | Medio: filtri nutrienti/stato, porzioni, compatibilità e frequenze | Prima leva, misurata |
| Più fonti proteiche mantenendo le frequenze | I/E: almeno nove identità necessarie nel modello fisso per sperare nel 10%; effetto finale non misurato | Medio/alto: fonte principale, porzioni e vincoli per dieta | Necessaria per scendere sotto il limite proteico fisso |
| Varianti di colazione/spuntini approvate dall’utente | M: rimozione sperimentale dei pasti aggiuntivi 95,61 → 73,98%; varianti che conservano i pasti non misurate | Medio: dominio e preferenze esplicite, etichette complete | Importante nei sostituti; non eliminare le abitudini in produzione |
| Più riferimenti/ordine di ricerca | M: S2 95,61 → 80,31% a dominio invariato; libera peggiora | Medio: budget moltiplicato per ogni riferimento aggiuntivo, conservazione del migliore pool | Complementare; non basta un seed esposto ma inutilizzato dal modello |
| Identità verdure più fini e coerenti | M: libera 59,46 → 59,46%; S2 95,61 → 96,11%. Effetto combinato col dominio ampliato non misurato | Basso/medio: mappa revisionata e regressioni su marche/stati | Dopo l’ampliamento, senza gonfiare diversità |
| Ricette pronte nella settimana | M: quattro CREA-only 59,46 → 77,27%; catalogo intero non misurato | Medio/alto | Leva di scelta e usabilità; non promessa di 90% |
| Più tempo di calcolo | L: ricerca verso i riferimenti già fissati certificata; non è stata eseguita una curva di budget | Basso in codice, costo operativo crescente | Priorità bassa per i casi certificati; utile dove la certificazione manca |

## Raccomandazione ordinata

1. **Ampliare e controllare il dominio effettivo**, partendo dai frutti completi e dagli amidi/verdure dell’inventario, e rendere visibili le esclusioni per nutriente mancante. Non sostituire vuoto con zero. Il seguente obiettivo è sostenuto da pool verificati del prototipo, non promesso per le diete reali o per Optees.

| Scenario | Base M % | Ampliato M % | Minimo ampliato B % | Obiettivo del prototipo E |
|---|---:|---:|---:|---|
| Libera audit | 59.46 | 25.48 | 25.48 | ≤ 26% osservato con questo dominio/budget |
| Sedentaria S1 · sintetica | 73.96 | 60.62 | 14.42 | ≤ 61% osservato con questo dominio/budget |
| Sedentaria S2 · sintetica | 95.61 | 58.51 | 16.17 | ≤ 59% osservato con questo dominio/budget |
| Palestra S1 · sintetica | 86.93 | 62.03 | 14.42 | ≤ 63% osservato con questo dominio/budget |
| Palestra S2 · sintetica | 95.94 | 63.43 | 16.17 | ≤ 64% osservato con questo dominio/budget |

2. **Aggiungere fonti proteiche e varianti dei pasti abituali**, conservando consenso e vincoli della dieta. Nel dominio ampliato dei sostituti la banana da sola pesa almeno 2.100 g: con la massa massima LP di circa 17.123 g è già oltre il 10% (I/B). Il target 90% non è dunque un obiettivo credibile finché si conserva quel dominio a banana unica. Il risultato delle vere varianti resta E, senza un numero di overlap promesso.

3. **Cercare da più riferimenti e conservare il migliore pool**, invece di investire prima in più secondi sulla stessa terna. Il solo ordine ha mostrato un miglioramento di 15,30 pp nella S2 sintetica e un peggioramento di 6,56 pp nella libera (M). Unire questa leva all’ampliamento potrebbe aiutare, ma l’effetto combinato non è stato misurato e non si somma aritmeticamente. Il vincolo nutrizionale continua a essere verificato per ogni alternativa.

Non si propone di rilassare abbinamenti, frequenze o target reali: gli esperimenti identificano i colli di bottiglia; le leve approvate richiedono nuove schede.

## Riproduzione e limiti

Comandi senza download, con output aggregati soltanto in `/tmp`:

```bash
set -a
. ./.env
set +a
PYTHONPATH=scripts:. "$DIET_PYTHON" scripts/diagnose_variety.py --solve-limit 5 --time-limit 60 --output /tmp/variety-diagnosis.json
PYTHONPATH=scripts:. "$DIET_PYTHON" scripts/diagnose_variety.py --solve-limit 5 --time-limit 60 --variants candidate_expansion --scenarios sedentary:1,training:1,training:2 --output /tmp/variety-extra-expansion.json
PYTHONPATH=scripts:. "$DIET_PYTHON" scripts/diagnose_variety.py --solve-limit 5 --time-limit 60 --baselines-only --bounds-only --output /tmp/variety-bounds.json
```

Lo script genera calendari/regole sintetici in una directory temporanea, ripristina ogni attributo modificato dall’esperimento e verifica la somma delle scomposizioni. Le righe LP indicano stato/tempo di ogni solve nell’output JSON. Le ricette sono controllate con lookup CREA-only, senza database OFF; nessuna configurazione salvata viene alterata.

Le misure sono state raccolte in più esecuzioni, alcune concorrenti con altri esperimenti e con i test. I tempi riportati sono quelli realmente osservati. Il limite per-solve include il tempo HiGHS; conversione del modello, controlli, inventario e più solve fanno superare talvolta il budget nominale di ricerca nel wall time totale. Non attribuire le differenze esclusivamente a un vincolo se cambia il riferimento ottenuto entro il timeout.

### Tutte le coppie delle baseline · M

| Scenario | Coppia | Direzione: massa del piano | Sovrapposizione % |
|---|---|---|---:|
| Libera audit | 1–2 | 1 | 59.46 |
| Libera audit | 1–3 | 3 | 52.51 |
| Libera audit | 2–3 | 3 | 59.46 |
| Sedentaria S1 · sintetica | 1–2 | 2 | 62.73 |
| Sedentaria S1 · sintetica | 1–3 | 3 | 73.96 |
| Sedentaria S1 · sintetica | 2–3 | 3 | 73.96 |
| Sedentaria S2 · sintetica | 1–2 | 2 | 67.66 |
| Sedentaria S2 · sintetica | 1–3 | 3 | 89.82 |
| Sedentaria S2 · sintetica | 2–3 | 2 | 95.61 |
| Palestra S1 · sintetica | 1–2 | 2 | 64.13 |
| Palestra S1 · sintetica | 1–3 | 3 | 83.05 |
| Palestra S1 · sintetica | 2–3 | 2 | 86.93 |
| Palestra S2 · sintetica | 1–2 | 1 | 66.82 |
| Palestra S2 · sintetica | 1–3 | 1 | 86.32 |
| Palestra S2 · sintetica | 2–3 | 2 | 95.94 |

### Verifica del repository

Suite completa: **494 test in 408,693 s, OK** (misura di esecuzione, non budget/certificazione MILP). Test protetti: **25 test in 48,454 s, OK**. `check_task`: **ESITO: pronto per revisione**. Test protetti identici alla Base della scheda; nessuna modifica di produzione e nessun commit. Controllo conclusivo verde; `git diff --check` pulito.
