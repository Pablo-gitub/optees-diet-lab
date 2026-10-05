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
