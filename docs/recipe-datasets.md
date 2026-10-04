# Ricerca database ricette — 3 ottobre 2026

## Scelta proposta

Primo test con foodose; UniTools come possibile complemento per procedimenti e varietà. Nutrienti importati con fonte USDA distinta da CREA; ricalcolo CREA solo dopo mapping verificato. Dal 4 ottobre 2026 entrambi sono importati nel catalogo offline e consultabili nell’app; non entrano ancora nel solver.

| Fonte primaria | Dimensione dichiarata | Licenza dichiarata | Valutazione |
| --- | --- | --- | --- |
| [foodose](https://www.foodose.co/glp1-recipes/nutrition-data) | 333 ricette, 2.439 righe ingredienti | CC BY 4.0 | Grammi, ID USDA e nutrienti per porzione; tempi stimati e ricette non ancora cucinate. Procedimenti sulle pagine, non nei CSV. Catalogo orientato GLP-1: non adottarne automaticamente obiettivi o raccomandazioni. |
| [UniTools](https://github.com/farcrak/unitools-recipes) | 501 ricette | CC BY-SA 4.0 | JSON con procedimenti EN/RU e macro; unità miste e quantità mancanti. Nessun mapping CREA/USDA nel campione. Media con licenze separate. |
| [Weighed-Meal Reference Set](https://dietaryassessmentinitiative.org/datasets/weighed-meal-reference-set-180/) | 180 pasti | CC BY 4.0 per tabelle | Schema promettente, ma nessun link diretto ai file individuato nella pagina o nell'indice. Download non verificato. |
| [RecipeNLG](https://github.com/Glorf/recipenlg) | 2.231.142 ricette | Condizioni dataset da verificare separatamente dal codice | Corpus testuale: parsing e normalizzazione aumentano il lavoro. Non primo import. |
| [Nutrition5k](https://github.com/google-research-datasets/Nutrition5k) | 5.006 piatti | CC BY 4.0 | Utile per validazione nutrizionale; non un ricettario con procedimenti. Scaricare eventualmente solo metadata, non archivio multimediale. |

## Verifiche concrete

Download dei due CSV foodose riusciti: 114.764 e 266.372 byte; conteggi effettivi 333 e 2.439. Intestazioni confermano porzioni, macro, grammi della ricetta intera e ID FDC. Questa verifica riguarda disponibilità e struttura, non correttezza dei calcoli.

- [recipes.csv](https://www.foodose.co/glp1-recipes/nutrition-data/recipes.csv)
- [ingredients.csv](https://www.foodose.co/glp1-recipes/nutrition-data/ingredients.csv)

UniTools: campione JSON pubblico esaminato; download dal sito ha restituito HTTP 403 allo script. Il repository dichiara copie complete versionabili, da usare come alternativa dopo verifica.

## Primo import da implementare

Conservare originali e hash; verificare chiavi e collegamenti; distinguere mancanti, acqua e tracce; conservare nutrienti dichiarati senza trattarli come misure di laboratorio. Selezionare 20–30 ricette pratiche per testare porzioni e pianificazione, lasciando il catalogo intero consultabile. Mapping CREA e traduzione italiana sono passaggi successivi, non prerequisiti per testare la selezione di ricette con macro dichiarati.

## Implementazione del 4 ottobre 2026

Importate 501 ricette UniTools dal repository e 333 foodose, per 834 record con fonte distinta. Il catalogo include 81 Italian e 6 Chinese. Interfaccia con ricerca, filtro cucina, preferenze separate per profilo e filtro delle preferite. Importatore, provenienza e ricalcolo esplicito dei nutrienti descritti in [dataset/recipes/README.md](../dataset/recipes/README.md). Le associazioni ingredienti–alimenti reali e l’integrazione nel solver restano da completare.
