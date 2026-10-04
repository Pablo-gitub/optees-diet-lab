# Prodotti confezionati venduti in Italia — Open Food Facts

Fonte: [Open Food Facts](https://world.openfoodfacts.org/data), export TSV gzip
ufficiale, filtrato in streaming per `countries_tags` contenente esattamente
`en:italy`. Tutte le marche vengono mantenute; non solo quelle richieste.
Il tag documenta la presenza nel mercato italiano secondo la fonte, non la
reperibilità attuale in uno specifico supermercato.

## File

- `products.jsonl`: record normalizzati, uno per barcode; nomi, marche,
  categorie, confezione/porzione, nutrienti, ingredienti, allergeni, controlli
  qualità e collegamento alla scheda originale.
- `raw_italy.jsonl.gz`: righe originali selezionate, conservate per verificare
  l'importazione e ripetere la normalizzazione senza scaricare tutto.
- `manifest.json`: data/ETag/hash della fonte, hash normalizzato, numero di
  prodotti e conteggi delle marche richieste e dei controlli di qualità.
- `catalog.sqlite`: indice locale opzionale generato con lo script dedicato.

I file voluminosi e l'indice SQLite sono esclusi da Git. L'export mondiale non
viene conservato: il download è filtrato senza decomprimerlo interamente su disco.
Il paese di vendita non equivale al paese di produzione. I barcode restano stringhe,
compresi eventuali zeri iniziali. L'aggiornamento deduplica per barcode e sostituisce
lo snapshot completato; non modifica i prodotti personali né i piani salvati.

## Qualità e uso nel motore

I valori sono per 100 g oppure 100 ml, non automaticamente per confezione.
La base massa/volume viene resa esplicita e resta irrisolta quando non deducibile
dall'unità della confezione. Una quantità in ml non viene convertita in grammi
senza una densità. L'energia in kcal è mantenuta; se manca e sono disponibili kJ,
viene convertita dividendo per 4,184 e marcata. Non viene calcolata dai macro.
I nutrienti mancanti restano null, i valori zero restano zero.

`numeric_candidate` indica soltanto disponibilità dei quattro nutrienti principali,
assenza di anomalie numeriche rilevate/errori segnalati dalla fonte, nome e base
massa/volume risolta: **non certifica l'etichetta**. I controlli non coprono ogni
possibile errore. Ingredienti e allergeni sono dati della fonte, non una verifica
indipendente. Il campo serving resta testo finché non viene validato.

Tutti i prodotti hanno inizialmente `solver_eligible: false` e
`diet_mapping_status: unreviewed`. Prima di usare un prodotto in un abbinamento,
serve associare ingredienti e stato crudo/cotto a un gruppo ammesso. Una pasta
semplice e una pasta con sugo non diventano intercambiabili solo perché hanno
la stessa marca o una categoria simile. Il nuovo catalogo è separato da CREA;
non cambia automaticamente gli abbinamenti né i valori inseriti dalle etichette
personali dell'utente. Nutrimenti e ricette possono cambiare nel tempo.

## Aggiornamento

```sh
python scripts/import_open_food_facts.py
python scripts/build_branded_catalog.py
python scripts/build_branded_catalog.py --search 'Barilla'
```

Opzionalmente `--input /percorso/export.tsv.gz` per un export già sul disco.
La normalizzazione può essere ricostruita dalle righe originali conservate.

## Attribuzione e licenza

Database: © Open Food Facts contributors, [ODbL 1.0](https://opendatacommons.org/licenses/odbl/1-0/).
Contenuti individuali: [DbCL 1.0](https://opendatacommons.org/licenses/dbcl/1-0/).
Questo estratto e la sua normalizzazione mantengono la licenza del database e
l'attribuzione alla fonte; non vengono scaricate immagini dei prodotti.
Documentazione: [API e riutilizzo](https://openfoodfacts.github.io/openfoodfacts-server/api/).
