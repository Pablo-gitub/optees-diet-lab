# T-005 · Pasti presunti a intervallo trattati come i confermati (DIARY-01)

Autore della scheda: Claude · Data: 2026-10-11 · Tappa del piano: 2
Esecutore: Codex (test rosso + correzione; logica del diario e della ricalibrazione) · Revisore: Claude

## Obiettivo

Un pasto presunto che contiene un piatto a intervallo (`dish_estimate`) viene rappresentato e contato come lo stesso pasto confermato: stessa incertezza, stessa prudenza nell'analisi e nella ricalibrazione.

## Contesto

Rilevato da Codex nella revisione di T-003 (registro **DIARY-01**). Oggi, con un pranzo pianificato a intervallo e 14 giorni altrimenti idonei, `make_proposal` restituisce `available` con il pasto presunto e `insufficient_data` dopo la conferma: `day_view` per il presunto usa i nutrienti centrali del piano (`eaten` puntuale), mentre la conferma (`diary_mutation` → `consumed_estimate` con `registration='planned_dish_estimate'`) produce un intervallo senza nutrienti puntuali.

Decisione del proprietario: i presunti valgono come confermati.

## Contratto

- Un presunto con `planned.nutrient_ranges` presenti è restituito da `day_view` con la stessa forma che avrebbe dopo la conferma (in particolare `eaten`/`eaten_range` e contributo ai totali), senza scrivere nulla; il campo `presumed` resta `true`.
- `week_analysis` e `make_proposal` producono lo stesso esito (stato e, se disponibile, stessa proposta salvo ID e token) per il pasto presunto e per lo stesso pasto confermato.
- Pasti presunti senza intervallo: invariati.

## Criteri di accettazione

- [ ] Test rosso: 14 giorni idonei con un pranzo a intervallo → esito di `make_proposal` identico presunto/confermato (oggi diverso).
- [ ] `day_view` di un presunto a intervallo: forma di `eaten`, `eaten_range` e `totals.eaten` uguale al confermato; `presumed: true`.
- [ ] Nessuna GET scrive; test di T-001 e T-003 invariati e verdi; suite completa verde.

## Fuori perimetro

Soglie, formule e limiti della ricalibrazione; interfaccia.

## Base

```
45f1ddc2d05822c6ff9cda6d8195f0d67657e507
```

## File consentiti

```
scripts/diary_service.py
scripts/progress_analysis.py
tests/test_presumed_interval_dishes.py
```

## Test protetti

```
tests/test_presumed_meals.py
tests/test_presumed_meals_extra.py
tests/test_checkin_presumed.py
tests/test_checkin_presumed_extra.py
```

## Test aggiuntivi consentiti

```
tests/test_presumed_interval_dishes.py
```

## Comando di test

```
set -a; . ./.env; set +a; PYTHONPATH=scripts:tests:. ${DIET_PYTHON:-python} -m unittest test_presumed_interval_dishes test_presumed_meals test_presumed_meals_extra test_checkin_presumed test_checkin_presumed_extra test_progress_api test_progress_recalibration -q
```

## Revisione

### Codex / Gemini · 11 ottobre 2026 · Esecuzione
- Test rosso aggiunto in `tests/test_presumed_interval_dishes.py`: confermato il fallimento per forma difforme di `eaten` in `day_view` e per la divergenza in `make_proposal` (`available` con presunto vs `insufficient_data` dopo conferma).
- Correzione applicata in `scripts/diary_service.py`: in `day_view`, per i pasti presunti con piatti a intervallo (`nutrient_ranges`), `eaten_range` assume i range pianificati ed `eaten` ha `items: []` con nutrienti puntuali a `None`; `totals.eaten` riflette l'incertezza con valori `None` come nel caso confermato.
- Test protetti invariati e verdi; suite completa verde (466 test); `check_task`: pronto per revisione.
