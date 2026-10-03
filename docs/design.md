# Orchestrazione prevista

1. Dataset importati e normalizzati con provenienza; estensioni personali separate.
2. Stato personale: diario, misurazioni, attività, aderenza, preferenze e tempo disponibile.
3. Generazione di piani fattibili tramite un adapter al contratto reale di Optees, da verificare nel repository.
4. Frontiera Pareto su obiettivi espliciti (scostamento dai target, praticità, varietà, tempo). Normalizzazione e direzione degli obiettivi documentate.
5. Valutazione Min-Max dei candidati su scenari di incertezza espliciti. Verificare quale formulazione sia supportata da Optees; non assumere che un solver di giochi a matrice implementi automaticamente ogni modello robusto.
6. Bandit su un piccolo insieme di strategie: inizialmente policy semplice con conteggi, reward e incertezza. Nessuna esplorazione fuori dai vincoli fissati.
7. Scelta umana, salvataggio di alternative e versione del modello, osservazione dell'esecuzione reale, aggiornamento.

Pareto, Min-Max e bandit sono requisiti centrali del caso di studio. L'interfaccia è secondaria.

Una preferenza espressa scegliendo un piano non è un risultato fisiologico. Il feedback riguarda soltanto il piano eseguito; non attribuire reward osservati ai piani non provati. Variazioni settimanali, ritardi e cambiamenti di contesto limitano le ipotesi di un bandit standard. Analizzare dapprima trend e aderenza, senza inferire causalità dei singoli alimenti o composizione corporea dal solo peso.

## Passi successivi

- Controllare qualità e copertura dei dati CREA.
- Scegliere dataset di ricette con quantità e mapping utilizzabili e catalogo di attività.
- Verificare API/contratti di Optees e implementare un caso piccolo riproducibile.
- Integrare generazione alternative, Pareto e scenari Min-Max.
- Simulare la policy bandit prima di usare feedback personali.
- Aggiungere diario e revisione settimanale essenziali.
