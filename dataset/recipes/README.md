# Catalogo ricette offline

Importazione del 4 ottobre 2026: **834 ricette**, di cui 81 con etichetta Italian e 6 Chinese. Le altre etichette includono cucine nazionali e regionali; East Asian resta distinta da Chinese. Varianti dello stesso piatto da fonti diverse non sono deduplicate automaticamente.

## Fonti e attribuzione

- **UniTools — theunitools.com**: 501 ricette, ingredienti e procedimenti EN/RU, [repository](https://github.com/farcrak/unitools-recipes), [pagina dati](https://theunitools.com/en/data). Contenuti sotto **CC BY-SA 4.0**, testo originale della licenza in `unitools/LICENSE`. La normalizzazione modifica struttura, identificativi e unità esplicite; mantiene questa licenza per i contenuti derivati UniTools. Nessuna immagine importata.
- **foodose**: 333 ricette e 2.439 righe ingredienti, [pagina dati e licenza](https://www.foodose.co/glp1-recipes/nutrition-data), **CC BY 4.0**. CSV originali in `foodose/raw`. Normalizzazione di struttura, identificativi e quantità; procedimenti consultabili sulle pagine originali, non inclusi nei CSV. Il progetto non adotta le raccomandazioni GLP-1 del sito.

Ogni record conserva fonte, licenza e URL. Le licenze delle due fonti restano distinte; l'indice aggregato non riassegna una licenza unica a tutti i contenuti. I manifest conservano URL, hash SHA-256, conteggi e provenienza.

## Rigenerazione

```sh
python scripts/import_recipes.py --download
```

Senza `--download`, ricostruisce JSONL normalizzati e `catalog.sqlite` dagli originali locali. Questo passaggio serve anche dopo un checkout pulito, perché SQLite è escluso da Git. Il catalogo web usa l'indice locale e non invia preferenze ai siti delle fonti.

## Nutrienti e associazione agli alimenti

I valori per porzione importati sono **dichiarati dalla fonte**, non misurazioni né valori ricalcolati sui nostri alimenti. Tutte le ricette partono con `solver_eligible=false`. Solo 300 ricette foodose hanno tutti i pesi espliciti; nessuna UniTools li ha tutti, per unità come cucchiai, pezzi e sale a piacere.

`scripts/calculate_recipe_nutrients.py` ricalcola kcal e macro per ricetta intera e porzione da associazioni verificate a CREA o a un codice a barre Open Food Facts. Il file JSON di mapping usa le chiavi degli ingredienti, ad esempio:

```json
{"0": {"source": "CREA", "id": "CODICE_VERIFICATO", "reviewed": true, "state_checked": true, "grams_override": 100}}
```

```sh
python scripts/calculate_recipe_nutrients.py ID_RICETTA --mapping mapping.json
```

Verificare alimento e stato crudo/cotto; `grams_override` indica grammi dell'intera ricetta. Per prodotti con valori per 100 ml serve `density_g_per_ml`. L'acqua pura può avere fonte `water` dopo verifica esplicita. Mancanti e quantità non convertite non valgono zero: il calcolo incompleto viene segnalato. Non vengono inferite perdite di cottura, assorbimento dell'olio o resa finale.

L'associazione dei record reali è gestita tramite pipeline offline (`scripts/match_recipe_ingredients.py`) che normalizza gli ingredienti mediante `config/ingredient-dictionary.json` e propone candidati CREA e Open Food Facts, mantenendo `reviewed: false` fino a verifica umana registrata in `config/ingredient-approved-mappings.json`. Solo le ricette con il 100% degli ingredienti approvati e pesi risolti possono essere ammesse al solver (`--export-solver config/recipe-solver.json`).

## Associazione illustrativa immagini ricette

Le immagini associate alle ricette hanno scopo esclusivamente **illustrativo**, poiché porzioni, ingredienti e presentazione reale possono differire dal piatto cucinato.

Lo script `scripts/associate_recipe_images.py` permette di ricercare immagini aperte su Wikimedia Commons a partire dal titolo della ricetta, memorizzando in `config/recipe-images.json`:
- URL immagine e thumbnail (rispettando il User-Agent e le policy Wikimedia Commons)
- Autore / artista originale (con pulizia dei tag HTML)
- Fonte della pagina file (`source_url`)
- Licenza open verificata (CC BY, CC BY-SA, Public Domain, ecc.)
- Flag `illustrative: true` e disclaimer esplicito

```sh
# Modalità sicura offline (mostra candidati già salvati o salta senza rete)
python scripts/associate_recipe_images.py

# Query a Wikimedia Commons (richiede accesso alla rete)
python scripts/associate_recipe_images.py --online --limit 10
```

