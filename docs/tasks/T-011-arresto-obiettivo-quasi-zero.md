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
659bc9a1399d366c810b68054e818e3951edcb5a
```

## File consentiti

```
scripts/plan_diet_day.py
scripts/nutrient_timing.py
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
