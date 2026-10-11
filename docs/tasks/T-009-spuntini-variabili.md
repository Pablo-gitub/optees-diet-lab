# T-009 · Spuntini e frutto pomeridiano a scelta fra più alimenti (non solo banana)

**Per Codex (test rossi), poi Gemini (dati e implementazione).** Autore della scheda: Claude · Data: 2026-10-12 · Tappa del piano: 3
Revisori: Codex (solver), Claude (dati e commit)

## Obiettivo

Colazione, spuntino del mattino e spuntino del pomeriggio scelgono fra un **insieme configurabile** di opzioni (frutti, yogurt, crackers e simili), con porzioni realistiche, invece della sola banana. Il prodotto preferito dell'utente resta un'opzione privilegiata come oggi.

## Decisione del proprietario (12 ottobre 2026)

«La banana era un esempio»: gli spuntini possono alternarsi con altri frutti e anche con alimenti non di frutta, come crackers o yogurt.

## Contesto (nomi verificati)

`scripts/daily_meals.py` → `add_choices`: per `breakfast`, `morning_snack`, `afternoon_snack` le opzioni sono il prodotto preferito (`food_preferences.preferences[meal].preferred_product_id`, porzione fissa) e la banana `007510` fra `banana_min_g` e `banana_max_g` (scritta nel codice); `afternoon_fruit` abilita lo spuntino del pomeriggio; `excluded_crea_ids` esclude. Diagnosi T-007: la banana fissa pesa ≥ 2,1 kg/settimana, oltre il 10% del totale: impedisce la varietà.

## Contratto

1. **Dati** (Gemini): `config/snack-options.json` con voci `{id CREA o OFF, nome, gruppo (frutta|latticino|cereale/cracker|altro), pasti ammessi, porzione_min_g, porzione_max_g, fonte della porzione}`; solo alimenti con i quattro nutrienti completi nel catalogo; porzioni da fonti verificabili (porzioni standard già usate nel progetto o etichette); nessuna affermazione sanitaria. Almeno 6 frutti, 3 latticini, 3 cereali/cracker. Revisione di Claude prima dell'uso.
2. **Solver**: per ogni pasto abilitato, scelta di **una** opzione fra quelle ammesse e non escluse, con porzione a passi di 5 g entro i limiti; il prodotto preferito resta favorito come oggi (penalità invariate); la banana è una voce del file come le altre.
3. **Varietà nella settimana**: la stessa opzione non più di N volte a settimana per pasto (N in configurazione, default 3), come le frequenze proteiche; se non è fattibile, il vincolo si allenta con avviso, non fallisce.
4. **Compatibilità**: `banana_min_g/max_g` esistenti diventano i limiti della voce banana per chi li ha impostati; `afternoon_fruit` resta il nome dell'interruttore ma vale per lo spuntino del pomeriggio in generale (testo UI da aggiornare in seguito).

## Criteri di accettazione (test rossi di Codex)

- [ ] Con il file di opzioni, una settimana libera ha negli spuntini almeno 3 alimenti diversi e nessuna opzione oltre N volte per pasto.
- [ ] Opzione esclusa da `excluded_crea_ids` mai scelta; prodotto preferito scelto come oggi quando presente.
- [ ] Porzioni sempre entro i limiti della voce e a passi di 5 g.
- [ ] Profili esistenti con `banana_min_g/max_g`: limiti rispettati per la banana.
- [ ] Varietà non fattibile (es. una sola opzione ammessa) → piano valido con avviso, non errore.
- [ ] Sovrapposizione delle alternative (metrica T-007) misurata prima/dopo sullo scenario libero e su un sostituto sintetico: riportata, nessuna soglia imposta.
- [ ] Suite completa verde.

## Fuori perimetro

Pranzo e cena (T-010); interfaccia del Profilo per scegliere le opzioni (scheda successiva).

## Base

<!-- Codex aggiorna con il commit dei test rossi -->
```
DA-AGGIORNARE
```

## File consentiti

```
config/snack-options.json
scripts/daily_meals.py
```

## Test protetti

```
tests/test_snack_options.py
tests/test_daily_meals.py
```

## Test aggiuntivi consentiti

```
tests/test_snack_options_extra.py
```

## Comando di test

```
set -a; . ./.env; set +a; PYTHONPATH=scripts:tests:. ${DIET_PYTHON:-python} -m unittest test_snack_options test_daily_meals test_week_orchestration -q
```

## Istruzioni per Codex (test rossi)

Scrivere `tests/test_snack_options.py` sui criteri, con un file di opzioni sintetico nei test (non dipendere da `config/snack-options.json` reale). Prima di committare, verificare l'effetto sui test esistenti come in T-003 ed elencarlo qui. Committare solo i test e aggiornare «Base».

## Resoconto Gemini

## Revisione
