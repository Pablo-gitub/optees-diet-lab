# Revisione dell'importatore ingredienti — 4 ottobre 2026

Lo script di Gemini `scripts/match_recipe_ingredients.py` elabora le 834 ricette offline, propone corrispondenze tramite un dizionario di 82 ingredienti e genera coda e rapporto. Non è collegato automaticamente al catalogo dei template usato dall'interfaccia.

Verifica: tutti i 44 test iniziali passavano, ma alcuni casi non erano coperti. Correzioni aggiunte:

- Le approvazioni devono avere entrambi i flag esplicitamente veri e non possono prevalere su prove di stato incompatibile nell'ingrediente effettivo: pasta cotta vs secca, prodotto fresco vs disidratato, integrale vs raffinato, olio da friggere o scartato.
- Le associazioni specifiche conservano le sostituzioni deliberate del panino già verificato; non estendono automaticamente quelle sostituzioni ad altre ricette.
- Un'associazione approvata non approva anche una quantità stimata: conversioni proposte da spicchi/pezzi/cucchiai restano non utilizzabili nell'esportazione per il calcolatore.
- L'esportazione dei template conserva URL, licenza e attribuzione della ricetta.

47 test superati dopo le correzioni. Rielaborato tutto il catalogo: 7.843 occorrenze, 1.019 gruppi; 875 associazioni riutilizzate approvate, 2.330 proposte esatte e 587 proxy, 973 ambigue, 3.034 mancanti, 44 da rivedere. Sono categorie del matcher, non certificazioni nutrizionali. 300 ricette hanno tutti i pesi risolti, 18 tutti gli ingredienti almeno proposti (include quella già approvata), una completamente approvata: foodose R315, già presente nel solver.

## Lavoro ancora necessario

Il risultato non rende le altre 833 ricette automaticamente utilizzabili. Il dizionario è limitato; 941 gruppi non riconosciuti richiedono ampliamento. La ricerca dei prodotti di marca consulta solo i barcode preconfigurati nel dizionario, non esegue una ricerca generale in tutto Open Food Facts. Ulteriori criticità da affrontare nella revisione delle proposte: ingredienti compositi raggruppati per sottostringa, lievito secco proposto come compresso, brodo liquido proposto con dado concentrato. Queste sono ancora proposte, da non approvare in blocco. La coda è organizzata per ingrediente canonico ma può contenere stati diversi: non basta approvare il nome del gruppo.

Prima di estendere l'interfaccia: controllare le 17 ulteriori ricette con tutte le associazioni proposte, validare dati e stati delle singole occorrenze, verificare formato esportato (acqua pura non ancora supportata da `plan_recipe.py`), servire solo configurazioni verificate, rispettare sostituzioni e licenze. L'approvazione dell'associazione non implica conformità alle diete personali.

```sh
python scripts/match_recipe_ingredients.py --report-file data/recipe_matching_report.json --review-queue data/recipe_ingredient_review_queue.json --export-solver /tmp/optees-matched-recipes.json
```

Questo comando non sovrascrive `config/recipe-solver.json` e non riavvia il server. Lo script dispone anche di un comando `--approve`: è un'azione di revisione esplicita, non un passaggio da eseguire automaticamente per svuotare la coda. La voce aglio nel file delle approvazioni riporta `user_review`; l'etichetta salvata da sola non prova una revisione fatta dall'utente umano.

## Seconda espansione di Gemini

Il dizionario era passato da 82 a 100 voci, con 45 ricette aventi almeno una proposta per ogni ingrediente. Le approvazioni esistenti non sono state aumentate: il solo template importato completamente approvato resta R315. Gemini ha aggiunto controlli per la diluizione dei brodi e distinto lievito fresco da secco.

La revisione ha riscontrato e corretto:

- Codice USDA 172232 duplicato tra basilico e capperi: i riferimenti delle ricette originali foodose identificano i capperi con 172238.
- Codice USDA 171077 duplicato tra pollo e tacchino: per il tacchino sono ora conservati i codici dichiarati nelle ricette originali (172850 macinato crudo, 171098 petto crudo, 171496 petto cotto). Il tacchino intero CREA rimane un proxy, non una corrispondenza esatta per tutti i tagli.
- Tofu morbido e compatto raggruppati con candidati di marca identici: separato il tofu morbido, senza riutilizzare i prodotti di quello compatto. I riferimenti originali distinguono 172449 morbido e 172475 compatto.
- Lievito madre candidato per lievito di birra secco: candidato rimosso dalla ricerca attiva e conservato come scartato nel dizionario.

Dopo le correzioni: 101 voci di dizionario, 42 ricette con tutte le associazioni almeno proposte (rispetto alle 18 precedenti), 300 con pesi risolti, una completamente approvata. 56 test del progetto passano; nessuna nuova ricetta attivata nell'interfaccia. Il rapporto e la coda sono stati rigenerati offline sull'intero catalogo.

Prossimo passaggio: revisione delle nuove proposte per ricetta e stato dell'ingrediente, validazione nutrizionale delle associazioni e solo dopo esportazione nel catalogo del solver. I contatori `proposed_exact` rimangono indicazioni del matcher, non approvazioni verificate. Gli `expected_qualifiers` aggiunti al dizionario non sono ancora applicati sistematicamente dalla ricerca: vanno controllati prima di approvare altre regole condivise.

## Correzioni dopo Fase 8 (esclusioni, tracce e brodo)

`load_approved_mappings()` legge tutti i `ingredient-proposals/batch-*.json` accanto al file di approvazioni e unisce `raw_names_excluded` per canonico (case/accenti normalizzati). Queste occorrenze sono `needs_review`, `approval_excluded:true` e non ereditano né la revisione del canonico né quella di una fonte speciale. Una revisione **specifica dell'occorrenza** resta possibile. Gli indici derivati non vengono riscritti nel file di approvazioni.

Policy versionata: `config/recipe-special-sources.json`.

- `condiment:trace`, categoria `condimento`: sale, pepe, spezie/erbe essiccate, alloro e vaniglia ammessi in traccia. **0 kcal dichiarate come approssimazione**, non un'etichetta nutrizionale a zero di tutte le spezie. Soglia euristica 2 g per ingrediente e porzione quando il peso è noto; per unità qualitative solo `toTaste`/`pinch`, oppure quantità limitate in cucchiaini o pezzi di alloro/vaniglia/cannella. Porzioni della ricetta obbligatorie per applicare questa policy. Fresco, composto, nomi esclusi e quantità superiori non si promuovono automaticamente. Il peso sconosciuto resta `grams:null`, `quantity_status:trace`; non diventa zero. Nel template solver queste occorrenze restano in `trace_condiments`, senza variabili di peso inventate, e nel calcolo compaiono nelle fonti con `declared_kcal:0`. Non viene stimato il sale/sodio.
- `stock:cube_1_50`, categoria `brodo`: proxy **liquido**, 2 g di dado CREA `503010` + 98 g di acqua per 100 g finali (1:50). I quattro nutrienti sono quelli del dado ×0,02; il dado tal quale non è più candidato per un brodo liquido, nemmeno per un'approvazione canonica errata. Densità 1 g/ml dichiarata come euristica; ml/l convertiti solo per questo liquido. Un brodo liquido specifico esplicitamente revisionato ha precedenza. Non certifica che il dado sia vegetale o di pollo, né la preparazione reale della fonte: formula e limite sono conservati nell'export. Non si interpreta automaticamente “stock cube/powder” come brodo pronto.

Matcher, `calculate_recipe_nutrients.py` e `plan_recipe.py` condividono le stesse fonti. Il solver conserva anche la traccia dei condimenti qualitativi nel risultato. La sovrapposizione del §9 esclude le categorie `condimento` e `brodo`, anche con nomi inglesi o non riconosciuti dal filtro nominale. Sono aggiunti i relativi gruppi espliciti; la compatibilità con i vincoli delle diete non viene certificata da questo passaggio.

Report rigenerato sull'intero catalogo locale: **834 ricette**, **24 pronte per il solver** (prima 24, dopo 24, nessuna nuova pronta). Le ricette con tutte le associazioni approvate passano da **24 a 26**; le due aggiuntive restano bloccate da quantità non verificate. **207 occorrenze** escluse dai batch sono fermate; fonti speciali compaiono in **412 ricette** per i condimenti e **113** per il brodo. Questi ultimi conteggi indicano copertura parziale degli ingredienti, non ricette interamente utilizzabili. Report e coda aggiornati in `data/recipe_matching_report.json` e `data/recipe_ingredient_review_queue.json`; export di verifica `/tmp/recipes-final-solver.json`.

Verifica conclusiva: **285 test verdi** con la suite completa del progetto; quattro nuove regressioni su esclusioni, tracce, diluizione ed export → calcolo → solver. Ricalcolo indipendente delle **24 ricette esportate: 24 complete**. Sistemato anche un riferimento della fixture del diario che funzionava solo di lunedì: ora il test modifica il pasto della settimana realmente applicata. `web/static/` intatto.
