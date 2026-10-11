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
set -a; . ./.env; set +a; PYTHONPATH=scripts:tests:. ${DIET_PYTHON:-python} -m unittest test_import_crea test_ingredient_overlap test_diet_day -q
```

## Resoconto

## Revisione
