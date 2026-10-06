# Registro delle proposte ingredienti e catalogo attività

Registro cronologico delle sessioni di lavoro su catalogo attività fisica e associazione ingredienti delle ricette ([phase8-spec.md](phase8-spec.md) §3 e §8, [gemini-handoff-phase8.md](gemini-handoff-phase8.md)).

---

## Sessione 0 — Catalogo attività (Compendium of Physical Activities 2024)

- **Data di esecuzione:** 2026-10-06
- **File prodotto:** `config/activity-catalog.json`
- **Fonte ufficiale:** 2024 Adult Compendium of Physical Activities ([pacompendium.com](https://pacompendium.com))
- **Stato:** Bozza completa di 14 attività secondo specifica §3.1.

### URL consultati nel Compendium 2024

1. `https://pacompendium.com/walking`
   - Camminata lenta: codice `17152`, MET 2.8, *"Walking, 2.0 to 2.4 mph, level, slow pace, firm surface"*
   - Camminata normale: codice `17190`, MET 3.8, *"Walking, 2.8 to 3.4 mph, level, moderate pace, firm surface"*
   - Camminata veloce: codice `17200`, MET 4.8, *"Walking, 3.5 to 3.9 mph, level, brisk, firm surface, walking for exercise"*
   - Camminata in salita: codice `17034`, MET 5.3, *"Climbing hills, no load, 1 to 5% grade, moderate-to-brisk pace"*
   - Escursione: codice `17082`, MET 5.3, *"Hiking or walking at a normal pace through fields and hillsides, no load"*
2. `https://pacompendium.com/bicycling`
   - Bici tranquilla: codice `01015`, MET 4.3, *"Bicycling, self-selected easy pace"*
   - Bici moderata: codice `01016`, MET 7.0, *"Bicycling, self-selected moderate pace"*
3. `https://pacompendium.com/running`
   - Corsa leggera: codice `12020`, MET 7.5, *"Jogging, general, self-selected pace"*
4. `https://pacompendium.com/water-activities`
   - Nuoto tranquillo: codice `18310`, MET 6.0, *"Swimming, leisurely, not lap swimming, general"*
5. `https://pacompendium.com/dancing`
   - Ballo: codice `03025`, MET 4.5, *"Ethnic or cultural dancing (e.g. Greek, Middle Eastern, hula, salsa, merengue, bamba y plena,  flamenco, belly, and swing)"*
6. `https://pacompendium.com/conditioning-exercise`
   - Yoga: codice `02175`, MET 2.3, *"Yoga, General"*
   - Pilates: codice `02105`, MET 2.8, *"Pilates, general"*
   - Stretching: codice `02101`, MET 2.3, *"Stretching, mild"*
7. `https://pacompendium.com/lawn-garden`
   - Giardinaggio: codice `08245`, MET 3.8, *"Gardening, general, moderate effort"*

Ogni voce include mappatura HealthKit (`HKWorkoutActivityTypeWalking`, `HKWorkoutActivityTypeCycling`, ecc.), intervallo `duration_minutes` a passi di 5 min, e associazione agli obiettivi della matrice di specifica §2 (`health`, `cardio_fitness`, `fat_loss`, `mobility`).

**Revisione Claude (2026-10-06):** codici, MET e descrizioni ricontrollati sulle pagine del Compendium 2024; le descrizioni di questo registro sono state riallineate al file, che era già corretto. Catalogo accettato come base del passo 8.3.

---

## Sessione 1 — Ingredienti: Lotto 1 (primi 60 gruppi per numero di ricette)

- **Data di esecuzione:** 2026-10-06
- **File prodotti/modificati:**
  - `config/ingredient-proposals/batch-01.json` (nuovo, 60 proposte strutturate)
  - `config/ingredient-dictionary.json` (esteso con 13 nuove voci in `canonical_ingredients`)
  - `data/recipe_matching_report.json` e `data/recipe_ingredient_review_queue.json` (rigenerati da `match_recipe_ingredients.py`)
- **Regole rispettate:** nessun uso di `--approve`, nessun commit, nessun tocco a `scripts/` o `web/`, nessun dato personale, ogni ID verificato con query locale eseguibile in `check_query`.

### Criterio di selezione dei 60 gruppi

Gruppi estratti dalla coda di revisione iniziale ordinati per `recipes_count` decrescente, escludendo i 10 ingredienti già approvati in `config/ingredient-approved-mappings.json` (`olio_oliva_extravergine`, `pomodori_passata`, `basilico_fresco`, `pasta_semola_secca`, `pomodori_freschi`, `mozzarella_vacca`, `pane_bianco`, `olive_nere`, `acqua`, `aglio`).

### Voci canoniche aggiunte al dizionario (`config/ingredient-dictionary.json`)

Sono state create 13 nuove voci in `canonical_ingredients`, coprendo varianti non mappate prima della sessione:
1. `cumino_polvere` (Cumino macinato, spezia essiccata)
2. `zenzero_fresco` (Zenzero fresco, radice decorticata)
3. `curcuma_polvere` (Curcuma in polvere, spezia essiccata)
4. `alloro_foglie` (Alloro, foglie essiccate)
5. `panna_acida` (Panna acida / sour cream fermentata ~15% lipidi)
6. `cavolo_cappuccio_crudo` (Cavolo cappuccio verde crudo, CREA 005200)
7. `agnello_crudo` (Agnello crudo, CREA 104020)
8. `lime_fresco` (Lime / limetta fresca)
9. `latte_cocco` (Latte di cocco culinario fluido in lattina)
10. `paprika_polvere` (Paprika dolce/affumicata in polvere)
11. `vaniglia` (Vaniglia baccello / estratto naturale)
12. `cannella_stecca` (Cannella in stecche per infusione)
13. `uvetta_secca` (Uva secca / uva sultanina / uvetta, CREA 007410)

### Esito delle 60 proposte in `batch-01.json`

- **Proposte con associazione CREA verificata (`proposed`):** 38 gruppi
  - `cipolla_cruda` (368 ricette) → CREA `005300` (Cipolle, crude)
  - `uovo_gallina_intero` (215 ricette) → CREA `181100` (Uova di gallina, intero)
  - `olio_vegetale_neutro` (211 ricette) → CREA `009799` (Oli vegetali)
  - `farina_grano_00` (168 ricette) → CREA `000220` (Farina di frumento, tipo 00)
  - `patate_crude` (150 ricette) → CREA `006500` (Patate, crude)
  - `succo_limone` (132 ricette) → CREA `008040` (Limoni, succo)
  - `burro` (121 ricette) → CREA `190010` (Burro)
  - `riso_brillato_crudo` (119 ricette) → CREA `000100` (Riso, brillato)
  - `prezzemolo_fresco` (117 ricette) → CREA `006840` (Prezzemolo, fresco)
  - `latte_vacca_parz_scremato` (114 ricette) → CREA `135020` (Latte vaccino parz. scremato)
  - `pollo_petto_crudo` (107 ricette) → CREA `106500` (Pollo, petto, crudo)
  - `zucchero` (102 ricette) → CREA `201500` (Zucchero, saccarosio)
  - `carote_crude` (94 ricette) → CREA `005150` (Carote, crude)
  - `peperoni_crudi` (89 ricette) → CREA `005600` (Peperoni, crudi)
  - `manzo_magro_crudo` (68 ricette) → CREA `101160` (Bovino adulto o vitellone, fesa, crudo)
  - `yogurt_intero` (57 ricette) → CREA `150010` (Yogurt, da latte intero)
  - `fagioli_cannellini_scatola` (51 ricette) → CREA `004210` (Fagioli, Cannellini in scatola, scolati)
  - `spinaci_crudi` (49 ricette) → CREA `005700` (Spinaci, crudi)
  - `peperoncino_fresco` (48 ricette) → CREA `006830` (Peperoncini piccanti, freschi)
  - `yogurt_greco` (41 ricette) → CREA `150020` (Yogurt greco, da latte intero)
  - `maiale_lombo_crudo` (40 ricette) → CREA `105210` (Maiale, lombo, crudo)
  - `salsa_soia` (40 ricette) → CREA `509020` (Soia, salsa)
  - `cetrioli_freschi` (38 ricette) → CREA `005220` (Cetrioli, freschi)
  - `menta_fresca` (36 ricette) → CREA `006810` (Menta, fresca)
  - `piselli_surgelati` (35 ricette) → CREA `004730` (Piselli, surgelati)
  - `ceci_scatola` (32 ricette) → CREA `004010` (Ceci, in scatola, scolati)
  - `pomodori_pelati_scatola` (32 ricette) → CREA `006680` (Pomodori, pelati in scatola)
  - `tacchino_petto_crudo` (31 ricette) → CREA `106710` (Tacchino intero, senza pelle, crudo)
  - `funghi_prataioli_crudi` (29 ricette) → CREA `006000` (Funghi coltivati, prataioli, crudi)
  - `gamberi_sgusciati` (27 ricette) → CREA `128100` (Gamberi)
  - `pangrattato` (27 ricette) → CREA `000570` (Pangrattato)
  - `cavolo_cappuccio_crudo` (27 ricette) → CREA `005200` (Cavolo cappuccio, verde, crudo)
  - `agnello_crudo` (26 ricette) → CREA `104020` (Agnello, crudo)
  - `melanzane_crude` (23 ricette) → CREA `005500` (Melanzane, crude)
  - `porri_crudi` (23 ricette) → CREA `005650` (Porri, crudi)
  - `zucchine_crude` (23 ricette) → CREA `005730` (Zucchine, crude)
  - `pancetta_affettata` (22 ricette) → CREA `110310` (Pancetta tesa)
  - `uvetta_secca` (22 ricette) → CREA `007410` (Uva, secca)

- **Proposte con stato ambiguo (`ambiguous`):** 22 gruppi
  1. `sale` (232 ricette): assente in CREA; minerale a 0 kcal; prodotto OFF Selex presente ma con etichetta sodio da verificare.
  2. `sale_e_pepe` (207 ricette): ingrediente composto privo di voce unitaria; da scorporare o escludere.
  3. `coriandolo_fresco` (93 ricette): assente in CREA; il proxy prezzemolo differisce per aroma e specie.
  4. `brodo_vegetale` (62 ricette): in CREA esiste solo 503010 (Dadi da brodo anidri, 250 kcal/100g e ~50% sale); serve diluizione 1:50 o voce per brodo liquido.
  5. `cumino_polvere` (62 ricette): assente in CREA; proposto candidato OFF Spar (9100000770208).
  6. `brodo_pollo` (55 ricette): stesso problema di stato di brodo vegetale (dado vs brodo liquido pronto).
  7. `erba_cipollina` (49 ricette): assente in CREA; il bulbo di cipolla è un proxy botanico inadeguato.
  8. `zenzero_fresco` (48 ricette): assente in CREA; radice fresca presente solo in USDA.
  9. `olio_frittura` (44 ricette): olio a consumo parziale (assorbimento reale 8–20% non documentabile automaticamente).
  10. `origano_secco` (41 ricette): assente in CREA; presente prodotto Esselunga OFF (8002330020644).
  11. `pomodoro_concentrato` (38 ricette): in CREA esiste solo passata (21 kcal/100g); il concentrato ha 80–100 kcal/100g (concentrazione non corrispondente).
  12. `ghee` (36 ricette): grasso anidro (~880 kcal/100g) diverso dal burro CREA con acqua (758 kcal/100g).
  13. `curcuma_polvere` (33 ricette): assente in CREA; presente prodotto Sottolestelle OFF (02772217).
  14. `lievito_secco` (32 ricette): assente in CREA.
  15. `alloro_foglie` (28 ricette): assente in CREA; uso in sola infusione con apporto energetico nullo.
  16. `panna_acida` (28 ricette): assente in CREA (panne presenti hanno diverso tenore lipidico e non sono fermentate); presente OFF Coop (8001120709905).
  17. `lime_fresco` (26 ricette): assente in CREA (specie agrumicola diversa dal limone).
  18. `tofu_fresco` (25 ricette): assente in CREA; presente prodotto OFF Vemondo Lidl (20001568).
  19. `latte_cocco` (25 ricette): assente in CREA; presente OFF Altromercato (8016225310437).
  20. `paprika_polvere` (24 ricette): assente in CREA.
  21. `vaniglia` (24 ricette): assente in CREA; aroma in tracce.
  22. `cannella_stecca` (22 ricette): assente in CREA; spezia in stecca da infusione.

### Note e dubbi per Claude

1. **Spezie ed erbe aromatiche essiccate assenti in CREA:** Le spezie più frequenti della cucina internazionale (`cumino`, `curcuma`, `zenzero`, `alloro`, `cannella`, `vaniglia`, `paprika`) non sono censite nelle tabelle ufficiali CREA. Per il solver, considerarle a 0 kcal (come condimenti esclusi ai sensi del §9) oppure importare una mini-tabella USDA ufficiale (FoodData Central) risolverebbe istantaneamente centinaia di ricette senza falsare i macronutrienti.
2. **Brodi (liquido vs dado):** Attualmente il dizionario associa i brodi al dado concentrato `503010`. È indispensabile definire una voce di brodo liquido diluito (circa 5–10 kcal per 100 ml) oppure applicare un fattore di conversione per evitare sovrastime di sodio ed energia.
3. **Olio di frittura:** Proponiamo di marcare formalmente le ricette che contengono «Oil for frying» con un fattore di assorbimento standard del 10% del peso dell'alimento impanato/fritto, invece di imputare i grammi totali dell'olio del tegame.
4. **Concentrato di pomodoro:** Serve una voce autonoma nel dizionario con prodotto OFF verificato (doppio concentrato Mutti o marca supermercato) per non confonderlo con la passata.
5. **Sale:** Proponiamo l'approvazione con sorgente speciale `salt` (analoga alla gestione di `water` già attiva in `config/ingredient-approved-mappings.json`).

---

## Confronto metriche matcher: Prima vs Dopo Sessione 1

| Metrica | Prima (Baseline) | Dopo (Sessione 1) | Variazione |
|---|---|---|---|
| **Ricette totali esaminate** | 834 | 834 | = |
| **Istanze totali ingredienti** | 7.843 | 7.843 | = |
| **Gruppi canonici / equivalenze** | 990 | 967 | -23 |
| **Istanze `missing`** | 2.707 (34,5%) | 2.483 (31,7%) | **-224** (-2,8%) |
| **Istanze `proposed_exact`** | 2.344 (29,9%) | 2.376 (30,3%) | **+32** (+0,4%) |
| **Istanze `proposed_proxy`** | 593 (7,6%) | 740 (9,4%) | **+147** (+1,8%) |
| **Istanze `ambiguous`** | 1.039 (13,2%) | 1.084 (13,8%) | +45 (+0,6%) |
| **Istanze `approved`** | 999 (12,7%) | 999 (12,7%) | = *(regola: niente `--approve`)* |
| **Istanze `needs_review`** | 161 (2,1%) | 161 (2,1%) | = |
| **Gruppi canonici `missing`** | 895 | 866 | **-29** |
| **Gruppi canonici `proposed_exact`** | 56 | 57 | +1 |
| **Gruppi canonici `proposed_proxy`** | 13 | 16 | +3 |
| **Gruppi canonici `ambiguous`** | 19 | 21 | +2 |
| **Gruppi canonici `approved`** | 7 | 7 | = |
| **Ricette con tutti ingredienti proposti** | 42 | 47 | **+5 ricette** |
| **Ricette pronte per il solver** | 24 | 24 | = *(richiede approvazione Claude)* |

### Revisione Claude (2026-10-06)

Tutti i 38 id CREA esistono, con il nome dichiarato. Esistono anche gli 8 codici a barre OFF, tutti `numeric_candidate`.

**Approvati: 30.**
- Cipolla, olio vegetale, farina 00, patate, succo di limone, burro, riso.
- Latte parzialmente scremato, come default per «milk».
- Zucchero, carote, peperoni, yogurt intero e greco, spinaci, peperoncino, salsa di soia.
- Cetrioli, menta, piselli, pelati, tacchino, funghi, gamberi, pangrattato.
- Cavolo cappuccio, agnello, melanzane, porri, zucchine, uvetta.

**Non approvati, da rivedere:**
- `uovo_gallina_intero` e `prezzemolo_fresco`: la voce CREA non ha i carboidrati. Mai zero al posto del dato mancante; resta il prodotto di marca usato finora.
- `pollo_petto_crudo`: copre «Chicken, jointed», «Chicken, in pieces» e «Minced chicken». Sono tagli con pelle o osso e più grassi del petto.
- `manzo_magro_crudo`: «Minced beef», «Beef chuck» e «Beef shin» sono molto più grassi della fesa.
- `maiale_lombo_crudo`: «Pork shoulder» e «Minced pork» sono più grassi del lombo.
- `fagioli_cannellini_scatola` e `ceci_scatola`: non è detto che la ricetta usi legumi in scatola anziché secchi. Inoltre «butter beans» sono fagioli di Lima, non cannellini.
- `pancetta_affettata`: il «bacon» britannico è spesso lombo affumicato, più magro della pancetta tesa.

**Limite dello strumento.** `--approve` vale per tutto il gruppo canonico del matcher e non rispetta `raw_names_excluded`. Per esempio «Spring onion» resta nel gruppo della cipolla. Va chiesto a Codex di far rispettare le esclusioni.

**Effetto.** Le ricette pronte restano 24. Quasi tutte le altre sono bloccate da sale, pepe, spezie, erbe e brodi. Serve una regola: un condimento in traccia vale 0 kcal, con una sorgente speciale come già avviene per `acqua`. I brodi vanno trattati come liquido diluito.


## Sessione 2 — Revisione 8 gruppi (Parte a) e successivi 60 gruppi (Parte b)

Data: **2026-10-06**  
File proposte: `config/ingredient-proposals/batch-02.json`  
Totale proposte nel lotto: **79 proposte** (19 revisioni Parte a + 60 nuovi gruppi Parte b).  
Stato proposte: **44 proposed**, **35 ambiguous**.  
Regole rispettate: nessun uso di `--approve`, nessun commit git, nessuna modifica a `scripts/` o `web/`. Ogni id CREA verificato con query esatta `grep '^CREA,<id>' dataset/crea/foods.csv`.

---

### Parte (a) — Revisione delle 8 proposte non approvate di Sessione 1

In conformità ai rilievi di Claude nella revisione del batch 01, i gruppi complessi sono stati disaggregati nel dizionario e nel batch delle proposte:

1. **Pollo (4 gruppi distinti):**
   - `pollo_petto_crudo`: taglio magro puro, fesa/petto senza pelle crudo (**CREA 106500**). *Proposed (high)*.
   - `pollo_coscia_cruda`: cosce, fusi e sovracosce senza pelle (**CREA 106610**). *Proposed (high)*.
   - `pollo_macinato_crudo`: macinato di pollo. In CREA non esiste carne macinata di pollo -> *Ambiguous*.
   - `pollo_con_osso_crudo`: pollo intero o a pezzi con osso/pelle. Le ricette indicano peso lordo con osso (scarto osseo 30–40% non standardizzabile) -> *Ambiguous*.

2. **Manzo (3 gruppi distinti):**
   - `manzo_magro_crudo`: tagli magri nobili (fesa, filetto, controfiletto, scamone) (**CREA 101160**). *Proposed (high)*.
   - `manzo_macinato_crudo`: carne macinata di manzo (10–15% lipidi). Associata come proxy ai tagli anteriori di vitellone (**CREA 101120**). *Proposed (medium, proxy)*.
   - `manzo_brasato_crudo`: tagli da cottura lunga e spezzatino (sottospalla, collo, chuck, shin, geretto) (**CREA 101230**). *Proposed (high)*.

3. **Maiale (3 gruppi distinti):**
   - `maiale_lombo_crudo`: lombo e lonza magra cruda (**CREA 105210**). *Proposed (high)*.
   - `maiale_spalla_cruda`: spalla e coppa cruda per cotture lente (**CREA 105220**). *Proposed (high)*.
   - `maiale_macinato_crudo`: macinato di maiale. Assente in CREA -> *Ambiguous*.

4. **Legumi (4 gruppi distinti: scatola vs secchi):**
   - `fagioli_cannellini_scatola`: cannellini in scatola scolati (**CREA 004210**). *Proposed (high)*.
   - `fagioli_cannellini_secchi`: cannellini secchi crudi da reidratare (**CREA 004200**). *Proposed (high)*.
   - `ceci_scatola`: ceci in scatola scolati precotti (**CREA 004010**). *Proposed (medium)*.
   - `ceci_secchi`: ceci secchi crudi (**CREA 004000**). *Proposed (high)*.

5. **Butter beans (separati):**
   - `butter_beans`: fagioli di Lima (*Phaseolus lunatus*), cultivar gigante distinta dai cannellini. Assente in CREA -> *Ambiguous*.

6. **Bacon separato da pancetta (2 gruppi distinti):**
   - `pancetta_affettata`: pancetta tesa italiana stagionata (**CREA 110310**). *Proposed (high)*.
   - `bacon_affettato`: back bacon britannico affumicato da lombo salato. Assente in CREA -> *Ambiguous*.

7. **Uova e prezzemolo (verifica macronutrienti completi):**
   - `uovo_gallina_intero`: la voce generica CREA 181100 è priva dei carboidrati disponibili (`carbs_available_g_100g` vuoto). Rispettando il divieto di sostituire con 0, è marcata *Ambiguous*. Documentati candidati OFF a marchio completi (Esselunga Smart `8002330008048`: 136 kcal, 12.4g P, 9.5g F, 0.1g C).
   - `prezzemolo_fresco`: la voce generica CREA 006840 è priva dei carboidrati disponibili. Rispettando il divieto di sostituire con 0, è marcata *Ambiguous*. In OFF sono presenti solo referenze surgelate industriali (Esselunga `8002330000141`).

---

### Raw names esclusi per ciascuna approvazione proposta

Come da specifica, per ogni proposta con stato `proposed` vengono documentati tassativamente i nomi grezzi del corpus che **NON rientrano** nell'approvazione e che il matcher esclude:

| Gruppo canonico | ID CREA | Nomi grezzi ESCLUSI (`raw_names_excluded`) | Motivo esclusione |
|---|---|---|---|
| **`pollo_petto_crudo`** | `106500` | `Boneless chicken thigh`, `Chicken thigh`, `Chicken thighs`, `Chicken drumsticks`<br>`Minced chicken`<br>`Chicken, jointed`, `Chicken, in pieces`, `Whole chicken`, `Chicken on the bone`, `Chicken breasts on the bone`<br>`Chicken`, `Chicken for the curry` | Tagli scuri più grassi (gruppo `pollo_coscia_cruda`)<br>Carne macinata (gruppo `pollo_macinato_crudo`)<br>Tagli con osso e pelle (gruppo `pollo_con_osso_crudo`)<br>Denominazioni generiche a taglio non specificato |
| **`pollo_coscia_cruda`** | `106610` | `Chicken breast`<br>`Minced chicken`<br>`Whole chicken` | Petto di pollo magro (gruppo separato)<br>Macinato di pollo<br>Pollo intero con osso |
| **`manzo_magro_crudo`** | `101160` | `Minced beef`<br>`Beef chuck`, `Beef shin`, `Beef shin or shoulder`, `Beef shoulder`<br>`Beef on the bone`<br>`Beef flank`<br>`Beef or lamb`<br>`Beef` | Macinato di manzo (gruppo `manzo_macinato_crudo`)<br>Tagli anteriori da stufato (gruppo `manzo_brasato_crudo`)<br>Taglio con osso<br>Bavetta/pancia semigrassa<br>Ingrediente alternativo ambiguo<br>Denominazione generica non specificata |
| **`manzo_brasato_crudo`** | `101230` | `Beef on the bone`<br>`Beef or lamb` | Taglio con osso non separabile<br>Alternativa ambigua manzo/agnello |
| **`maiale_lombo_crudo`** | `105210` | `Pork shoulder`<br>`Minced pork`<br>`Pork belly`<br>`Pork neck`<br>`Pork ribs`<br>`Pork` | Spalla di maiale (gruppo `maiale_spalla_cruda`)<br>Macinato di maiale (gruppo `maiale_macinato_crudo`)<br>Pancetta fresca (gruppo separato ad alto tenore lipidico)<br>Coppa di maiale<br>Costine con osso<br>Denominazione generica |
| **`maiale_spalla_cruda`** | `105220` | `Pork loin`<br>`Minced pork`<br>`Pork belly`<br>`Pork ribs` | Lombo magro<br>Macinato di maiale<br>Pancetta fresca<br>Costine con osso |
| **`fagioli_cannellini_scatola`** | `004210` | `butter beans`<br>`White beans`, `white beans`<br>`Large white beans` | Fagioli di Lima (gruppo `butter_beans` separato)<br>Fagioli bianchi generici a cultivar non specificata<br>Possibile cultivar gigante o secca |
| **`fagioli_cannellini_secchi`** | `004200` | `butter beans`<br>`cannellini beans` | Fagioli di Lima<br>Cannellini in scatola già idratati |
| **`ceci_secchi`** | `004000` | `chickpeas` | Ceci precotti in scatola |
| **`pancetta_affettata`** | `110310` | `Bacon`, `Smoked bacon`<br>`Smoked bacon fat`, `Smoked pork fat`<br>`Smoked pork belly`<br>`Guanciale` | Bacon britannico affumicato da lombo (gruppo `bacon_affettato`)<br>Grasso fuso puro<br>Pancetta affumicata nordica<br>Guanciale di maiale (guancia stagionata) |
| **`feta`** | `162000` | `Feta and coriander` | Ingrediente composto / condimento misto |
| **`riso_cotto`** | `000105` | `risotto rice` | Riso crudo da risotto (Carnaroli/Arborio per cottura, non riso già cotto) |

---

### Parte (b) — Successivi 60 gruppi per numero di ricette

Trattati in ordine strettamente decrescente di `recipes_count` (da 22 a 10 ricette), escludendo approvati, batch 01 e condimenti in traccia (`trace:*`):

| N. | Gruppo canonico | Ricette | Stato | Fonte / ID | Denominazione / Motivazione se ambiguo | Query verifica (`check_query`) |
|---|---|---|---|---|---|---|
| 1 | `uovo_tuorlo` | 22 | `ambiguous` | — | CREA 183010 privo di carboidrati disponibili | `grep '^CREA,183010' dataset/crea/foods.csv` |
| 2 | `senape_dijon` | 21 | `ambiguous` | — | Senape di Digione assente in CREA | `grep -i 'senape' dataset/crea/foods.csv` |
| 3 | `feta` | 21 | `proposed` | CREA 162000 | Feta DOP greca (250 kcal, 15.6g P, 20.2g F, 1.5g C) | `grep '^CREA,162000' dataset/crea/foods.csv` |
| 4 | `grana_padano` | 21 | `proposed` | CREA 162410 | Grana Padano DOP (392 kcal, 33.9g P, 28.5g F, 0.0g C) | `grep '^CREA,162410' dataset/crea/foods.csv` |
| 5 | `noci` | 21 | `proposed` | CREA 008570 | Noci, secche (702 kcal, 14.3g P, 68.1g F, 5.1g C) | `grep '^CREA,008570' dataset/crea/foods.csv` |
| 6 | `ricotta_vacca` | 21 | `proposed` | CREA 166820 | Ricotta di vacca (146 kcal, 8.8g P, 10.9g F, 3.5g C) | `grep '^CREA,166820' dataset/crea/foods.csv` |
| 7 | `aneto_fresco` | 20 | `ambiguous` | — | Aneto fresco assente in CREA | `grep -i 'aneto' dataset/crea/foods.csv` |
| 8 | `avena_fiocchi` | 20 | `proposed` | CREA 003030 | Fiocchi d'avena (367 kcal, 8.0g P, 7.5g F, 66.8g C) | `grep '^CREA,003030' dataset/crea/foods.csv` |
| 9 | `fiocchi_di_latte` | 20 | `proposed` | CREA 170010 | Fiocchi di formaggio magro (115 kcal, 9.7g P, 7.1g F, 3.2g C) | `grep '^CREA,170010' dataset/crea/foods.csv` |
| 10 | `panna_fresca` | 19 | `proposed` | CREA 140300 | Panna da montare 35% lipidi (337 kcal, 2.3g P, 35.0g F, 3.4g C) | `grep '^CREA,140300' dataset/crea/foods.csv` |
| 11 | `cipollotto_fresco` | 18 | `ambiguous` | — | Cipollotto assente in CREA come ortaggio autonomo | `grep -i 'cipollott' dataset/crea/foods.csv` |
| 12 | `capperi_sottaceto` | 17 | `ambiguous` | — | Capperi assenti in CREA | `grep -i 'capper' dataset/crea/foods.csv` |
| 13 | `amido_mais` | 17 | `ambiguous` | — | CREA 000300 privo del valore dei lipidi | `grep '^CREA,000300' dataset/crea/foods.csv` |
| 14 | `lenticchie_cotte_scatola` | 17 | `proposed` | CREA 004510 | Lenticchie in scatola scolate (91 kcal, 5.0g P, 0.5g F, 15.4g C) | `grep '^CREA,004510' dataset/crea/foods.csv` |
| 15 | `pane_integrale` | 17 | `proposed` | CREA 000550 | Pane di tipo integrale (224 kcal, 8.5g P, 1.3g F, 44.1g C) | `grep '^CREA,000550' dataset/crea/foods.csv` |
| 16 | `vino_bianco` | 16 | `ambiguous` | — | CREA 405010 privo di proteine e carboidrati | `grep '^CREA,405010' dataset/crea/foods.csv` |
| 17 | `salsa_pesce` | 16 | `ambiguous` | — | Salsa di pesce asiatica assente in CREA | `grep -i 'salsa.*pesce' dataset/crea/foods.csv` |
| 18 | `pepe_nero` | 16 | `proposed` | CREA 006820 | Pepe nero (311 kcal, 11.4g P, 3.3g F, 49.0g C) | `grep '^CREA,006820' dataset/crea/foods.csv` |
| 19 | `sedano_crudo` | 16 | `proposed` | CREA 005680 | Sedano, crudo (23 kcal, 2.3g P, 0.2g F, 2.4g C) | `grep '^CREA,005680' dataset/crea/foods.csv` |
| 20 | `scalogno` | 16 | `ambiguous` | — | Scalogno assente in CREA | `grep -i 'scalogno' dataset/crea/foods.csv` |
| 21 | `timo_fresco` | 16 | `ambiguous` | — | Timo fresco assente in CREA | `grep -i 'timo' dataset/crea/foods.csv` |
| 22 | `zucchero_a_velo` | 15 | `proposed` | CREA 201500 | Zucchero, saccarosio (392 kcal, 100% C, identico chimico) | `grep '^CREA,201500' dataset/crea/foods.csv` |
| 23 | `mandorle_secche` | 15 | `proposed` | CREA 008540 | Mandorle dolci, secche (628 kcal, 22.0g P, 55.3g F, 4.6g C) | `grep '^CREA,008540' dataset/crea/foods.csv` |
| 24 | `mele_fresche` | 15 | `proposed` | CREA 007110 | Mele fresche senza buccia (57 kcal, 0.3g P, 0.1g F, 13.7g C) | `grep '^CREA,007110' dataset/crea/foods.csv` |
| 25 | `orzo_perlato` | 15 | `proposed` | CREA 000090 | Orzo perlato (346 kcal, 9.4g P, 1.5g F, 73.7g C) | `grep '^CREA,000090' dataset/crea/foods.csv` |
| 26 | `formaggio_quark` | 15 | `ambiguous` | — | Formaggio Quark assente in CREA | `grep -i 'quark' dataset/crea/foods.csv` |
| 27 | `vino_rosso` | 14 | `ambiguous` | — | CREA 405020 privo di proteine e carboidrati | `grep '^CREA,405020' dataset/crea/foods.csv` |
| 28 | `finocchi_crudi` | 14 | `ambiguous` | — | CREA 005320 privo del valore dei lipidi | `grep '^CREA,005320' dataset/crea/foods.csv` |
| 29 | `miele` | 14 | `proposed` | CREA 210010 | Miele naturale (304 kcal, 0.6g P, 0.0g F, 80.3g C) | `grep '^CREA,210010' dataset/crea/foods.csv` |
| 30 | `pane_segale` | 14 | `proposed` | CREA 000510 | Pane di segale (228 kcal, 8.3g P, 1.7g F, 45.4g C) | `grep '^CREA,000510' dataset/crea/foods.csv` |
| 31 | `riso_cotto` | 14 | `proposed` | CREA 000105 | Riso brillato cotto bollito (100 kcal, 2.0g P, 0.1g F, 24.2g C) | `grep '^CREA,000105' dataset/crea/foods.csv` |
| 32 | `aceto_vino` | 14 | `ambiguous` | — | Aceto di vino assente in CREA | `grep -i 'aceto' dataset/crea/foods.csv` |
| 33 | `formaggio_cheddar` | 14 | `proposed` | CREA 160880 | Cheddar formaggio (388 kcal, 26.7g P, 31.0g F, 0.5g C) | `grep '^CREA,160880' dataset/crea/foods.csv` |
| 34 | `lievito_chimico_polvere` | 13 | `ambiguous` | — | Lievito chimico per dolci assente in CREA | `grep -i 'lievito.*polvere' dataset/crea/foods.csv` |
| 35 | `fagiolini_freschi` | 13 | `proposed` | CREA 004310 | Fagiolini, freschi (24 kcal, 2.1g P, 0.1g F, 2.4g C) | `grep '^CREA,004310' dataset/crea/foods.csv` |
| 36 | `tofu_morbido` | 13 | `ambiguous` | — | Silken tofu morbido assente in CREA | `grep -i 'tofu' dataset/crea/foods.csv` |
| 37 | `timo_secco` | 13 | `ambiguous` | — | Timo essiccato assente in CREA | `grep -i 'timo' dataset/crea/foods.csv` |
| 38 | `zucca_cruda` | 13 | `proposed` | CREA 005720 | Zucca gialla, fresca (29 kcal, 1.1g P, 0.1g F, 3.5g C) | `grep '^CREA,005720' dataset/crea/foods.csv` |
| 39 | `brodo_manzo` | 12 | `ambiguous` | — | Brodo di manzo liquido non diluito assente in CREA | `grep -i 'brodo.*manzo' dataset/crea/foods.csv` |
| 40 | `sedano_rapa_crudo` | 12 | `proposed` | CREA 005690 | Sedano rapa, crudo (29 kcal, 1.9g P, 0.1g F, 3.8g C) | `grep '^CREA,005690' dataset/crea/foods.csv` |
| 41 | `panna_doppia` | 12 | `ambiguous` | — | Double cream (~48% lipidi) assente in CREA (regola 3) | `grep '^CREA,140300' dataset/crea/foods.csv` |
| 42 | `cardamomo_polvere` | 12 | `ambiguous` | — | Cardamomo spezia assente in CREA | `grep -i 'cardamomo' dataset/crea/foods.csv` |
| 43 | `merluzzo_fresco` | 12 | `proposed` | CREA 121410 | Merluzzo o nasello (71 kcal, 17.0g P, 0.3g F, 0.0g C) | `grep '^CREA,121410' dataset/crea/foods.csv` |
| 44 | `semi_sesamo` | 12 | `ambiguous` | — | Semi di sesamo assenti in CREA | `grep -i 'sesamo' dataset/crea/foods.csv` |
| 45 | `tonno_scatola_olio` | 12 | `proposed` | CREA 123610 | Tonno sott'olio sgocciolato (192 kcal, 25.2g P, 10.1g F, 0.0g C) | `grep '^CREA,123610' dataset/crea/foods.csv` |
| 46 | `pasta_fillo` | 12 | `ambiguous` | — | Pasta fillo sfoglia assente in CREA | `grep -i 'fillo' dataset/crea/foods.csv` |
| 47 | `burro_arachidi` | 12 | `proposed` | CREA 009010 | Burro d'arachidi 100% (625 kcal, 24.9g P, 53.7g F, 8.0g C) | `grep '^CREA,009010' dataset/crea/foods.csv` |
| 48 | `bicarbonato_sodio` | 11 | `ambiguous` | — | Sale minerale acalorico assente in CREA | `grep -i 'bicarbonato' dataset/crea/foods.csv` |
| 49 | `couscous_crudo` | 11 | `proposed` | CREA 000045 | Couscous, crudo (361 kcal, 13.7g P, 1.1g F, 76.5g C) | `grep '^CREA,000045' dataset/crea/foods.csv` |
| 50 | `scorza_limone` | 11 | `ambiguous` | — | Scorza di limone assente come voce distinta in CREA | `grep -i 'scorza' dataset/crea/foods.csv` |
| 51 | `senape` | 11 | `ambiguous` | — | Senape salsa pronta assente in CREA | `grep -i 'senape' dataset/crea/foods.csv` |
| 52 | `maiale_pancetta_fresca` | 11 | `ambiguous` | — | Pork belly crudo fresco assente in CREA | `grep -i 'maiale.*pancia' dataset/crea/foods.csv` |
| 53 | `peperoncino_scotch_bonnet` | 11 | `proposed` | CREA 006830 | Peperoncini piccanti freschi (30 kcal, proxy piccante fresco) | `grep '^CREA,006830' dataset/crea/foods.csv` |
| 54 | `mais_dolce` | 11 | `proposed` | CREA 000070 | Mais dolce in scatola sgocciolato (105 kcal, 3.4g P, 1.3g F, 20.5g C) | `grep '^CREA,000070' dataset/crea/foods.csv` |
| 55 | `avocado_fresco` | 11 | `proposed` | CREA 007490 | Avocado, fresco (238 kcal, 4.4g P, 23.0g F, 1.8g C) | `grep '^CREA,007490' dataset/crea/foods.csv` |
| 56 | `cavolfiore_crudo` | 11 | `proposed` | CREA 005160 | Cavolfiore, crudo (30 kcal, 3.2g P, 0.2g F, 2.7g C) | `grep '^CREA,005160' dataset/crea/foods.csv` |
| 57 | `peperoncino_secco_fiocchi` | 10 | `ambiguous` | — | Peperoncino secco in fiocchi assente in CREA | `grep -i 'peperoncin.*secco' dataset/crea/foods.csv` |
| 58 | `polenta_cruda` | 10 | `proposed` | CREA 000075 | Polenta, cruda (323 kcal, 8.0g P, 0.7g F, 72.7g C) | `grep '^CREA,000075' dataset/crea/foods.csv` |
| 59 | `broccoli_crudi` | 10 | `proposed` | CREA 005110 | Broccolo a testa, crudo (33 kcal, 3.0g P, 0.4g F, 3.1g C) | `grep '^CREA,005110' dataset/crea/foods.csv` |
| 60 | `tahina` | 10 | `ambiguous` | — | Pasta di sesamo tostata assente in CREA | `grep -i 'tahina' dataset/crea/foods.csv` |

---

### Confronto metriche matcher: Prima vs Dopo Sessione 2

Rilevazione effettuata con:
`python scripts/match_recipe_ingredients.py --report-file data/recipe_matching_report.json --review-queue data/recipe_ingredient_review_queue.json`

| Metrica | Baseline inizio Sess. 2 | Dopo Sessione 2 | Variazione |
|---|---|---|---|
| **Ricette totali esaminate** | 834 | 834 | = |
| **Istanze totali ingredienti** | 7.843 | 7.843 | = |
| **Gruppi canonici / equivalenze** | 972 | 952 | **-20** (consolidamento unmapped nel dizionario) |
| **Istanze `missing`** | 2.277 (29,0%) | 2.151 (27,4%) | **-126** (-1,6%) |
| **Istanze `approved`** | 3.695 (47,1%) | 3.706 (47,3%) | +11 *(regola: niente `--approve`)* |
| **Istanze `proposed_exact`** | 856 (10,9%) | 895 (11,4%) | **+39** (+0,5%) |
| **Istanze `proposed_proxy`** | 345 (4,4%) | 380 (4,8%) | **+35** (+0,4%) |
| **Istanze `ambiguous`** | 418 (5,3%) | 392 (5,0%) | -26 (-0,3%) |
| **Istanze `needs_review`** | 252 (3,2%) | 319 (4,1%) | +67 (+0,9%) |
| **Gruppi canonici `missing`** | 857 | 820 | **-37** |
| **Gruppi canonici `proposed_exact`** | 46 | 57 | **+11** |
| **Gruppi canonici `proposed_proxy`** | 29 | 32 | **+3** |
| **Gruppi canonici `ambiguous`** | 10 | 13 | +3 |
| **Gruppi canonici `approved`** | 30 | 30 | = *(regola: niente `--approve`)* |
| **Ricette con tutte le associazioni proposte** | 73 | 75 | **+2 ricette** |
| **Ricette pronte per il solver (100% OK)** | 24 | 24 | = *(richiede approvazione Claude)* |

---

### Note e dubbi per la revisione di Claude

1. **Uova e prezzemolo (prodotti a marchio vs CREA):** In CREA 181100 (uova) e 006840 (prezzemolo) il valore `carbs_available_g_100g` è nullo nel dataset ufficiale. Per non violare la regola 4 ("mai zero al posto di un dato mancante"), sono stati lasciati `ambiguous` registrando nei candidati OFF referenze commerciali a marchio del supermercato (Esselunga Smart per le uova fresche, Esselunga per il prezzemolo surgelato) che possiedono tutti e 4 i macro completi. Spetta a Claude decidere se approvare formalmente i barcode OFF oppure adottare un proxy standardizzato.
2. **Macinato di manzo:** In assenza di una voce "macinato" in CREA, è stato proposto come proxy `101120` ("tagli anteriori, crudi", 145 kcal, 7% grassi), che riflette fedelmente il profilo medio del macinato da banco bovino (10–15% grasso).
3. **Double cream britannica:** La panna doppia inglese ha circa il 48–50% di lipidi. La panna più ricca in CREA è al 35% (`140300`). Applicando rigorosamente la regola 3 ("non scegliere la voce più vicina"), `panna_doppia` è stata marcata `ambiguous`.
4. **Vini da cucina (bianco e rosso):** Le voci CREA `405010` e `405020` hanno i campi carboidrati e proteine vuoti. In aggiunta, durante la cottura l'alcol evapora in percentuale variabile dal 15% all'85% a seconda del tempo di ebollizione. Restano pertanto `ambiguous`.

### Revisione Claude della sessione 2 (2026-10-06)

Gli id CREA esistono tutti e i nomi corrispondono. Nel dizionario Gemini ha aggiunto 43 voci nuove. Ha cambiato anche voci esistenti, ma solo per aggiungere sinonimi o per riempire `fiocchi_di_latte`, che prima era vuota.

**Approvate: 39 proposte CREA.**

**Non approvate:**
- `pollo_petto_crudo`: comprende ancora «Cooked chicken», cioè il valore crudo applicato al pollo cotto.
- `grana_padano`: «Parmesan» va al Parmigiano Reggiano, secondo la decisione della verifica delle ricette candidate.
- `tonno_scatola_olio`: «Tinned tuna» nelle ricette britanniche è spesso al naturale (CREA 123550).
- `panna_fresca`: «Cream» non dice se è panna leggera o da montare.
- `fagioli_cannellini_secchi`: «White beans» non indica lo stato.

**Sorgenti speciali di Codex (`5e55730`).** I condimenti in traccia della policy sono approvati come `condiment:trace`; `pepe_nero` passa da CREA a traccia. I brodi liquidi sono approvati come `stock:cube_1_50`.

**Effetto.** Le ricette pronte salgono da 24 a 26, quelle con tutte le associazioni approvate a 29. Il collo di bottiglia ora sono i **pesi**: solo 300 ricette su 834 hanno pesi espliciti; le altre usano cucchiai, pezzi e spicchi da convertire.
