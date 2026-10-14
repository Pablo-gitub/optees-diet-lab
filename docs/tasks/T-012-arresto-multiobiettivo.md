# T-012 · Fase ε nelle scalarizzazioni nutrizionali

Per Gemini. Autore: Codex · 15 ottobre 2026. Revisore: Codex.
Prerequisito: T-011 salvata, con adattatore e contratto test_diet_day aggiornati.

## Obiettivo

Riutilizzare la fase breve T-011 nei solve nutrizionali di multiobjective_day,
senza cambiare strategie, pesi, preferenze o vincoli. Questa fase estende le
somme nutrizionali; il primo solve minmax/maxmin resta invariato.

## Contratto

1. In `solve_strategy`, applicare `solve_nutrition` al solve balanced/pareto
   e alla somma secondaria dopo il primo solve minmax/maxmin ottimo. Il primo
   solve delle preferenze e il primo solve su worst_error restano normali.
   Non introdurre una fase ε sul massimo: richiede un contratto distinto.
2. Riutilizzare costanti, margine numerico, verifica e fallback T-011. È ammesso
   aggiungere a solve_nutrition un parametro esplicito per la funzione solver:
   il chiamante passa il proprio solve_problem; nessun riconoscimento dei test.
   Preservare anche i modelli senza chiave solver usati dalle fixture esistenti,
   adottando per la fase il default produttivo di 15 s e il limite breve 3 s.
3. Per pesi positivi finiti, ε=1e-3 resta una tolleranza assoluta della somma
   effettiva D_w=Σ w_n dev_n/target_n, senza riscalare o normalizzare i pesi.
   Ogni componente con peso positivo soddisfa dev_n <= ε target_n/w_n.
   Il certificato riguarda D_w e deve indicare l'ambito pesato; non certificare
   la somma non pesata. Componenti a peso zero non ricevono questa garanzia.
   Obiettivi negativi, non finiti o con coefficienti soft restano sul solve
   ordinario; non introdurre nuovi limiti o modifiche ai pesi accettati.
4. Per objective_override affidarsi alla verifica dell'obiettivo effettivo:
   bonus e penalità soft escludono la fase. Nessuna nuova gerarchia nutrizione/
   preferenze, nessuna modifica dei bonus esistenti.
5. Preservare il vincolo sulla penalità preferenze e quello sul primo ottimo
   minmax/maxmin. La fase secondaria non certifica un primo solve solo feasible.
   Preservare tutti i certificati durante nutrient_timing e gli eventuali
   fallback: non assegnare un certificato a una soluzione diversa senza verifica.
6. Non modificare formule di metrics, ranking Pareto, bandit, vincoli duri,
   porzioni o dati T-008. Se un test protetto cambia esito, annotarlo e fermarsi.

## Criteri di accettazione

- [ ] Balanced quasi zero: sequenza con fase breve, valori verificati e certificato.
- [ ] Somma pesata: certificato sull'obiettivo effettivo, senza normalizzare i pesi.
- [ ] Minimum superiore a ε, timeout senza incumbent o soluzione non verificata:
      fallback ordinario, nessun falso certificato.
- [ ] Preferenze bloccate prima della fase, obiettivo misto escluso.
- [ ] Minmax/maxmin: primo solve invariato, fase solo sulla somma secondaria;
      valori primari e vincoli preservati, nessuna promozione di feasible.
- [ ] Modello e argomenti originali non mutati; timing preserva il certificato.
- [ ] Test protetti verdi e check_task pronto; suite completa eseguita e riportata
      fedelmente. I test rossi T-009 restano fuori da questa implementazione.

## Base

```
c8909a4
```

## File consentiti

```
scripts/plan_diet_day.py
scripts/multiobjective_day.py
scripts/nutrient_timing.py
tests/test_multiobjective_near_zero.py
```

## Test protetti

```
tests/test_multiobjective_day.py
tests/test_day_orchestration.py
tests/test_near_zero_objective.py
tests/test_nutrient_timing.py
tests/test_diet_day.py
```

## Test aggiuntivi consentiti

```
tests/test_multiobjective_near_zero.py
```

## Comando di test

```
set -a; . ./.env; set +a; PYTHONPATH=scripts:tests:. ${DIET_PYTHON:-python} -m unittest test_multiobjective_near_zero test_multiobjective_day test_day_orchestration test_near_zero_objective test_nutrient_timing test_diet_day -q
```

## Resoconto Gemini

## Revisione
