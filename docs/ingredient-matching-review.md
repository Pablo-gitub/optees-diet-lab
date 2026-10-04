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
