# Verifica delle 42 ricette candidate

Verifica del 4 ottobre 2026 su ingredienti e pesi originali, descrizioni dei riferimenti USDA riportate nelle ricette, alimenti CREA e record locali Open Food Facts. **24 adattamenti approvati, 18 sospesi**. Sono state aggiunte 23 ricette al solver: l'interfaccia contiene ora 25 composizioni (24 importate più la pasta al pomodoro dimostrativa).

Le approvazioni sono specifiche per ricetta e ingrediente, con evidenze in `config/ingredient-approved-mappings.json`; non autorizzano indiscriminatamente ogni occorrenza del nome. La verifica riguarda la coerenza del catalogo disponibile: non prova la confezione attuale, la correttezza analitica dei dati delle fonti né la conformità alle diete personali. Le differenze rispetto all'originale sono esposte nell'interfaccia e nel risultato. I nutrienti vengono ricalcolati dagli alimenti effettivamente scelti.

Correzioni principali: tonno al naturale → CREA 123550 in salamoia sgocciolato; lenticchie bollite → CREA 004505; Parmigiano → record OFF specifico anziché Grana Padano; uova e prezzemolo → record di marca con macro completi, evitando di trasformare i mancanti CREA in zero. Origano essiccato → prodotto con ingrediente e stato dichiarati; capperi → prodotto con composizione esplicita. I fiocchi di latte scremati, la mozzarella vaccina, il latte parzialmente scremato e alcuni proxy di formato sono adattamenti dichiarati. Nessun ingrediente omesso per ottenere un totale completo.

## Ricette approvate

- foodose:R048 — Aubergine and cottage cheese parmigiana
- foodose:R328 — Aubergine caponata with white beans
- foodose:R299 — Baked chicken schnitzel with green beans and lemon
- foodose:R144 — Cod and chickpea fritters
- foodose:R054 — Courgette and ricotta lasagne rolls
- foodose:R270 — Lentil and walnut bolognese with spaghetti
- foodose:R068 — Lentil and walnut ragù with pasta
- foodose:R165 — Mediterranean vegetable bread pudding
- foodose:R315 — Mozzarella, tomato and olive bread roll with basil
- foodose:R326 — Potato and ricotta gnocchi with tomato and basil
- foodose:R039 — Prawn and courgette linguine
- foodose:R143 — Prawn and rice stuffed courgettes
- foodose:R223 — Prawns with courgette, garlic and lemon spaghetti
- foodose:R100 — Roasted vegetable and mozzarella frittata sandwich
- foodose:R009 — Savoury oats with peas, eggs and Parmesan
- foodose:R057 — Tomato, mozzarella and lentil bake
- foodose:R094 — Tuna and cannellini potato bowl
- foodose:R249 — Tuna and white bean open sandwich on rye
- foodose:R323 — Tuna and white bean panzanella
- foodose:R038 — Tuna and white bean stuffed peppers
- foodose:R303 — Tuna, egg and potato salad with green beans and olives
- foodose:R044 — Tuna, tomato and olive pasta bake
- foodose:R225 — Tuna, white bean and caper salad on rye
- foodose:R064 — White bean and aubergine tomato bake

## Ricette sospese

- foodose:R191 — Chicken Waldorf-style rye sandwiches: Dati nutrizionali mancanti o non validi: fat_g_100g; Fonte indica petto arrostito, candidato CREA petto in padella: metodo e composizione non verificati.
- foodose:R105 — Chicken and mushroom baked potato: Erba cipollina non equivalente a cipolla; candidato fresco con dati completi non individuato.; Fonte indica petto arrostito, candidato CREA petto in padella: metodo e composizione non verificati.
- foodose:R198 — Chicken and pea savoury pancakes: Erba cipollina non equivalente a cipolla; candidato fresco con dati completi non individuato.; Fonte indica petto arrostito, candidato CREA petto in padella: metodo e composizione non verificati.
- foodose:R093 — Chicken and white bean open sandwich: Fonte indica petto arrostito, candidato CREA petto in padella: metodo e composizione non verificati.
- foodose:R201 — Cottage cheese and roasted pepper toasties: Peperoni arrostiti in vasetto non equivalenti a peperoni in padella: liquido di governo e olio non risolti.
- foodose:R053 — Greek-style butter beans with baked eggs: Fagioli lima/butter beans non equivalenti a cannellini; la fonte riutilizza un riferimento generico.
- unitools:chapati-kenyan — Kenyan chapati: Peso effettivo non disponibile; nessuna conversione stimata approvata.
- foodose:R061 — Lemon-herb tofu with Mediterranean rice: Peso effettivo non disponibile; nessuna conversione stimata approvata.; Prodotti al naturale proposti non dichiarano la consistenza compatta nel record; composizione/stato da confermare.
- foodose:R316 — Potato and courgette rosti with a poached egg: Erba cipollina non equivalente a cipolla; candidato fresco con dati completi non individuato.; Yogurt greco low-fat non equivalente al candidato intero; prodotto specifico ancora da verificare.
- foodose:R306 — Potato, pepper and onion tortilla: Peperoni arrostiti in vasetto non equivalenti a peperoni in padella: liquido di governo e olio non risolti.
- foodose:R174 — Red lentil and tomato pasta shells: Prodotti al naturale proposti non dichiarano la consistenza compatta nel record; composizione/stato da confermare.
- foodose:R226 — Salmon with peas, mint and yoghurt: Yogurt greco low-fat non equivalente al candidato intero; prodotto specifico ancora da verificare.
- foodose:R003 — Spinach and cottage cheese baked eggs: Erba cipollina non equivalente a cipolla; candidato fresco con dati completi non individuato.
- foodose:R134 — Turkey and fennel patties with soft carrots: Dati nutrizionali mancanti o non validi: fat_g_100g; Macinato con 7% grassi non equivalente a tacchino intero senza pelle.
- foodose:R129 — Turkey and lentil bolognese: Macinato con 7% grassi non equivalente a tacchino intero senza pelle.
- foodose:R202 — Turkey, pea and basil pasta salad: Petto cotto non equivalente al tacchino intero cotto.
- foodose:R260 — Turkey, spinach and ricotta meatloaf with tomato: Macinato con 7% grassi non equivalente a tacchino intero senza pelle.
- foodose:R021 — Turkey-stuffed peppers with herbed rice: Macinato con 7% grassi non equivalente a tacchino intero senza pelle.

## Validazione

60 test passano, incluso il controllo delle porzioni di riferimento di tutti i nuovi template, acqua pura con peso conservato e nutrienti zero, correzioni di tonno/lenticchie e distinzione tra latte intero e cereale integrale. Le 23 nuove ricette hanno anche una soluzione ottima verificata con Optees via MCP, usando bersagli ricavati dalla porzione di riferimento ricalcolata. Questo prova il modello con quei bersagli, non la fattibilità con qualunque obiettivo personale o con una dieta prescritta.

Registro ingrediente per ingrediente in `data/recipe_candidate_verification.json`; risultati Optees in `data/recipe_solver_verification.json`. Il rapporto del matcher ora conferma 24 ricette completamente approvate. Il catalogo originale resta invariato: le composizioni utilizzabili sono adattamenti separati in `config/recipe-solver.json`.
