# Optees Diet Case of Study · Diet Lab

[English](README.md) · **Italiano**

Applicazione personale per la pianificazione e il diario nutrizionale e motorio, basata sul motore di ottimizzazione matematica **Optees** (solver MILP richiamato via protocollo MCP).

## Dove stanno i dati personali (fuori da Git)
Per tutelare la riservatezza medica e personale, i dati sensibili sono esclusi dal tracciamento Git tramite [`.gitignore`](.gitignore):
- `data/personal/`: database SQLite locale `web.sqlite`, note personali e credenziali generate con permessi protetti `0600` da [`web/app.py:initialize`](web/app.py); configurazione attrezzatura personale da [`scripts/workout_configuration.py:seed_legacy_equipment`](scripts/workout_configuration.py). I profili dimostrativi usano default neutri generati da [`web/app.py:defaults`](web/app.py).
- `sanitary_data_export/`: archivio con l'esportazione grezza di Apple Salute (`export.zip`).
- `private_docs/`: documenti personali riservati.
- `.env` e `*.sqlite*`: variabili d'ambiente locali di macchina e copie del database.

## Avvio dell'applicazione
1. Configurare `.env` partendo da `.env.example` indicando l'interprete Python (`DIET_PYTHON`).
2. Avviare il server web locale su `http://127.0.0.1:8765`:
```bash
./scripts/start_web.sh
```
Per avviare su un database temporaneo isolato: `DIET_WEB_DB=/tmp/demo/web.sqlite ./scripts/start_web.sh`.

## Le schermate dell'applicazione

### Oggi
Cruscotto giornaliero servito da [`web/app.py:read_day`](web/app.py) tramite [`scripts/diary_service.py:day_view`](scripts/diary_service.py). Gestisce esattamente i cinque pasti della giornata (colazione, metà mattina, pranzo, metà pomeriggio e cena; non c'è spuntino serale) e l'attività sportiva. Ogni pasto si conferma con un tocco o si modifica (grammi, alimenti aggiunti, tolti o sostituiti). «Fuori programma» registra un pasto libero come intervallo di calorie, e «Rientro della settimana» somma tutti gli scostamenti registrati e propone come rientrare nei giorni seguenti, cambiando il meno possibile e senza scendere sotto i minimi protetti ([`scripts/meal_rebalance.py:preview`](scripts/meal_rebalance.py), [`scripts/meal_rebalance.py:decide`](scripts/meal_rebalance.py)). «Com'è andata?» raccoglie un voto da 1 a 5 sul piano applicato.
![Oggi](docs/screenshots/02_oggi.png)

### Piano
Genera la settimana congiunta dieta + palestra differenziando i target tra riposo e allenamento ([`scripts/joint_orchestration.py:generate_week`](scripts/joint_orchestration.py)) e applica il piano scelto ([`scripts/joint_orchestration.py:apply_week`](scripts/joint_orchestration.py)). Mostra le alternative non dominate (compromessi di Pareto) e il piano più robusto calcolato minimizzando il rimpianto peggiore sugli scenari di dispendio ([`scripts/joint_robustness.py:annotate_pool`](scripts/joint_robustness.py)).
![Piano](docs/screenshots/03_piano.png)

### Allenamento
Catalogo delle 11 sessioni standard ([`scripts/workout_service.py:catalog`](scripts/workout_service.py)) dai protocolli in `config/workout-protocols.json`, corredate da immagini di postura da Free Exercise DB, video didattici YouTube e registro serie con carichi, ripetizioni, RPE e timer di recupero.
![Allenamento](docs/screenshots/04_allenamento.png)

### Ricette
Ricettario internazionale in `dataset/recipes/`, con nutrienti calcolati su tabelle ufficiali CREA e immagini libere. Include il Recipe Solver ([`scripts/plan_recipe.py:optimize_recipe`](scripts/plan_recipe.py)) che calcola le grammature ottimali rispettando i vincoli nutrizionali e le proporzioni culinarie.
![Ricette](docs/screenshots/05_ricette.png)

### Progressi
Misurazioni e andamento del peso depurato dalle fluttuazioni tramite filtro di Kalman scalare sulle mediane giornaliere (con serie EMA opzionale a 7 giorni), come descritto in [`docs/backend-handoff-progress.md`](docs/backend-handoff-progress.md) e calcolato in [`scripts/progress_analysis.py:progress`](scripts/progress_analysis.py). Include il check-in settimanale del lunedì ([`web/app.py:monday_check_in`](web/app.py)) che analizza le ultime due settimane di dati e propone eventuali ricalibrazioni protette dei consumi ([`scripts/progress_recalibration.py:make_proposal`](scripts/progress_recalibration.py)).
![Progressi](docs/screenshots/06_progressi.png)

### Profilo
Gestione dei target nutrizionali e configurazione delle abitudini relative ai cinque pasti giornalieri ([`scripts/daily_meals.py:defaults`](scripts/daily_meals.py), [`scripts/daily_meals.py:validate`](scripts/daily_meals.py)).
![Profilo](docs/screenshots/07_profilo.png)

## La catena di ottimizzazione in parole semplici
1. **Pasto e ricette (MILP a passi di 5g)**: ogni porzione è discreta e pesabile ([`scripts/plan_diet_day.py:formulate`](scripts/plan_diet_day.py)); il Recipe Solver porziona gli ingredienti salvaguardando le proporzioni culinarie ([`scripts/plan_recipe.py:optimize_recipe`](scripts/plan_recipe.py)).
2. **Giornata coordinata**: i pasti principali si armonizzano con colazione e spuntini evitando combinazioni monotone delle fonti proteiche.
3. **Settimana congiunta (Dieta + Allenamento)**: [`scripts/joint_orchestration.py:generate_week`](scripts/joint_orchestration.py) unisce la programmazione degli allenamenti a fabbisogni calorici differenziati per giorni di allenamento e riposo.
4. **Frontiera di Pareto e Robustezza**: Optees genera alternative ottimali (migliore, varia, preferita) e valuta la stabilità rispetto ai consumi reali rilevati da Apple Salute ([`scripts/joint_robustness.py:annotate_pool`](scripts/joint_robustness.py)).
5. **Adattamento continuo**: preferenze apprese con bandit UCB1, rientro non punitivo dagli sgarri e ricalibrazione controllata al check-in settimanale.

## Importazione di Apple Salute e Withings
- L'archivio esportato dall'iPhone va messo in `sanitary_data_export/`: deve esserci un solo file `.zip`.
- L'importazione atomica su database SQLite locale è gestita da [`scripts/apple_health.py:import_zip`](scripts/apple_health.py).
- I dati biometrici (peso, grasso corporeo, dispendio a riposo e attivo) vengono usati solo con copertura sufficiente: giornate coperte per almeno 20 ore su 24 ([`scripts/apple_health.py:summarize`](scripts/apple_health.py)), almeno 7 giornate utili su 28 e dati non più vecchi di 14 giorni ([`scripts/health_inputs.py:refresh_report`](scripts/health_inputs.py)).
- Per la procedura passo per passo, consultare la [Guida all'aggiornamento Apple Salute / Withings (`docs/apple-health-import.md`)](docs/apple-health-import.md).

## Lingue
L'interfaccia è predisposta per **italiano** (predefinito) e **inglese**: i testi stanno in file di traduzione (`web/static/locales/`) invece che nel codice, e la lingua si sceglie dal menu dell'avatar. I nomi degli alimenti delle tabelle CREA restano in italiano, come nei dati di origine. Le schermate qui sopra mostrano l'interfaccia italiana.

## Dati di terzi e licenze

Il codice e la documentazione del progetto sono sotto licenza MIT (`LICENSE`). I dati di terzi mantengono le proprie condizioni:

- **CREA, tabelle di composizione degli alimenti** — nessuna licenza aperta identificata: le tabelle derivate (`dataset/crea/foods.csv`, `foods.json`) **non sono incluse**. Si rigenerano in locale con `scripts/import_crea.py` a partire dalle schede pubbliche del sito CREA (vedi `dataset/crea/README.md`), citando la fonte. Senza queste tabelle il solver e la suite di test non sono utilizzabili.
- **foodose** — CC BY 4.0, attribuzione in `dataset/recipes/README.md`.
- **UniTools recipes** — CC BY-SA 4.0 (`dataset/recipes/unitools/LICENSE`): i dati derivati restano CC BY-SA 4.0.
- **Free Exercise DB** — Unlicense (`dataset/free_exercise_db/LICENSE.md`); immagini degli esercizi in `web/static/media`.
- **RepDB** — uso con attribuzione; redistribuzione come dataset vietata: i file originali non sono inclusi.
- **Open Food Facts** — ODbL; i dati scaricati non sono inclusi, solo manifest e documentazione.
- **USDA FoodData Central SR Legacy** — pubblico dominio; l'archivio non è incluso.
- **Immagini illustrative delle ricette** — Wikimedia Commons, autore e licenza per immagine in `config/recipe-images.json`.

Il progetto è un caso di studio personale: non è un dispositivo medico e non fornisce consigli clinici.
