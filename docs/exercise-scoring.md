# Punteggi di esercizi e sessioni

## Dati disponibili e significato

RepDB fornisce MET numerici e categorie di muscoli, difficoltà e obiettivi; Free Exercise DB offre un confronto indipendente dei metadati. I cataloghi sono scaricati, non ancora integrati nel pianificatore.

Le dimensioni nella trascrizione sono obiettivi di piano: perdita di grasso, mantenimento muscolare, prestazione, nutrizione e aderenza. Non esiste nei file scaricati una scala numerica validata che assegni a ogni esercizio tutti questi risultati. Il MET non è un punteggio di ipertrofia né una previsione personale di dimagrimento.

## Modello iniziale proposto

- Dati di fonte: muscoli, attrezzatura, livello, obiettivi nominali e MET, con provenienza e valori originali.
- Fattibilità: vincolo rispetto ad attrezzatura, variante e limiti configurati. Non un premio che compensa un prerequisito mancante.
- Copertura muscolare: contributi di muscoli primari e secondari mediante coefficienti euristici dichiarati e versionati; non percentuali biologiche misurate. Coefficienti ancora da definire.
- Dose e tempo: serie, ripetizioni, carico, recupero e durata del template. Senza dose non assegnare un risultato quantitativo all'esercizio.
- Energia: stima di sessione condizionata a durata e intensità, verificando il riferimento del MET. Distinguere energia totale e attiva; evitare duplicazione con Apple Watch. Non usare un MET fisso per tutte le varianti/intensità.
- Difficoltà e affaticamento: inizialmente categorie e vincoli di programmazione; eventuali numeri sono ipotesi del modello, non dati del catalogo.
- Preferenza e aderenza: feedback personale, inizialmente ignoto. Risultati delle sessioni eseguite separati dalle aspettative.

Calcolare un vettore di punteggi per template e piano settimanale, normalizzato rispetto a target espliciti. Pareto confronta le dimensioni, Max-Min bilancia i target, Min-Max valuta scenari. Non promettere risposta corporea dal solo punteggio di copertura muscolare.

## Passo successivo

Il comando `python scripts/build_workout_catalog.py` genera `data/personal/workout_catalog.json`, escluso da Git: 609 record, 393 candidati secondo il primo campo attrezzatura e cinque template dimostrativi (full body, cyclette, vogatore, camminata, ellittica). I candidati non sono automaticamente esercizi fattibili: soltanto otto esercizi hanno prerequisiti controllati per i template.

Il modello `workout-draft-v1` assegna, per serie ipotizzata, 1 unità al muscolo primario e 0,5 al secondario. Sono unità euristiche di copertura; niente previsioni di ipertrofia o dimagrimento. Il template full body usa due serie ipotetiche; ripetizioni e carichi restano vuoti. Durate ipotizzate, aderenza e prestazione non apprese. MET conservati senza conversione automatica in calorie. Aqua bag/tank restano estensioni da modellare.

Selezionare gli esercizi compatibili, conservando prerequisiti multipli (panca, barra, supporti) che un singolo campo equipment può omettere. Aggiungere varianti australiane con barra regolabile confermata e attrezzi ad acqua. Costruire pochi template di sessione, poi definire coefficienti e scenari con esempi riproducibili prima della chiamata Optees.

## Aggiornamento v2

Il modello sopra descrive il prototipo iniziale. Ora il catalogo genera 11 bozze di sessione complete, da otto protocolli, con tempi comprensivi di lavoro e recuperi e dieci prerequisiti di esercizi controllati. Dettagli, provenienza e limiti: [Protocolli e sessioni](workout-protocols.md).
