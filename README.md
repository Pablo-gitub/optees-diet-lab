# Optees diet case of study

Applicazione personale indipendente: Optees viene usato come motore di ottimizzazione, senza modificare il suo core.

## Obiettivo

Importare dati esistenti di alimenti, ricette e attività; registrare piano scelto e osservazioni; generare alternative tramite ottimizzazione vincolata, Pareto e robustezza Min-Max; aggiungere una politica bandit per esplorare poche strategie del piano.

Il budget iniziale di 10 ore è stato ampliato, senza fissare ancora un nuovo limite. L'interfaccia resta essenziale; il focus è orchestrazione e analisi dati.

## Stato

- Repository locale inizializzato; nessun remote configurato.
- Importatore CREA da schede ufficiali, con cache e provenienza.
- Solver, modello personale, Pareto e bandit non ancora implementati.

## Importazione CREA

```bash
python -m pip install -r requirements.txt
python scripts/import_crea.py
```

La cache evita di riscaricare le schede già ottenute. `--limit 5` importa un campione; `--offline` rigenera gli output dalla cache. L'importazione restituisce un errore se alcune schede richieste non sono importabili. I macro simbolici o mancanti sono segnalati nel manifest e richiedono una politica esplicita prima dell'ottimizzazione.

Output e attribuzione: [dataset/crea/README.md](dataset/crea/README.md).
Architettura prevista: [docs/design.md](docs/design.md).
