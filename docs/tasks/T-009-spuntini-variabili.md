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
659bc9a1399d366c810b68054e818e3951edcb5a
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

### Test rossi di Codex · 12 ottobre 2026

- Dieci metodi in `tests/test_snack_options.py`, con file temporaneo e dodici alimenti sintetici (6 frutti, 3 latticini, 3 cereali/cracker), vettori completi e porzioni sintetiche dichiarate. Nessun download, nessun catalogo personale. Le regole dello scenario sostitutivo sono scritte nella directory temporanea.
- Il file viene reindirizzato nelle letture `Path` e `daily_meals` ricaricato: il contratto vale anche se il futuro caricamento avviene all'import. Il modello e la decodifica ricevono lo stesso catalogo copiato, compresi i prodotti preferiti sintetici.
- Coperti: scelta unica, limiti e griglia 5 g, pasti ammessi, esclusioni, nutrienti incompleti, preferiti/penalità, limiti banana, interruttore pomeridiano, frequenza predefinita 3 e configurata 2, ripiego con avviso, sovrapposizione prima/dopo in libera e sostituto sintetico. La quantità 32 g dei crackers confezionati è conservata.
- Verifica completa del file committato (incluso default di N): 10 test in 214,671 s, `FAILED (failures=10)`, senza errori di esecuzione; 9 metodi rossi (la misura ha due sottocasi falliti), compatibilità dei limiti banana verde. Il successivo controllo della frequenza senza chiave esplicita (default 3) fallisce anch'esso per la sola banana, in 1,236 s. I fallimenti riguardano opzioni assenti, assenza di varietà e limite settimanale; non import o fixture.
- Misura sui piani attuali: libera prima/dopo 73,66% / 73,66%; sostituto sedentario prima/dopo 73,66% / 73,66%. Tre alternative, massimo della sovrapposizione canonica fra coppie, controllato contro il report del generatore. File ignorato dal codice attuale: nessun beneficio futuro dedotto. Budget dichiarato del generatore 120 s per richiesta; l'adattatore SciPy dei test esistenti risolve esattamente senza limite per singola chiamata. Questi valori certificano soltanto la misura dei piani prodotti, non il minimo globale della sovrapposizione.

### Decisioni e perimetro

Conferma del proprietario: «Sì, conserva le porzioni preferite e segnala il perimetro settimanale». La griglia di 5 g vale per le opzioni del catalogo; i preferiti mantengono la porzione confezionata esistente.

Il formato JSON non è definito nei dettagli dalla scheda. I test propongono un oggetto `{version, max_occurrences_per_meal, options}` e voci `{source, id, name, group, meals, portion_min_g, portion_max_g, portion_source}`. Sono nomi di contratto proposti, da recepire nella specifica dei dati prima dell'implementazione, non un formato già presente nel repository. Il default di N è verificato omettendo la relativa chiave.

La costruzione del problema congiunto e gli avvisi sono in `scripts/week_orchestration.py`, fuori dai file consentiti. Il limite settimanale e il suo ripiego non si possono affidare alla sola formulazione giornaliera. Occorre estendere esplicitamente il perimetro prima dell'implementazione; qui nessun file di produzione T-009 è stato modificato.

### Effetto sui test esistenti

Analisi statica, senza prototipo di produzione T-009:

- `DailyMealsTests.test_hard_bounds_can_override_preference` pretende esattamente banana come ripiego: con altri alimenti poveri di grassi potrebbe cambiare esito pur rispettando il vincolo. Test protetto invariato; la decisione su questa aspettativa precede l'implementazione.
- `test_whole_day_totals_and_discrete_personal_products` e `test_optional_second_bar_is_not_available_without_permission`: porzioni 35/32 g e permesso per seconda barretta restano obbligatori. Le penalità giornaliere devono continuare a favorire i preferiti. La relazione fra preferito quotidiano e limite settimanale va specificata prima dell'estensione settimanale: i nuovi test con preferiti sono giornalieri, quelli settimanali senza preferiti.
- `test_unplanned_afternoon_is_explicit_and_adds_no_food`, esclusioni, target duri e assenza di etichette personali altrui devono rimanere validi.
- `IngredientOverlapTests` e `WeekOrchestrationTests` confrontano in più punti il report con la misura effettiva, senza richiedere i vecchi grammi. Le misure possono cambiare; budget, numero di alternative e fattibilità vanno rivalutati dopo l'implementazione. Nessuna soglia aggiunta nei test nuovi.
- Nessuna correzione di date necessaria per questo contratto; nessun test esistente modificato.

Commit dei soli test: `659bc9a1399d366c810b68054e818e3951edcb5a`. Scheda e Base aggiornate nella working tree; nessuna implementazione T-009.

Verifica esistente durante la fase T-008: 58 test completati verdi; suite interrotta durante `DailyMealsTests.test_daily_targets_do_not_reuse_main_meal_targets` per tempi di soluzione, dopo esaurimento del budget del controllo protetto T-008. Nessuna suite verde dichiarata; questo esito riguarda il catalogo ampliato T-008, senza implementazione T-009 e senza i test nuovi nella scoperta iniziale.
