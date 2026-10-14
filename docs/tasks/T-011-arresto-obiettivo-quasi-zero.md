# T-011 · Arresto rapido quando il piano giornaliero è già ottimo (obiettivo ≈ 0)

**Per Codex.** Autore della scheda: Claude · Data: 2026-10-12 · Tappa del piano: 3
Esecutore: Codex (formulazione e solver: parte delicata) · Revisore: Claude
Prerequisito per chiudere T-008; da fare con i dati T-008 nella working tree.

## Obiettivo

Quando esiste un piano giornaliero con scostamento nutrizionale entro una soglia trascurabile ε, ottenerlo subito con stato certificabile, invece di attendere il limite di tempo per dimostrare un ottimo che il gap relativo non può chiudere.

## Evidenza (misure Codex, Optees reale, CBC, limite 15 s)

| Problema | Tempo | Stato | Obiettivo | Bound |
|---|---:|---|---:|---:|
| Daily targets, 115 variabili | 16,42 s | feasible | 2,1e-5 | 0 |
| Diet day libero | 17,68 s | feasible | 3,6e-5 | 0 |
| Modello settimanale | 29,04 s | feasible | 3,916 | 3,787 |
| Ricetta | 0,24 s | optimal | 0,0245 | 0,0245 |

Con i test SciPy/HiGHS senza limite di tempo il primo problema non termina (0,7 s prima di T-008). Payload: `docs/t008-daily-targets-optees-problem.json`. Optees/CBC non supporta un gap assoluto (verificato dalla sessione Optees). Il caso settimanale (gap relativo ~3%) è fuori da questa scheda: lo risolve la tolleranza relativa su CBC nell'estensione di Optees in corso.

## Contratto

1. In `plan_diet_day.optimize_day`, prima del solve che minimizza lo scostamento nutrizionale (sia nel ramo con preferenze, dopo il vincolo sulla penalità, sia nel ramo senza), una **fase di fattibilità**: stesso problema, vincolo `scostamento ≤ ε` e obiettivo nullo, con limite di tempo breve (proporre e motivare, es. 3 s). Lo scostamento è non negativo per costruzione: verificarlo e scriverlo; se non lo è, fermarsi.
2. Se la fase trova una soluzione: è il risultato, stato **`optimal` entro ε** con campi espliciti (es. `optimality: "within_absolute_tolerance"`, `absolute_tolerance: ε`, valore dello scostamento). Vincoli verificati come oggi (`values_verified`).
3. Se la fase è infattibile o scade: solve normale invariato, stesso comportamento di oggi.
4. ε motivato rispetto alle unità dell'obiettivo (che cosa significa in kcal/grammi di scostamento) e definito in un solo punto. Proposta iniziale 1e-3, da confermare con l'analisi.
5. `nutrient_timing.refine` e gli altri chiamanti non perdono la garanzia: se fanno solve propri con lo stesso tipo di obiettivo, applicare la stessa fase o motivare perché non serve.
6. Adattatori di test (`tests/test_recipe_solver.solve` e simili): rispettano `problem['solver']['time_limit']` come la produzione e restituiscono `feasible` al limite, così un test non resta mai bloccato all'infinito. Nessuna asserzione indebolita.
7. Nessun cambiamento a vincoli, target, porzioni, preferenze.

## Criteri di accettazione

- [ ] Test: problema con piano a scostamento ≈ 0 → risultato con stato `optimal` entro ε in tempo breve, senza attendere il limite (verificare la sequenza delle chiamate al solver, non i secondi).
- [ ] Test: problema dove lo scostamento minimo è > ε → fase infattibile, solve normale, risultato identico a oggi.
- [ ] Test: ramo con preferenze: la penalità ottima resta rispettata anche nella fase ε.
- [ ] Payload T-008 con Optees reale: tempo e stato prima/dopo riportati nella scheda.
- [ ] Con i dati T-008: `test_daily_meals`, `test_diet_day` e suite completa verdi, tempi riportati.

## Base

```
93befa334575270019c9134838cf5d7d8077c6b7
```

## File consentiti

```
scripts/plan_diet_day.py
scripts/nutrient_timing.py
scripts/week_orchestration.py
tests/test_recipe_solver.py
tests/test_near_zero_objective.py
```

## Test protetti

```
tests/test_daily_meals.py
tests/test_diet_day.py
tests/test_presumed_meals.py
```

## Test aggiuntivi consentiti

```
tests/test_near_zero_objective.py
```

## Comando di test

```
set -a; . ./.env; set +a; PYTHONPATH=scripts:tests:. ${DIET_PYTHON:-python} -m unittest test_near_zero_objective test_daily_meals test_diet_day test_recipe_solver -q
```

## Resoconto

## Revisione

### Verifica preliminare Codex · 13 ottobre 2026 — arresto prima delle modifiche

La precondizione del contratto non vale per l'obiettivo completo attuale. In
`plan_diet_day.formulate`, le variabili `devN` hanno limite inferiore zero e
coefficiente `1 / target`, con target strettamente positivo: la sola somma
nutrizionale `D = Σ devN / targetN` è dunque non negativa per costruzione.
Tuttavia la stessa formulazione aggiunge bonus negativi sulle variabili di
selezione delle ricette preferite (`plan_diet_day.py`, `PREFERENCE_BONUS`) e
degli abbinamenti (`meal_matches.penalties`: −0,03 per like e −0,06 per love),
oltre alle penalità positive dei dislike. `optimize_day` ripristina questo
obiettivo misto anche dopo la fase delle preferenze dei prodotti confezionati.
Non esiste quindi la garanzia generale `obiettivo >= 0`, né un taglio su questo
obiettivo certifica `D <= ε`. Per esempio, aritmeticamente, D=0,02 e un bonus
−0,03 danno −0,01: il taglio passerebbe con uno scostamento superiore a ε.
Questo esempio illustra la formula, non è un piano risolto o un risultato misurato.

Per la sola D, ε=1e-3 è adimensionale: la somma degli scostamenti assoluti
divisi per i rispettivi target è al massimo 0,1%. Ciascuno scostamento è quindi
al massimo `0,001 × target` kcal o grammi; questi massimi individuali non si
possono consumare tutti contemporaneamente, perché condividono il budget.
Per esempio, un target di 2000 kcal consente al massimo 2 kcal se assorbe tutto
il budget, un target di 100 g consente 0,1 g. Sono esempi dimensionali, non dati
personali né misure. Questa interpretazione non vale per l'obiettivo misto.

Serve una decisione di contratto prima di procedere: distinguere esplicitamente
D dall'obiettivo misto e stabilire come preservare i bonus di ricette e
abbinamenti. Restituire il primo piano con D entro ε e obiettivo nullo potrebbe
perdere l'ottimalità delle preferenze soft attualmente incluse nell'obiettivo;
non sarebbe coerente con «nessun cambiamento a preferenze». Anche la
certificazione dopo `nutrient_timing.refine` dovrà riguardare la stessa D.
Non è stata scelta o implementata una reinterpretazione del contratto.

Per il settimanale, proposta ancora da misurare: `mip_gap=0.05` nel dizionario
`solver` costruito da `week_orchestration.weekly_model`, attualmente con il solo
`time_limit`. È un compromesso di qualità dell'obiettivo misto, non una
tolleranza sui vincoli nutrizionali; il rapporto dipende dalla convenzione del
backend e va riportato insieme a obiettivo e bound. Il 5% è proposto sulla base
della precedente misura T-008 (3,916 contro 3,787, circa 3,3% con quella
convenzione), non costituisce una nuova misura con Optees 0.11.1.
Occorre autorizzare `scripts/week_orchestration.py`, che non è tra i file
consentiti. Non impostarlo globalmente in `solve_problem`, perché cambierebbe
anche i solve giornalieri e delle preferenze.

Esito: fermato come richiesto al punto 1. Nessun file di produzione o test
modificato, nessun dato T-008 modificato, nessun commit. Non eseguiti nuovi
solve prima/dopo, suite o check_task: non esiste una correzione da certificare.
Le precedenti misure T-008 non sono attribuite alla versione 0.11.1.

### Decisione del proprietario · 14 ottobre 2026

Confermato il perimetro conservativo: fase ε solo per obiettivi composti da
scostamenti nutrizionali; obiettivi misti invariati. Confermata anche
l’estensione a `scripts/week_orchestration.py` per il gap settimanale.

### Esecuzione Codex · 14 ottobre 2026

La somma D delle variabili devN non negative divise per target positivi è
non negativa. La fase breve si applica esclusivamente a questa componente:
coefficienti non nulli positivi solo su devN, minimizzazione, limiti inferiori
non negativi. Bonus negativi e penalità soft positive escludono la fase.
ε=0,001 è il budget complessivo di errore relativo: sui target sintetici del
caso giornaliero (1800 kcal, 80 g proteine, 60 g grassi, 235 g carboidrati),
i massimi individuali sono 1,8 kcal, 0,08 g, 0,06 g e 0,235 g; condividono
il budget e non possono essere consumati tutti insieme.

Limite della fase: min(3 s, limite esistente), un quinto del budget ordinario
di 15 s. Il taglio usa ε × (1−1e-6) per lasciare margine all'aritmetica floating
point; il certificato verifica comunque D <= ε senza aumentare ε. Nella prima
prova HiGHS produceva 0,001000000000000013: la verifica rigorosa portava al
fallback e ai tre fallimenti giornalieri, risolti con questo margine.
Nessuna asserzione o fixture protetta è stata modificata.

La fase preserva il vincolo della penalità dei prodotti confezionati.
Infattibilità/scadenza riportano al solve originale. L'ottimalità è dichiarata
esplicitamente entro tolleranza (`optimality`, `absolute_tolerance`,
`nutritional_deviation`); il valore zero e il bound zero del risultato MCP
riguardano l'obiettivo nullo della fase, non un ottimo nutrizionale esatto.
La redistribuzione nutrient_timing mantiene D entro ε, ricontrolla il valore e
propaga il certificato; il proprio obiettivo soft di timing segue il solve
ordinario perché non è D.

Per altri chiamanti: `multiobjective_day.solve_strategy` fa solve nutrizionali
propri, anche pesati e minmax. Non passa da optimize_day ed è fuori dai file
consentiti: non riceve la nuova fase. Serve autorizzare
`scripts/multiobjective_day.py` per estendere la politica e definire il budget
per gli obiettivi pesati/minmax. Non si afferma una copertura universale.

Per il settimanale è stato impostato mip_gap=0,05 in weekly_model, come
autorizzato. La misura seguente mostra un gap certificato di circa 3,36%
con un peggioramento dell'incumbent di circa 0,002315 rispetto al precedente;
nessun vincolo allentato. Il gap è del modello misto complessivo, non delle
quantità nutrizionali né della fase delle preferenze presa isolatamente.
Gli adattatori condivisi SciPy rispettano time_limit e mip_gap e distinguono
feasible con incumbent da not_solved senza incumbent e da infeasible.

#### Misure ripetute sul codice finale

Optees installato: versione 0.11.1, HEAD locale c052088 verificato. Percorso produzione solve_problem, CBC,
limite ordinario 15 s, stessa sessione locale. Tempo totale dopo avvio sessione;
comprende validazione, creazione job e polling. Misure con verifiche concorrenti:
non sono un benchmark isolato e il limite CBC è osservabilmente morbido.

| Modello | Totale s | CBC s | Stato | Obiettivo MCP | Bound | Gap riportato |
|---|---:|---:|---|---:|---:|---:|
| daily_before | 29.112 | 28.714 | feasible | 2.12765957446615e-05 | 0.0 | 2.12765957446615e-05 |
| daily_after | 0.459 | 0.141 | optimal | 0.0 | 0.0 | 0.0 |
| week_before | 44.695 | 35.704 | feasible | 3.916170547514159 | 3.786871848779086 | 0.033016615892059994 |
| week_after | 24.426 | 12.005 | optimal | 3.9184852108244175 | 3.786871848779086 | 0.03358781645564545 |

Il daily_after ha D=0,0009159278959812625 ed è optimal entro ε, non esatto.
Prima e dopo sono lo stesso payload pubblico T-008, 115 variabili e 140
vincoli originali; dopo passa da optimize_day e aggiunge il taglio. Il modello
settimanale è quello iniziale del test joint_week (812 variabili, 1071 vincoli),
prima senza mip_gap e dopo con 0,05. Tutti e quattro hanno validazione MCP
verified e verifica indipendente values_verified su vincoli originali.
Sul settimanale dopo: mip_gap_applied=true, mip_abs_gap_applied=false; negli
altri casi entrambe false. Lo stato optimal CBC settimanale va letto insieme
al gap non nullo, non come prova di ottimo esatto.

Prima ripetizione precedente al margine numerico: daily 17,511→0,341 s,
settimanale 30,518→12,049 s; stesso incumbent e bound settimanali.
I risultati completi locali sono /tmp/t011-measurements.json; i numeri qui
trascritti sono certificati da quei quattro job e non derivati da dati personali.

#### Verifiche e blocchi

- Nuovi test: 10 in test_near_zero_objective (sequenza fase breve, fallback
  infattibile e timeout, preferenze bloccate, esclusione obiettivo misto e
  penalità positiva, timing, budget inferiore, adattatore gap/timeout).
- Gruppo finale test_near_zero_objective + test_daily_meals + test_recipe_solver
  + test_presumed_meals: **Ran 48 tests in 16.051s — OK**.
- Primo gruppo fase+giornalieri dopo margine: 17 test in 2,728 s, OK.
- Comando della scheda avviato con budget complessivo 120 s: uscita 124;
  test giornalieri verdi, bloccato in test_diet_day.test_free_mode_and_invalid_targets.
  Questo test protetto chiama direttamente scipy.milp senza options e senza
  optimize_day. Per allinearlo serve autorizzare una modifica del suo adattatore,
  preservando le asserzioni sui vincoli e l'interpretazione dello stato.
- Suite completa avviata con budget 480 s, interrotta dopo aver raggiunto lo
  stesso test protetto e confermato un rosso esterno alla scheda: non completa,
  nessun riepilogo OK. test_snack_options.test_enabled_slots_choose_one_catalog_option_with_five_gram_portions
  verificato separatamente: 1 test, 0,165 s, 1 failure (banana invece di catalogo
  sintetico); resta intenzionalmente rosso T-009, funzionalità non implementata.
- check_task T-011 e T-008 con test: budget 120 s, uscita 124, nessun ESITO
  finale perché il comando contiene lo stesso solve illimitato.
- check_task --no-tests: T-011 **ESITO: non pronto (9 problemi)**, tutti file
  della lavorazione T-008/T-009 già presenti; T-008 **ESITO: non pronto (8 problemi)**,
  file della T-011, scheda T-009 e payload diagnostico. Non modificato il checker
  e non allargati artificialmente i perimetri per renderli verdi.
- Dati T-008 e test protetti invariati durante questa lavorazione.

Stato: implementazione parziale da rivedere; chiusura bloccata sui perimetri,
sull'adattatore protetto e sui test rossi T-009. Nessun commit.

### Step 1 autorizzato · Codex, 15 ottobre 2026

Il proprietario ha autorizzato esclusivamente la modifica dell'adattatore di
`tests/test_diet_day.py`, senza modificare fixture o asserzioni. L'adattatore
ora esegue optimize_day, usando il solve SciPy condiviso con time_limit e
mip_gap della formulazione; verifica i valori sui vincoli originali e conserva
l'interfaccia success/status/x. Solo optimal (compreso il certificato entro ε)
è success; feasible resta status=1 e non viene promosso a successo.

Confronto AST contro HEAD: setUp e tutti gli otto metodi test_* identici.
Comando test_diet_day + test_near_zero_objective + test_daily_meals +
test_recipe_solver: Ran 38 tests in 4.027s, FAILED (failures=1), quindi 37 passati.
Nessun blocco del solver; test_free_mode_and_invalid_targets passa.

Il solo rosso è test_training_schedule_and_allowed_groups: vieta tra tutti i
candidati gli ID 007120 e 181100, ma la formulazione attuale con T-008 li può
includere perché le tracce nutrizionali sono ora utilizzabili. Il conflitto è
nei candidati costruiti da formulate prima di qualsiasi solve, non dipende
dall'adattatore né dal piano selezionato. L'asserzione resta invariata: serve
una decisione esplicita del revisore sul contratto di questo test.

Nessuna modifica ulteriore di produzione, nessun dato T-008 modificato,
nessun commit o aggiornamento Base. check_task continuerà anche a rilevare
il file protetto cambiato contro Base finché il revisore non salva la modifica
autorizzata e aggiorna la base pertinente. Suite completa non ripetuta in
questa fase: già presente il conflitto protetto, oltre ai rossi T-009.

### Contratto del test aggiornato con autorizzazione del proprietario · 15 ottobre 2026

Il proprietario ha confermato la sostituzione della sola asserzione che
escludeva gli ID 007120 e 181100. In test_training_schedule_and_allowed_groups
ora ogni candidato viene verificato sui quattro nutrienti diet.NUTRIENTS:
valore presente, convertibile in numero, finito e non negativo. Lo zero delle
tracce è ammesso. Nessun divieto alimentare aggiunto. Tutte le altre asserzioni
su calendario, gruppi ammessi e selezioni, nonché tutte le fixture, restano
invariate. Nessuna modifica al codice di produzione o ai dati in questa fase.

Verifica: test_diet_day + test_near_zero_objective + test_daily_meals +
test_recipe_solver: **Ran 38 tests in 4.339s — OK**. Risolto il conflitto del
test training; non si estende questo esito alla suite completa o a check_task.
Restano i rossi T-009, l'estensione multiobjective fuori perimetro e le
sovrapposizioni della working tree; il checker rileverà inoltre la modifica
autorizzata del test protetto contro Base finché il revisore non la salva e
aggiorna la base pertinente. Nessun commit, nessun aggiornamento Base.

### Salvataggio autorizzato · 15 ottobre 2026

Il proprietario ha autorizzato i commit di tutti i cambiamenti. T-008: 7d83382;
T-011: daf9065; annotazioni T-009: 93befa3. Base aggiornata a 93befa3 per
proteggere la versione salvata dei test, comprese le modifiche esplicitamente
autorizzate dell’adattatore e dell’asserzione di test_diet_day. Le annotazioni
precedenti descrivono lo stato storico e non costituiscono una suite verde.

### Verifica dopo il salvataggio · 15 ottobre 2026

check_task T-011: Ran 38 tests in 6.414s — OK; ESITO: pronto per revisione.
Controllo eseguito sulla working tree pulita dopo c8909a4, prima della
preparazione T-012. Gruppo congiunto import CREA, ingredient_overlap,
diet_day, near_zero_objective, daily_meals e recipe_solver: 52 test in
61,251 s, OK. Suite completa non ripetuta: i test rossi T-009 restano
un blocco noto e non sono stati saltati o modificati.
