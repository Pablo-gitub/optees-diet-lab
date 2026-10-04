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
