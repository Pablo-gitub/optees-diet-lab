# T-008 · Tracce CREA («tr») trattate come zero dichiarato, così mele, uova e altri alimenti tornano utilizzabili

**Per Codex.** Autore della scheda: Claude · Data: 2026-10-12 · Tappa del piano: 3
Esecutore: Codex (import dei dati e loro provenienza) · Revisore: Claude

## Obiettivo

Gli alimenti CREA con un nutriente indicato come **tracce** nella pagina sorgente non vengono più esclusi dal solver: il valore diventa 0 con provenienza esplicita «tracce (tr) nel CREA». I valori **davvero mancanti** restano vuoti ed esclusi.

## Contesto

- Diagnosi T-007 (`docs/variety-diagnosis.md`): mele `007120` (grassi vuoti) e uova `181100` (carboidrati disponibili vuoti) sono tra i candidati ma `formulate` le scarta; nei gruppi base restano 1 frutto e 6 proteine invece di 2 e 7.
- Rilevato in precedenza: in circa 55 alimenti CREA il valore `tr` della pagina grezza diventa vuoto (27 grassi, 21 carboidrati); 14 proteine non lette dal parser.
- `scripts/import_crea.py` legge le tabelle HTML; `dataset/crea/foods.csv` è il risultato.

## Contratto

1. Nel risultato dell'import un nutriente `tr` vale **0** e la riga dichiara quali nutrienti sono tracce (colonna o file di provenienza; scegliere la forma meno invasiva e documentarla).
2. Un valore assente (cella vuota o «n.d.» nella sorgente) resta vuoto: nessuno zero inventato.
3. Le 14 proteine non lette: correggere la lettura se è un difetto del parser; altrimenti elencarle come assenti con il motivo.
4. Il solver e le altre funzioni che leggono `foods.csv` non cambiano logica: l'effetto è solo sul dominio utilizzabile.
5. Un breve rapporto prima/dopo: quanti alimenti tornano utilizzabili per gruppo (frutta, verdura, amidi, proteine, latticini), elenco di quelli dei gruppi candidati.

## Criteri di accettazione

- [ ] Test: una pagina CREA sintetica con `tr`, un valore numerico e una cella mancante → 0 con provenienza «tracce», numero, vuoto.
- [ ] Mele `007120` e uova `181100` utilizzabili dal solver; nessun alimento con valore realmente mancante diventato 0.
- [ ] Rapporto prima/dopo in `docs/crea-traces.md`.
- [ ] Nessun download nuovo senza approvazione: usare le pagine già scaricate; se servono pagine mancanti, fermarsi e chiedere.
- [ ] Suite completa verde.

## Base

```
6894e823f3cf807c648aab6321fe7f2e9a850dd8
```

## File consentiti

```
scripts/import_crea.py
dataset/crea/foods.csv
dataset/crea/*
docs/crea-traces.md
tests/test_import_crea.py
```

## Test protetti

```
tests/test_ingredient_overlap.py
tests/test_diet_day.py
```

## Test aggiuntivi consentiti

```
tests/test_import_crea.py
```

## Comando di test

```
set -a; . ./.env; set +a; PYTHONPATH=scripts:tests:.:/tmp/optees-crea-pure ${DIET_PYTHON:-python} -m unittest test_import_crea test_ingredient_overlap test_diet_day -q
```

## Resoconto

- File modificati T-008: `scripts/import_crea.py`, `dataset/crea/foods.csv`, `dataset/crea/foods.json`, `dataset/crea/manifest.json`, `tests/test_import_crea.py`, `docs/crea-traces.md`, questa scheda. Nessun commit T-008; le modifiche T-009 sono descritte sulla propria scheda.
- Test aggiunti: cinque in `tests/test_import_crea.py`; prima della correzione i tre iniziali fallivano con assertion su `tr` convertito in `None`, dopo la correzione tutti e cinque verdi.
- Import: 832/832 pagine alimentari già presenti, tre pagine di contesto; nessun download. 777 → 832 vettori essenziali completi, 55 alimenti recuperati, 62 celle essenziali da traccia a zero. SHA delle pagine grezze invariati. Tutte le 14 proteine erano `tr`, con etichetta già corretta.
- Decisioni prese: colonna `trace_nutrients` nel CSV e provenienza sulle sole righe di traccia nel JSON. Controllo preliminare della cache e interruzione prima degli output in caso di errore di parsing, per evitare dataset parziali. Nessuna modifica al solver.
- Ambiente: `bs4` e `soupsieve` già installati nell'interprete locale di base, esposti temporaneamente al Python del progetto tramite `/tmp/optees-crea-pure`; nessuna libreria installata. Il comando della scheda include questo percorso. La suite HTTP si blocca nell'event loop del TestClient sotto sandbox; il rilancio fuori sandbox supera i test HTTP. Letture automatiche della sola suite già autorizzate dal proprietario.
- Test protetti: 17 test (9 ingredient overlap, 8 diet day), file identici alla Base; esecuzione non completata nel budget. Nessuna assertion indebolita, nessun test disabilitato.
- Suite completa: non completata. Rilancio fuori sandbox: 58 test conclusi verdi; dopo circa 13,5 minuti ancora in `DailyMealsTests.test_daily_targets_do_not_reuse_main_meal_targets`. Interrotto quando il controllo protetto ha esaurito il proprio budget. Nessuna assertion fallita osservata, ma nessuna attestazione di suite verde. Senza test rossi T-009 nella scoperta di questa fase. Il loro file nuovo non ancora committato era stato temporaneamente tenuto fuori da `tests`, poi ripristinato e committato separatamente; nessun test esistente/protetto spostato o disabilitato.
- check_task: `ESITO: non pronto (1 problemi)`, unico problema `Comando di test fallito (codice -15)` dopo interruzione esplicita del processo, ancora in calcolo dopo 20 minuti (rilevazione a 20:19). Avviato sulla sola working tree T-008 prima della fase T-009: nessuna violazione di perimetro o modifica dei protetti rilevata in quel controllo.
- Dubbi o blocchi: forte aumento dei tempi degli adattatori SciPy dei test, che non impongono un limite alla singola soluzione. Budget di osservazione dichiarato 20 minuti per esecuzione; controllo interrotto al suo esaurimento, suite generale interrotta anticipatamente per lo stesso blocco. Il confronto storico T-007 è indicativo (25 test in 48,454 s), non una misura isolata sul medesimo modello. Non è certificata una causa numerica precisa, né infeasibilità. La scheda impone «Il solver e le altre funzioni che leggono foods.csv non cambiano logica»: nessuna modifica ai solver o ai test esistenti per aggirare il problema. Occorre una diagnosi dei tempi in una scheda con perimetro appropriato prima di soddisfare suite verde/check pronto.
Stato: non pronto, verifica della suite bloccata dai tempi di soluzione.

## Revisione

### Verifica protocollo e criterio di arresto · Codex, 12 ottobre 2026

Su richiesta del proprietario, verificato prima di ogni modifica al solver se il protocollo accetti un gap assoluto. L'autorizzazione estende il precedente perimetro al solver e agli adattatori dei test soltanto se il criterio è supportato; in caso contrario il proprietario chiede di fermarsi e proporre alternative. Nessun file di produzione o adattatore è stato modificato in questa verifica, nessun commit.

**Esito: tolleranza assoluta non supportata dal protocollo installato.** `optees_get_capability` per `milp.linear`, contratto 1, espone soltanto `solver.time_limit` e `solver.mip_gap`. I backend dichiarati sono `ortools.cbc` e `ortools.cp_sat`: HiGHS è usato dagli adattatori SciPy dei test, non da questa capability di produzione.

Verifica sul codice effettivamente importato dal Python del progetto (percorsi ottenuti con `inspect.getfile`):

- `/home/paolo/Projects/optees/src/optees/utility/milp_json_io.py`, `_parse_solver_options`: legge soltanto tempo massimo e gap relativo. Il modello MILP e il caso d'uso trasportano soltanto queste due opzioni.
- Prova riproducibile di sola conversione su un problema binario sintetico di una variabile: input `solver={time_limit:15, mip_gap:0.001, mip_abs_gap:0.001}`; dopo il codec e la serializzazione restano soltanto `{time_limit:15.0, mip_gap:0.001}`. Il modello non ha un attributo `mip_abs_gap`. Non è stata avviata un'ottimizzazione per questa prova. L'accettazione di una proprietà JSON sconosciuta non ne dimostra il supporto: qui viene ignorata.
- `/home/paolo/Projects/optees/src/optees/utility/milp_utils.py`: CP-SAT imposta `relative_gap_limit`; CBC imposta il tempo massimo ma non applica il `mip_gap` ricevuto (lo riporta soltanto nei diagnostics). Nessun arresto per gap assoluto trovato nei due percorsi. Aggiungere il campo nella sola app non risolverebbe il problema.

**Classificazione attuale al limite di tempo:** il backend restituisce `Feasible` quando ha un incumbent senza prova di ottimo, `NotSolved` quando non ha una soluzione utilizzabile. `milp_result_codec.py` li serializza rispettivamente come `feasible` e `not_solved`, con avviso di ottimo globale non provato nel primo caso. `milp_solver_adapter.py` aggiunge `termination_reason=time_limit` per questi stati se il tempo misurato è almeno il 90% del limite: è una rilevazione euristica, non un codice esplicito del backend. La validazione dei vincoli è indipendente dallo stato matematico. `scripts/plan_diet_day.py:solve_problem` inoltra il risultato MCP; la decodifica mantiene lo stato. `optimize_day` verifica le soluzioni utilizzabili e mantiene `feasible` anche nel ripiego sulla sola ottimizzazione delle preferenze.

L'adattatore `tests/test_recipe_solver.py:solve` attualmente non passa opzioni temporali e traduce ogni `result.success=False` in `infeasible`: aggiungere soltanto un tempo massimo lo farebbe classificare erroneamente anche un incumbent fermato al limite. Da allineare dopo la scelta del criterio, mantenendo tutte le verifiche dei vincoli. Gli altri punti SciPy individuati sono `tests/test_diet_day.py`, `tests/test_recipe_intents.py` e la patch in `tests/test_joint_api.py`; le opzioni attuali non sono uniformi.

**Alternative proposte, senza implementazione:**

1. Preferibile: estendere Optees con un gap assoluto esplicito lungo schema, codec, modello e backend, verificando che sia davvero applicato dal backend scelto. Successivamente app e SciPy possono condividere 15 s e gap assoluto `1e-3`. La soglia significa distanza massima fra incumbent e bound nell'unità dell'obiettivo; non è una tolleranza di calorie, grammi o rispetto dei vincoli, e non certifica ottimalità esatta. L'estensione richiede un compito nel repository Optees.
2. Usare il limite di tempo già supportato e accettare soltanto risultati fattibili verificati, mantenendo stato `feasible`, avviso e gap/bound disponibili. Questo impedisce solve illimitati ma non certifica la distanza assoluta dall'ottimo; non consente di mantenere indiscriminatamente le aspettative di stato `optimal` dei test.
3. Per i soli obiettivi con un lower bound analitico dimostrato (per esempio zero per una somma di costi non negativi), esprimere un problema di fattibilità con vincolo `obiettivo <= lower_bound + 1e-3`. Una soluzione verificata certifica la distanza assoluta richiesta senza un parametro nativo di gap. Serve un disegno esplicito per le fasi lessicografiche, la classificazione dei risultati e gli obiettivi privi di quel bound; non va introdotto come trasformazione generica implicita.

Alzare soltanto il gap relativo non è equivalente a un gap assoluto vicino a zero e non risolve in modo affidabile la diagnosi riportata. Un offset dell'obiettivo non è un ripiego affidabile: il percorso CBC aggiunge l'offset al risultato dopo il solve, senza inserirlo nell'espressione ottimizzata.

Non eseguita nuovamente la suite illimitata: nessuna modifica al criterio di arresto, e i test T-009 restano intenzionalmente rossi e indipendenti. Non dichiarati suite verde o check pronto. La diagnosi di Claude (103 → 115 variabili, circa 0,7 s → oltre 300 s, gap 1.0 ai limiti di 5/30 s) è qui riportata come misura fornita dal revisore, non come nuova misura ripetuta da Codex.

Stato: fermo alla condizione richiesta dal proprietario; scegliere l'alternativa prima di modificare produzione o adattatori.

### Misure con Optees reale · Codex, 12 ottobre 2026

Richiesta del proprietario: misura prima di qualsiasi modifica, con i dati T-008 nella working tree. Nessun codice di produzione, test o adattatore modificato; nessun commit. Aggiunto soltanto il payload richiesto in `docs/t008-daily-targets-optees-problem.json` e questo resoconto. Le modifiche preesistenti T-008/T-009 restano invariate.

**Percorso effettivo:** Python del progetto indicato da `.env`, `optees_command()` → `/home/paolo/anaconda3/envs/optees/bin/optees-mcp`, client MCP stdio inizializzato, `plan_diet_day.solve_problem(session, problem)` senza patch, validazione e creazione del job come in produzione. Una sessione condivisa, quattro richieste sequenziali, una misurazione per problema. Ogni formulazione contiene esattamente `solver={time_limit:15}`; nessun gap, offset o altro criterio aggiunto. Il tentativo sotto sandbox non ha restituito misure nell'avvio MCP; è stato interrotto e il suo server chiuso. Le misure riportate provengono dal rilancio fuori sandbox.

**Primo problema:** `DailyMealsTests.setUp()`, quindi la stessa assegnazione del test `main_meals_targets.kcal_100g={min:9000,target:9000,max:9000}`, infine `plan_diet_day.formulate(config, foods)`. Modalità libera, preferiti esclusivamente sintetici dalla fixture pubblica (barretta 35 g e crackers 32 g), catalogo CREA pubblico T-008. Nessun file sotto `data/personal`, `.sqlite` reale o esportazione sanitaria letto. Il prefisso `personal:` delle variabili identifica i prodotti sintetici della fixture, non informazioni del proprietario.

Il payload salvato è l'oggetto MILP trasmesso da `solve_problem` (chiavi `version`, `variables`, `constraints`, `objective`, `solver`), non un wrapper MCP: per una sessione Optees usarlo come `problem` con `capability_id=milp.linear`, validandolo prima di creare il job. Contiene 115 variabili e 140 vincoli. È la singola formulazione iniziale, **prima** delle successive fasi lessicografiche di `optimize_day`; non è una misura dell'intero metodo di test.

| Problema della suite / formulazione iniziale | Variabili / vincoli | Backend | Tempo end-to-end (s) | Tempo backend (s) | Stato | Obiettivo | Bound | Arresto |
|---|---:|---|---:|---:|---|---:|---:|---|
| daily_meals · daily_targets_do_not_reuse_main_meal_targets | 115 / 140 | CBC | 16.418387 | 16.218 | `feasible` | 2.12765957446615e-05 | 0 | `time_limit` |
| diet_day · free_mode_and_invalid_targets | 102 / 124 | CBC | 17.677051 | 17.379 | `feasible` | 3.57142857142532e-05 | 0 | `time_limit` |
| week_orchestration · joint_week_model_frequencies_locked_quantities_and_verification | 812 / 1071 | CBC | 29.035282 | 23.632 | `feasible` | 3.91617054751416 | 3.78687184877909 | `time_limit` |
| recipe_solver · real_catalog_recipe_quantities_and_lexicographic_ratios | 25 / 44 | CBC | 0.237562 | 0.028 | `optimal` | 0.0245008006084151 | 0.0245008006084151 | `completed` |

Le altre formulazioni riproducono: (a) config demo della suite `test_diet_day` con `mode=free`; (b) `WeekOrchestrationTests.profile()` e `weekly_model` con `week_start=2026-10-05`, `k=1`, `pool_size=1`, `max_protein_repetitions=3`, e `make_config` della fixture; (c) `formulate_recipe(templates()[0], RecipeSolverTests.config())`, prima dell'ottimizzazione dei rapporti. Tutti dati pubblici o sintetici, nessuna dieta personale. Non sono tempi delle suite complete o delle catene di alternative: il caso ricetta è un confronto di un'altra suite che usa lo stesso adattatore SciPy, non un caso qui dimostrato lento.

**Validazione e certificazione:** tutti e quattro i risultati hanno validazione indipendente Optees `verified`; anche `plan_recipe.values_verified` ha verificato limiti, integrità e tutti i vincoli sul modello originale. L'obiettivo è stato ricalcolato dai coefficienti e dai valori restituiti e coincide con quello Optees entro gli errori di arrotondamento (primo: `2.1276595744521386e-5` contro `2.12765957446615e-5`). Solo la ricetta ha stato `optimal` e bound coincidente. Per gli altri tre si certifica la fattibilità della soluzione, non l'ottimo esatto. Le distanze assolute incumbent–bound sono rispettivamente circa `2.12766e-5`, `3.57143e-5`, `0.129299`, `0`; sono misure sul risultato, non una tolleranza richiesta o applicata.

`relative_gap` di CBC/Optees usa `|obj-bound| / max(1, |obj|)`: per i due obiettivi vicini a zero restituisce circa `2.12766e-5` e `3.57143e-5`. Non è direttamente confrontabile con il `mip_gap=1.0` di HiGHS riportato da Claude, che normalizza diversamente. Non si deve dedurre ottimalità dal piccolo valore di questo campo. Il backend misura i propri millisecondi; il tempo end-to-end con `time.perf_counter` include chiamate MCP, validazione, coda e polling, escludendo avvio/inizializzazione della sessione. CBC supera il limite richiesto di 15 s in tutti e tre i casi `feasible`: il limite osservato non è un tetto rigido sul tempo end-to-end.

Riproducibilità del primo payload e del dataset misurato:

- Payload SHA-256: `eaa02b0ad13e1ad65a0a8266e0ae4049ebec8e279ba71889844e2146fe52143e`.
- `dataset/crea/foods.csv` SHA-256: `c9a3596a57aa95ba9d2eb654e15463204d9cd4c5d97b51f3a304091fcd519d27`.

Gli esiti mostrano che il problema non resta illimitatamente aperto nel percorso reale misurato: ritorna un incumbent al limite con stato `feasible`. La necessità di definire il criterio di arresto e allineare gli adattatori rimane da decidere; nessuna correzione introdotta in questa richiesta. Nessuna nuova dichiarazione di suite verde/check pronto: la richiesta era limitata alle misure.

### Collegamento T-011 · Codex, 14 ottobre 2026

Dati T-008 invariati. Implementata la fase ε conservativa nel giorno e
mip_gap=0,05 nel settimanale, autorizzati dal proprietario. Misure finali
Optees 0.11.1/CBC sul payload pubblico: 29,112→0,459 s (giorno);
44,695→24,426 s (settimanale), con verifiche concorrenti. Dettagli, obiettivi,
bound, gap e certificazione entro ε nella Revisione T-011. Gruppo limitato:
48 test verdi in 16,051 s; suite completa non certificabile per il solve diretto
illimitato del test protetto test_diet_day e i rossi T-009. check_task T-008
con test fermato a 120 s (uscita 124); --no-tests stampa ESITO: non pronto
(8 problemi), tutti perimetri sovrapposti. Nessun dato modificato né commit.
