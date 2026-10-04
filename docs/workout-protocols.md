# Protocolli e sessioni complete — modello v2

`config/workout-protocols.json` contiene otto protocolli: forza, massa e resistenza muscolare a serie, circuito, EMOM, isometria, cardio continuo e HIIT. Sono distinte finalità, formato e intensità. Un formato non è una misura universale di efficacia. Le compatibilità sono etichette del modello, non una classifica sanitaria.

Fonti consultate il 4 ottobre 2026:

- [ACSM Resistance Training Position Stand 2026](https://pmc.ncbi.nlm.nih.gov/articles/PMC12965823/): principi generali su carico, volume e obiettivi. Non prescrive i parametri esatti dei nostri esempi.
- [ACSM HIIT](https://acsm.org/high-intensity-interval-training-fitness/): distingue lavoro intenso e recupero e descrive la variabilità dei protocolli. Non valida i nostri intervalli demo.

Serie, ripetizioni, tempi, RIR/RPE e transizioni sono **ipotesi locali dimostrative**, dichiarate come `local_demo_assumptions`. Per circuito, EMOM, isometria e cardio continuo non è attribuita una fonte a una dose specifica non verificata. Non è stato scaricato un ulteriore catalogo di esercizi: questa estensione aggiunge struttura e provenienza ai dati già disponibili.

## Compilazione

`python scripts/build_workout_catalog.py` genera il catalogo privato, con 11 schede complete quando l'attrezzatura necessaria è presente. Gli esercizi non fattibili escludono la relativa scheda; non vengono sostituiti senza controllo. Due nuovi prerequisiti sono modellati: floor press e deadlift con manubri, senza assumere una panca o un rack. La verifica di attrezzatura non verifica la capacità personale di eseguire l'esercizio.

Ogni sessione contiene esercizi, dose, intensità, parametri, obiettivi compatibili, fonti, configurazioni personali mancanti e cronologia dettagliata:

- riscaldamento e preparazione;
- lavoro dinamico, tenute o intervalli;
- recuperi fra serie, recuperi attivi, cambi di stazione e pausa fra giri;
- defaticamento;
- durata totale e ripartizione delle componenti.

I recuperi fra serie non vengono aggiunti dopo l'ultima serie. Negli EMOM il tempo di ogni slot è lavoro + cambio + recupero: la compilazione rifiuta le dosi che non lasciano il recupero minimo previsto. Il recupero dell'ultimo slot fa parte del blocco a tempo. Nei circuiti i cambi e le pause fra giri sono eventi distinti, senza sovrapposizioni. Gli intervalli includono esplicitamente il recupero finale. Le ripetizioni hanno una durata di esecuzione **stimata**, non misurata: i tempi reali possono differire. Riscaldamento, preparazione e defaticamento hanno una durata nel modello, ma le loro attività dettagliate richiedono configurazione personale.

RIR indica ripetizioni in riserva; RPE usa qui una scala dello sforzo 0–10. Non sono intercambiabili. Carichi in kg, velocità, inclinazione e frequenze cardiache non vengono inventati. La scheda forza segnala il carico da configurare; una bassa ripetizione nominale non certifica uno stimolo di forza. La compatibilità “massa” non verifica da sola intensità, volume settimanale o progressione.

## Solver settimanale

`python scripts/plan_workout_week.py --output data/personal/workout_sessions_week_v2.json` usa la durata totale delle nuove sessioni per i vincoli di tempo. I minuti cardio conteggiati sono soltanto il lavoro cardio, senza riscaldamento, pause o defaticamento. Gli esercizi isometrici e i circuiti possono essere sedute muscolari anche senza un punteggio di serie dinamiche.

Filtri opzionali: `goal`, `allowed_protocols`, `allow_high_intensity_demo`. HIIT è escluso di default. La configurazione demo permette di esplorare bozze; una configurazione non demo esclude le sessioni con configurazioni personali mancanti. Non si trasforma una bozza in prescrizione perché è fattibile matematicamente.

La copertura muscolare rimane euristica (primario 1, secondario 0,5 per serie). Circuiti temporizzati e isometrie non inventano equivalenze con le serie di ipertrofia. MET, calorie, prestazione e aderenza non vengono tradotti in risultati corporei. Il solver settimanale mantiene i suoi criteri tempo/copertura; Pareto e bandit nutrizionali non sono automaticamente estesi agli allenamenti.

## Da completare

Configurazione del livello, varianti eseguibili, carichi, intensità, progressione e calendario personale; attività dettagliate di riscaldamento; aqua bag/tank; interfaccia palestra e registro di esecuzione. La prima versione non richiede altri migliaia di esercizi, ma una selezione verificata e feedback reale.
