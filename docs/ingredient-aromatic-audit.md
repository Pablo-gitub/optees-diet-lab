# Aromatici in traccia — audit offline

Policy `recipe-special-sources-v3`, decisione dell'utente del 2026-10-06.
Gli aromatici moderati hanno **0 kcal dichiarate**; rimangono nella spesa,
con categoria `condimento`, esclusa anche dalla sovrapposizione fra piani.
Non entrano negli ingredienti ponderali del solver: alimenti primari e grassi
continuano a essere pesati e conteggiati normalmente.

## Regole

- Erbe fresche elencate in config: 20 g per porzione.
- Aglio 10 g; zenzero fresco 15 g; peperoncino fresco 25 g;
  succo/scorza di limone o lime 30 g; citronella, lime kaffir e alloro 10 g.
- `sprig`, `leaf`, `bunch`, `handful`: sempre traccia per costruzione, con
  quantità positiva. Per verificare una quantità ponderale sopra soglia si
  usa l'ingrediente espresso in grammi, anziché queste unità qualitative.
- `pinch`, `q.b.`, `to taste`: qualitative; nessun peso inventato.
- `clove`, `slice`, `piece`: conversioni approvate con fonte/autore quando
  disponibili; pesi soltanto proposti non valgono come pesi verificati.
- `tsp`, `tbsp`, `ml`: prima conversione/peso approvato; altrimenti proxy
  volumetrico dichiarato configurabile 1 g/ml (5 ml/tsp e 15 ml/tbsp).
- `juice of 1 lemon/lime` in almeno quattro porzioni: regola esplicita sul
  conteggio del frutto (`max_juice_fruits_per_serving = 0.25`), senza assegnare
  grammi misurati al succo. Se sono dichiarati grammi, vale la soglia di 30 g.
- Testa d'aglio (`head`) non equivale a uno spicchio; resta ingrediente normale.
- Oli, burro, panna, zucchero, miele, frutta secca, semi, formaggi e salse
  composte restano normali, anche in piccole dosi. Tolti i semi dall'elenco
  precedente delle spezie in traccia. Pesto e curry paste non sono aromatici.
- Sola eccezione per la salsa di soia semplice: al massimo 1 tbsp per porzione,
  16 g nella conversione approvata locale; oltre il limite resta normale.
- Peperoni dolci e cipolle sono verdure, non aromatici.
- Gli esclusi dei batch rimangono esclusi; nessuna approvazione canonica
  nutrizionale né conversione esterna è generata automaticamente.

## Risultati sullo stesso catalogo

| Indicatore | Prima | Dopo |
|---|---:|---:|
| Ricette esaminate | 834 | 834 |
| Occorrenze ingredienti | 7843 | 7843 |
| Ricette con quantità utilizzabili (pesi risolti o tracce ammesse) | 310 | 311 |
| Ricette pronte nel matcher | 26 | 34 |
| Ricette con condimenti in traccia | 545 | 712 |
| Occorrenze escluse dai batch | 275 | 275 |

**8 ricette nuove pronte, nessuna precedentemente pronta persa.**
693 occorrenze aromatiche in 459 ricette. Tutte le 34 ricette esportate sono
complete anche nel ricalcolo locale dei nutrienti, senza pesi di aromatici
aggiunti alla massa ottimizzata. ID nuovi e conteggi verificabili in
[data/ingredient-aromatic-audit.json](../data/ingredient-aromatic-audit.json).

L'audit riguarda l'uscita del matcher; non sovrascrive gli adattamenti già
revisionati di `config/recipe-solver.json`. Il catalogo importato, le
approvazioni e il registro delle conversioni restano invariati.

## Riproduzione

```bash
PYTHONPATH=scripts:tests:. python scripts/match_recipe_ingredients.py \
  --report-file /tmp/aromatic-report.json \
  --export-solver /tmp/aromatic-solver.json \
  --export-mappings /tmp/aromatic-mappings
```

Confronto iniziale raccolto prima dell'aggiunta della classe. Mapping e modelli
esportati mantengono `trace_class: aromatic`, soglia e nota della policy.
I modelli conservano le quantità/unità originali; il matcher conserva la
fonte/autore delle conversioni nella nota quantitativa o nel campo
`conversion` quando presente. Il calcolatore verifica nuovamente la soglia:
un override sopra il limite viene bloccato per le quantità espresse in
grammi; le quattro unità sempre in traccia conservano la priorità dichiarata. La lista della spesa riusa la sezione finale dei
condimenti in traccia, senza sommarli ai grammi degli alimenti primari.
