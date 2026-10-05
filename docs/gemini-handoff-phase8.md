# Consegna a Gemini — fase 8: ingredienti delle ricette e catalogo attività

Lavoro lungo e ripetitivo, diviso in **sessioni**. Ogni sessione è indipendente e si chiude con un file di proposte e un registro. **Gemini non fa commit e non approva nulla:** Claude verifica e approva. Specifica generale: [phase8-spec.md](phase8-spec.md) §3 e §8.

## Regole valide per ogni sessione

1. **Proporre, non approvare.** Non usare mai `--approve` di `scripts/match_recipe_ingredients.py` e non modificare `config/ingredient-approved-mappings.json`.
2. **Solo dati locali.** Valori nutrizionali da `dataset/crea/foods.csv`; prodotti da `dataset/open_food_facts/catalog.sqlite`. Ogni id citato deve esistere davvero in quei file: va controllato con una query, non ricordato. Un id inventato fa scartare l'intero lotto.
3. **Lo stato conta quanto il nome.**
   - Crudo, cotto o bollito; secco o cotto (pasta, riso, legumi); fresco, in scatola o surgelato; intero o raffinato; sgocciolato o con liquido.
   - Se lo stato della ricetta non corrisponde a nessuna voce CREA, la proposta è `ambiguous`, con il motivo. Non scegliere la voce più vicina.
4. **Mai uno zero al posto di un dato mancante.** Se la voce CREA non ha un nutriente, segnalarlo; non sostituirlo con 0.
5. **Quantità.** Pezzi, spicchi e cucchiai si convertono solo con una fonte (`standard_conversions`) e restano `requires_review: true`.
6. **Prodotti del supermercato facoltativi.** Un record Open Food Facts si propone solo con codice a barre presente nel catalogo locale e macro completi; serve a sapere quale prodotto comprare.
7. **Nessun dato personale** nei file prodotti.
8. **File che Gemini può toccare.**
   - `config/ingredient-dictionary.json`: solo voci **nuove** di `canonical_ingredients`, o sinonimi aggiunti a voci esistenti.
   - `config/ingredient-proposals/batch-NN.json`: nuovo, uno per sessione.
   - `docs/ingredient-proposals-log.md`: registro, una sezione per sessione.

   Nient'altro: niente `scripts/`, niente `web/`, niente test.

## Formato di `config/ingredient-proposals/batch-NN.json`

```json
{
  "batch": 1,
  "created": "2026-10-06",
  "group_selection": "primi 60 gruppi per numero di ricette, esclusi quelli già approvati",
  "proposals": [
    {
      "canonical_id": "cipolla_cruda",
      "raw_names_covered": ["Onion", "Onions", "Red onion"],
      "raw_names_excluded": [{ "name": "Spring onion", "reason": "Cipollotto: ortaggio diverso, voce CREA separata" }],
      "recipes_count": 368,
      "proposed": { "source": "CREA", "id": "005300", "name": "Cipolle, crude", "state": "crudo, parte edibile" },
      "status": "proposed" ,
      "confidence": "high",
      "rationale": "Le ricette usano cipolla cruda poi cotta nel piatto: il valore crudo pesato è corretto per il calcolo.",
      "off_candidates": [],
      "check_query": "grep '^005300' dataset/crea/foods.csv"
    }
  ]
}
```

- `status` vale `proposed` oppure `ambiguous` (con `rationale` che spiega cosa manca); nessun altro valore.
- `check_query` è il comando con cui Claude può ritrovare l'id in un secondo. Se la query non lo trova, la proposta viene scartata.

## Sessioni

### Sessione 0 — catalogo attività (piccola, una volta sola)

Bozza di `config/activity-catalog.json` secondo [phase8-spec.md](phase8-spec.md) §3.1.

- **Attività:** camminata lenta, normale e veloce; camminata in salita; escursione; bici tranquilla e moderata; corsa leggera; nuoto tranquillo; ballo; yoga; pilates; stretching; giardinaggio.
- **Per ogni voce:**
  - `met` e codice del **Compendium of Physical Activities, edizione 2024**: il codice a 5 cifre e la descrizione **esatta** della tabella;
  - l'URL della pagina del Compendium dove si legge il valore;
  - `healthkit_types` (per esempio `HKWorkoutActivityTypeWalking`);
  - `duration_minutes` (min, max, passo);
  - `goals`, con i soli id della tabella del §2 della specifica.
- Se un valore non si trova nel Compendium 2024, scrivere `null` e il motivo. Non usare valori di siti divulgativi.
- **Registro:** il file `docs/ingredient-proposals-log.md`, sezione «Sessione 0», con l'elenco degli URL consultati.

### Sessioni 1…N — ingredienti, 60 gruppi per sessione

1. Rigenerare la coda e il rapporto, che non sovrascrivono il solver:
   ```sh
   python scripts/match_recipe_ingredients.py --report-file data/recipe_matching_report.json --review-queue data/recipe_ingredient_review_queue.json
   ```
2. **Scegliere i 60 gruppi successivi.**
   - Ordine: `recipes_count` decrescente, esclusi i gruppi già approvati o già presenti in un batch precedente.
   - Dalla sessione 3 in poi: prima i gruppi che compaiono nelle ricette italiane (`--cuisine Italian` per vederli), poi gli altri.
3. **Per ogni gruppo:**
   - se manca la voce, aggiungere o estendere la voce nel dizionario: `display_name_it`, sinonimi it/en, `expected_qualifiers`, `crea_matches`;
   - scrivere la proposta nel batch;
   - dividere i nomi grezzi che in realtà sono ingredienti diversi (per esempio «Onion, tomato, cabbage to serve» non è «cipolla»).
4. **Rieseguire il comando del punto 1** e annotare nel registro, prima e dopo la sessione:
   - i gruppi riconosciuti;
   - le proposte esatte;
   - quelle ambigue;
   - quelle mancanti;
   - le ricette con tutti gli ingredienti proposti.
5. **Chiudere la sessione** con il registro: lotto, gruppi trattati, ambigui con il motivo, dubbi per Claude.

**Dimensione della sessione:** 60 gruppi è un riferimento. Se una sessione si allunga, chiudere prima con meno gruppi fatti bene.

## Cosa fa Claude dopo ogni sessione

- Controlla a campione almeno 15 proposte con `check_query` e tutte quelle con `confidence` diversa da `high`.
- Approva con `--approve` quelle verificate e scrive l'esito nel registro.
- Fa il commit con i file di Gemini e le approvazioni.
- Dopo il commit, Codex rigenera le ricette esportabili per il solver; in quel passaggio entrano solo le ricette con tutti gli ingredienti approvati.
