# Optees diet case of study

Applicazione personale indipendente: Optees viene usato come motore di ottimizzazione, senza modificare il suo core.

## Obiettivo

Importare dati esistenti di alimenti, ricette e attività; registrare piano scelto e osservazioni; generare alternative tramite ottimizzazione vincolata, Pareto e robustezza Min-Max; aggiungere una politica bandit per esplorare poche strategie del piano.

Il budget iniziale di 10 ore è stato ampliato, senza fissare ancora un nuovo limite. L'interfaccia resta essenziale; il focus è orchestrazione e analisi dati.

## Stato

- Repository locale inizializzato; nessun remote configurato.
- Importatore CREA da schede ufficiali, con cache e provenienza.
- Pianificatori MILP via Optees e interfaccia locale con profili separati.
- Cataloghi di prodotti italiani e ricette dal mondo consultabili offline.
- Pareto e bandit non ancora implementati.

## Importazione CREA

```bash
python -m pip install -r requirements.txt
python scripts/import_crea.py
```

La cache evita di riscaricare le schede già ottenute. `--limit 5` importa un campione; `--offline` rigenera gli output dalla cache. L'importazione restituisce un errore se alcune schede richieste non sono importabili. I macro simbolici o mancanti sono segnalati nel manifest e richiedono una politica esplicita prima dell'ottimizzazione.

Output e attribuzione: [dataset/crea/README.md](dataset/crea/README.md).
Architettura prevista: [docs/design.md](docs/design.md).
Roadmap, interfaccia e fasi di sviluppo: [docs/roadmap.md](docs/roadmap.md).
Primo pianificatore settimanale via MCP: [docs/weekly-planner.md](docs/weekly-planner.md).

## Interfaccia locale

Copiare `.env.example` in `.env` e indicare il Python con le dipendenze (`DIET_PYTHON`);
`optees-mcp` viene cercato accanto a quell'interprete, oppure si imposta `OPTEES_COMMAND`.
Avviare `./scripts/start_web.sh` e aprire http://127.0.0.1:8765.
Per la rete domestica: `DIET_WEB_HOST=0.0.0.0 ./scripts/start_web.sh`.
Credenziali iniziali Paolo in `data/personal/web_access.txt`, escluso da Git.
I nuovi profili partono senza dati personali di Paolo. Dettagli e limiti in
[docs/web-interface.md](docs/web-interface.md).

## Prodotti di marca

Catalogo italiano Open Food Facts separato da CREA, importabile con
`python scripts/import_open_food_facts.py` e indicizzabile con
`python scripts/build_branded_catalog.py`. Ricerca offline:
`python scripts/build_branded_catalog.py --search 'La Molisana'`.
Fonte, licenza e controlli qualità in [dataset/open_food_facts/README.md](dataset/open_food_facts/README.md).

## Ricette dal mondo

Importare con `python scripts/import_recipes.py --download`; rigenerare dagli originali locali omettendo `--download`. La pagina Ricette permette ricerca e filtro della cucina; nel profilo si salvano le cucine preferite. Fonti, licenze e stato del ricalcolo nutrienti in [dataset/recipes/README.md](dataset/recipes/README.md). Le ricette non sono ancora integrate nel solver.

Il [solver delle ricette](docs/recipe-solver.md) sceglie prodotti e quantità con proporzioni flessibili; attualmente 25 composizioni con mapping esplicito, senza integrazione automatica nei piani delle diete.

Il [controllo degli abbinamenti delle ricette](docs/recipe-diet-compatibility.md) valuta ingredienti, rami e complementi mancanti per i 14 giorni di ogni programma. La verifica nutrizionale e l’inserimento automatico nel piano giornaliero restano separati.
