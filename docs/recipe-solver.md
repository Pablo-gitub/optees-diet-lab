# Solver delle ricette

Disponibile nella pagina **Ricette → Adatta ingredienti e porzione**. Calcola un singolo piatto, scegliendo un prodotto per ingrediente e i grammi da utilizzare. Le prove sono salvate separatamente per utente e non sostituiscono i piani pranzo/cena.

## Modello

MILP eseguito tramite MCP Optees `milp.linear`, con validazione del problema e della soluzione. Variabili binarie per scegliere un solo prodotto per ingrediente, continue per grammi e dimensione della porzione. Per un ingrediente con quantità di riferimento `b`, fattore porzione `s` e flessibilità `f`:

`b × s × (1 − f) ≤ grammi ≤ b × s × (1 + f)`.

Default: ±10% (interfaccia 0–20%), porzione da 0,5 a 1,8 volte il riferimento (limiti consentiti 0,25–3). Flessibilità zero mantiene tutte le proporzioni. Le quantità sono della parte edibile nello stato indicato, non del piatto dopo cottura. Si assume consumo completo, senza inventare perdite o resa finale.

Gli intervalli nutrizionali sono vincoli rigidi. Primo obiettivo: somma degli scarti assoluti dal bersaglio, normalizzati per i rispettivi bersagli. Secondo calcolo: mantenere il miglior valore nutrizionale entro tolleranza numerica 1e-7 e minimizzare gli scarti dalle proporzioni. Se il primo risultato è soltanto feasible, non viene dichiarato ottimo; il secondo passaggio non parte. Se il secondo passaggio non trova soluzione, rimane la prima soluzione verificata. Non è ancora Pareto, Min-Max o bandit.

Nessun rilassamento automatico dei limiti quando il problema è impossibile. Quantità, binarie e tutti i vincoli sono ricontrollati sul risultato numerico non arrotondato prima di mostrare la proposta. I grammi visualizzati sono arrotondati a due decimali; nutrienti calcolati sui valori originali.

## Associazioni disponibili

Configurazione estendibile in `config/recipe-solver.json`, separata dal catalogo importato:

- Pasta al pomodoro dimostrativa: 80 g pasta secca, 150 g passata, 10 g olio EVO, 5 g basilico come porzione di riferimento. Pasta generica CREA oppure spaghetto quadrato integrale La Molisana, barcode **8004690611517**. Il prodotto è identificato dal record offline, non dalla verifica della confezione attuale; non coincide con lo spaghetto numero uno citato come esempio dall'utente.
- Adattamento **foodose R315**, panino con mozzarella, pomodoro, olive e basilico: pesi originali per porzione, alimenti CREA, pane generico come proxy del panino. [Fonte foodose](https://www.foodose.co/glp1-recipes/mozzarella-tomato-olive-bread-roll-basil), CC BY 4.0; il collegamento esatto alla fonte è conservato nel catalogo originale e nella configurazione.

Ogni candidato ha fonte/ID, revisione esplicita e stato crudo/cotto controllato. I valori per 100 ml o con base incerta, nutrienti mancanti ed errori di qualità vengono esclusi. Le esclusioni CREA del profilo e le selezioni dei prodotti disponibili sono rispettate. Disabilitare tutti i candidati di un ingrediente blocca il calcolo, senza rimuoverlo dalla ricetta.

Il catalogo delle 834 ricette rimane consultabile: l'abilitazione nel solver richiede queste associazioni per tutti gli ingredienti. Non si assegna automaticamente il primo alimento trovato dal nome. Per estenderlo si aggiunge una configurazione esplicita, conservando la provenienza e indicando le sostituzioni.

## Limiti di questa fase

Obiettivi del singolo piatto dimostrativi, modificabili nell'interfaccia; non derivati automaticamente da un fabbisogno personale. Nessuna verifica ancora degli abbinamenti delle diete sedentaria/palestra, delle allergie o dell'intera giornata. La modalità dieta del profilo non rende una prova di ricetta conforme a quella dieta. Ricette e quantità non sono inserite automaticamente nel piano scelto. Le preferenze di cucina filtrano il catalogo, ma non cambiano l'obiettivo numerico di questa prova.

## Esecuzione e verifica

```sh
/home/paolo/anaconda3/envs/optees/bin/python scripts/plan_recipe.py --config config/demo-recipe.json --output /tmp/recipe-result.json
```

Prova reale Optees del 4 ottobre 2026: soluzione ottima con La Molisana 93,03 g, passata 142,72 g, olio 9,55 g, basilico 4,76 g; 446,1947 kcal, 15,9577 g proteine, 12 g grassi, 65 g carboidrati. Tutti gli intervalli e le proporzioni rispettati.

33 test complessivi: includono scelta di prodotti diversa al cambiare dell'obiettivo, flessibilità zero, controllo dei due obiettivi, infeasibilità, esclusioni, dati mancanti, risultati non verificati e isolamento dello storico delle ricette. Verifica anche del pulsante web con MCP Optees.

## Copertura dopo la verifica delle candidate

Disponibili 24 ricette importate come adattamenti documentati più il piatto dimostrativo. Verifica completa delle 42 candidate, correzioni e casi sospesi in [recipe-candidate-verification.md](recipe-candidate-verification.md). La sezione precedente con due composizioni descrive il primo avvio; la copertura attuale è 25 composizioni.

### Prodotti di marca prioritari

Le composizioni usano `product_policy: branded_first`: per ogni ingrediente il solver confronta prima tutte le alternative Open Food Facts revisionate e utilizzabili. CREA viene utilizzato solo se non rimane nessun prodotto di marca utilizzabile per quell’ingrediente, anche dopo le esclusioni. Non si torna a CREA per rendere fattibile un obiettivo quando sono disponibili prodotti di marca: in quel caso la soluzione può risultare impossibile.

Prima estensione: 41 associazioni aggiunte, 11 prodotti distinti, 12 ricette. Include spaghetti Barilla e La Molisana, linguine Garofalo e Carrefour, sfoglie Barilla senza uovo, passate Mutti e Del Monte, ricotte Galbani e mozzarella Santa Lucia. Le associazioni sono revisionate sul catalogo locale (ingredienti, formato/stato e nutrienti completi per 100 g), non sulla confezione attuale. Il registro è `data/recipe_branded_mappings.json`.

Gli ingredienti freschi senza prodotto compatibile restano generici. Gli oli con etichetta per 100 ml non vengono trattati come valori per 100 g: occorre una densità verificata. I nutrienti di riferimento della precedente revisione sono storici; il risultato del solver è sempre ricalcolato sui prodotti selezionati. La conformità alle diete personali resta da verificare.

CREA è un database italiano di composizione degli alimenti, non una marca commerciale. È il riferimento generico per alimenti sfusi o privi di etichetta (verdura, carne, pesce, ecc.). Per un prodotto confezionato identificabile, inclusi uova e olio, si preferiscono i dati del prodotto di marca se completi e compatibili con stato e unità di misura.

È ora disponibile il [controllo strutturale degli abbinamenti](recipe-diet-compatibility.md) nella pagina Ricette. Verifica ingredienti e gruppi dei rami modellati, senza approvare le quantità o inserire il piatto nel piano giornaliero.
