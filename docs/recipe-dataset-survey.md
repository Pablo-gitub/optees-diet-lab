# Ricognizione Dataset di Ricette — Ottobre 2026

Indagine comparativa di dataset di ricette culinarie con particolare attenzione a:
1. Ricette **italiane / mediterranee** con **dosi in grammi**.
2. Ricette **asiatiche (cinesi, giapponesi, thailandesi)** con **dosi in grammi**.

Ogni candidato è stato verificato aprendo direttamente URL, API o dump di dati ed eseguendo un campionamento casuale uniforme di **30 ricette** per misurare empiricamente la percentuale di ingredienti con peso in grammi, la presenza di porzioni e la disponibilità di fotografie con relativa licenza d'uso.

---

## 1. Quadro di Sintesi Comparativo

| Candidato | N. Ricette | Lingua | Formato | Licenza Dichiarata | Uso Privato | Redistribuzione | % Ingr. con Grammi (Campione 30) | Porzioni (Campione 30) | Foto e Licenza (Campione 30) | Idoneità al Progetto |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **it.wikibooks «Libro di cucina»** | 768 | Italiano | MediaWiki API / Dump XML | [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/deed.it) / [GFDL](https://it.wikibooks.org/wiki/Wikibooks:Copyright) | **Sì** | **Sì** (ShareAlike) | **27.4%** (59/215) | 76.7% (23/30) | 10.0% (3/30) — [Wikimedia Commons](https://commons.wikimedia.org/) (PD, CC BY-SA) | **Buona** (fonte aperta primaria per cucina italiana, dosi miste) |
| **en.wikibooks «Cookbook» (Cina, Giappone, Thai)** | 104 (29 ZH, 38 JP, 37 TH) | Inglese | MediaWiki API / Dump XML | [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/) / [GFDL](https://en.wikibooks.org/wiki/Wikibooks:Copyright) | **Sì** | **Sì** (ShareAlike) | **8.0%** (23/288) | 56.7% (17/30) | 13.3% (4/30) — [Wikimedia Commons](https://commons.wikimedia.org/) (CC BY-SA) | **Moderata** (legale, ma dosi prevalentemente imperiali/volumetriche) |
| **RecipeNLG** | 2.231.142 | Inglese | Dump Parquet / CSV | Proprietà accademica ([Poznań Univ. of Tech.](https://recipenlg.cs.put.poznan.pl/)) | **Sì** (ricerca) | **No** (proibita) | **0.0%** (0/245) | 10.0% (3/30 accidentali) | 0.0% (nessuna foto) | **Inadatto** (licenza restrittiva, 100% dosi imperiali, niente porzioni) |
| **Food.com / Kaggle** | ~231.637 (shuyangli94) / ~522.517 (irkaal) | Inglese | Dump CSV / Parquet | Copyright © Original Authors / Scripps Networks | Tollerato | **No** (copyright proprietario) | **0.0%** (0/267) | 73.3% (22/30) | 23.3% (7/30) — Proprietà Scripps, no licenza libera | **Inadatto** (copyright restrittivo, 0 grammi espliciti, solo unità imperiali) |
| **Zenodo 7265253** (*Italian gastronomic recipes*) | 900 | IT/EN | Dump RAR (CSV, XLSX) | Dichiarata [CC BY 4.0](https://doi.org/10.5281/zenodo.7265253), ma fonte GialloZafferano | Viziato | **No** (derivato da scrape vietato) | **0.0%** (0 grammi; W è peso ordinale 1-5) | 0.0% (nessun campo) | 0.0% (nessuna foto) | **Escluso** (nessun grammo, origine illecita) |
| **HuggingFace `KanuSaru/italian-recipes`** | 5.939 | Italiano | CSV / Parquet | [Unlicensed](https://huggingface.co/datasets/KanuSaru/italian-recipes) (Scrape GialloZafferano) | Viziato | **No** (violazione ToS GZ) | 60.0% (192/320) | 100.0% (30/30) | 0.0% (solo link web) | **Escluso** (violazione ToS Mondadori Media) |
| **foodose** (già a catalogo) | 333 | Inglese | CSV | [CC BY 4.0](https://www.foodose.co/glp1-recipes/nutrition-data) | **Sì** | **Sì** | **90.1%** ricette con 100% grammi | 100.0% | 0.0% nei CSV | **Già integrato** (eccellente per grammi, limitato per varietà regionale) |
| **UniTools** (già a catalogo) | 501 | EN / RU | JSON / Git | [CC BY-SA 4.0](https://github.com/farcrak/unitools-recipes) | **Sì** | **Sì** | 0 ricette con 100% grammi | 100.0% | Foto con licenze miste separate | **Già integrato** (ottimi procedimenti, richiede mapping di conversione unità) |
| **Pellegrino Artusi (Wikisource)** | 790 | Italiano (letterario) | MediaWiki API / Testo | [Pubblico Dominio](https://it.wikisource.org/wiki/La_scienza_in_cucina_e_l%27arte_di_mangiar_bene_(1895)) (1891) | **Sì** | **Sì** | ~40-50% grammi/etti | Riferito a commensali | Nessuna foto d'epoca | **Candidato speciale** (storico, non strutturato, richiede parsing NLP) |

---

## 2. Analisi Dettagliata dei Singoli Candidati

### 2.1 it.wikibooks «Libro di cucina»

- **URL verificato:** [https://it.wikibooks.org/wiki/Libro_di_cucina](https://it.wikibooks.org/wiki/Libro_di_cucina)
  - API endpoint: [https://it.wikibooks.org/w/api.php](https://it.wikibooks.org/w/api.php)
  - Dump completi XML/SQL: [https://dumps.wikimedia.org/itwikibooks/](https://dumps.wikimedia.org/itwikibooks/)
- **Licenza esatta:** Creative Commons Attribuzione - Condividi allo stesso modo 4.0 Internazionale ([CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/deed.it)) e GNU Free Documentation License ([GFDL](https://it.wikibooks.org/wiki/Wikibooks:Copyright)).
  - **Uso privato:** Sì, senza restrizioni.
  - **Redistribuzione:** Sì, a condizione di citare la fonte e mantenere la stessa licenza ShareAlike.
- **Numero di ricette:** **768 ricette attive** individuate sotto il prefisso `Libro di cucina/Ricette/` (escluse le pagine indice e tassonomiche).
- **Lingua:** Italiano.
- **Formato:** MediaWiki API (formato JSON, testo sorgente in Wikitext/HTML), oppure dump scaricabili `itwikibooks-latest-pages-articles.xml.bz2`.
- **Presenza porzioni:** **76.7%** (23 ricette su 30 nel campione contengono esplicitamente le porzioni o il numero di persone).
- **Presenza foto e licenza:** **10.0%** (3 su 30). Le immagini sono ospitate su [Wikimedia Commons](https://commons.wikimedia.org/) con licenze libere verificate (es. *Public Domain*, *CC BY-SA 3.0*, *CC BY-SA 2.5*).
- **Misurazione Dosi in Grammi (Campione Casuale di 30 Ricette, seed 42):**
  - Ingredienti totali esaminati: **215**
  - Ingredienti con peso esplicito in grammi o multipli (`g`, `gr`, `grammi`, `kg`, `etti`, `hg`): **59** (**27.4%**)
  - Cause principali delle dosi non in grammi: forte presenza di ingredienti a pezzi (es. "2 uova", "4 carciofi"), volumi domestici ("1 cucchiaio d'olio", "un bicchiere di vino", "un pizzico di sale") o senza dose ("q.b.").

#### Dettaglio del campione di 30 ricette (it.wikibooks):

| ID Pagina | Titolo Ricetta | Ingr. Totali | Ingr. in Grammi (%) | Porzioni | Immagini Presenti (Wikimedia Commons) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **31238** | Libro di cucina/Ricette/Bacio pantesco | 10 | 4 (40%) | No | Nessuna |
| **22681** | Libro di cucina/Ricette/Bagna càuda | 5 | 2 (40%) | Sì | `File:Bagna cauda1.jpg` (Public domain) |
| **43195** | Libro di cucina/Ricette/Bagnet verd senz'aglio | 15 | 0 (0%) | Sì | Nessuna |
| **27189** | Libro di cucina/Ricette/Barbotta | 9 | 3 (33%) | No | Nessuna |
| **32098** | Libro di cucina/Ricette/Calamari fritti | 5 | 2 (40%) | Sì | Nessuna |
| **8654** | Libro di cucina/Ricette/Canalini innamorati del mare | 7 | 3 (43%) | Sì | Nessuna |
| **30912** | Libro di cucina/Ricette/Cannelloni ripieni con soia | 21 | 6 (29%) | Sì | Nessuna |
| **8871** | Libro di cucina/Ricette/Carpaccio di salmone al profumo di aneto | 8 | 1 (12%) | Sì | Nessuna |
| **9670** | Libro di cucina/Ricette/Ciambelle e san bastiano | 9 | 4 (44%) | No | Nessuna |
| **20089** | Libro di cucina/Ricette/Cuscus | 0 (stub narrativo) | 0 (0%) | No | `File:Couscous of Fes.JPG` (CC BY-SA 3.0) |
| **27209** | Libro di cucina/Ricette/Fideuá | 14 | 0 (0%) | Sì | Nessuna |
| **21712** | Libro di cucina/Ricette/Flamenquin de jambon | 5 | 0 (0%) | No | Nessuna |
| **18050** | Libro di cucina/Ricette/Fonduta al castelmagno | 3 | 2 (67%) | Sì | Nessuna |
| **4798** | Libro di cucina/Ricette/Frittata con gli asparagi | 2 | 1 (50%) | Sì | Nessuna |
| **42268** | Libro di cucina/Ricette/Gnocchi al pesto genovese | 5 | 3 (60%) | Sì | Nessuna |
| **3885** | Libro di cucina/Ricette/Patate sabbiose | 7 | 1 (14%) | Sì | Nessuna |
| **5558** | Libro di cucina/Ricette/Pavesini con cocco e Nutella | 4 | 0 (0%) | Sì | Nessuna |
| **8411** | Libro di cucina/Ricette/Ragù di cavallo | 8 | 4 (50%) | Sì | Nessuna |
| **26597** | Libro di cucina/Ricette/Roto di Carpino | 6 | 2 (33%) | Sì | Nessuna |
| **5946** | Libro di cucina/Ricette/Salsa di acciughe | 3 | 0 (0%) | Sì | Nessuna |
| **8697** | Libro di cucina/Ricette/Seitan con patate | 4 | 1 (25%) | Sì | Nessuna |
| **21278** | Libro di cucina/Ricette/Shashlik | 0 (stub narrativo) | 0 (0%) | No | `File:Shashlyk1.jpg` (CC BY-SA 2.5) |
| **5668** | Libro di cucina/Ricette/Tacchino all'olandese | 9 | 2 (22%) | Sì | Nessuna |
| **26900** | Libro di cucina/Ricette/Tartufi al cioccolato | 5 | 2 (40%) | No | Nessuna |
| **5458** | Libro di cucina/Ricette/Torta con i cicoli | 5 | 1 (20%) | Sì | Nessuna |
| **30728** | Libro di cucina/Ricette/Torta stella di Natale | 19 | 5 (26%) | Sì | Nessuna |
| **42581** | Libro di cucina/Ricette/Tronco al caffè | 9 | 4 (44%) | Sì | Nessuna |
| **12458** | Libro di cucina/Ricette/Zucchini ripieni di carne | 4 | 0 (0%) | Sì | Nessuna |
| **5598** | Libro di cucina/Ricette/Zuppa d'orzo | 10 | 3 (30%) | Sì | Nessuna |
| **26609** | Libro di cucina/Ricette/Zuppa di Carpino | 4 | 3 (75%) | Sì | Nessuna |

---

### 2.2 en.wikibooks «Cookbook» (Cucina Cinese, Giapponese, Thailandese)

- **URL verificato:** [https://en.wikibooks.org/wiki/Cookbook:Table_of_Contents](https://en.wikibooks.org/wiki/Cookbook:Table_of_Contents)
  - Categoria Cinese: [https://en.wikibooks.org/wiki/Category:Chinese_recipes](https://en.wikibooks.org/wiki/Category:Chinese_recipes)
  - Categoria Giapponese: [https://en.wikibooks.org/wiki/Category:Japanese_recipes](https://en.wikibooks.org/wiki/Category:Japanese_recipes)
  - Categoria Thailandese: [https://en.wikibooks.org/wiki/Category:Thai_recipes](https://en.wikibooks.org/wiki/Category:Thai_recipes)
- **Licenza esatta:** Creative Commons Attribution-ShareAlike 4.0 International ([CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/)) e GFDL ([Wikibooks:Copyright](https://en.wikibooks.org/wiki/Wikibooks:Copyright)).
  - **Uso privato:** Sì.
  - **Redistribuzione:** Sì, con attribuzione e licenza ShareAlike identica.
- **Numero di ricette:** **104 ricette** verificate nel namespace Cookbook:
  - Cinesi: 29 ricette
  - Giapponesi: 38 ricette
  - Thailandesi: 37 ricette
- **Lingua:** Inglese.
- **Formato:** MediaWiki API (JSON/wikitext), HTML, dump XML.
- **Presenza porzioni:** **56.7%** (17 ricette su 30 contengono il parametro `servings` o `yield`).
- **Presenza foto e licenza:** **13.3%** (4 ricette su 30). Immagini presenti su Wikimedia Commons sotto licenze libere (es. CC BY-SA 2.0/3.0 o CC0).
- **Misurazione Dosi in Grammi (Campione Bilanciato di 30 Ricette: 10 ZH, 10 JP, 10 TH, seed 42):**
  - Ingredienti totali esaminati: **288**
  - Ingredienti con peso esplicito in grammi/kg: **23** (**8.0%**)
  - Cause della bassa percentuale: I ricettari in lingua inglese adottano sistematicamente il sistema imperiale statunitense o misure volumetriche di cucina (*cups*, *tbsp*, *tsp*, *ounces*, *pieces*). I grammi compaiono solo sporadicamente quando un contributore inserisce tabelle di conversione ponderale (es. nella ricetta del *Baozi*).

#### Dettaglio del campione di 30 ricette (en.wikibooks):

| ID Pagina | Cucina | Titolo Ricetta | Ingr. Totali | Ingr. in Grammi (%) | Porzioni | Immagini Presenti (Wikimedia Commons) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **24098** | Giapponese | Cookbook:Agedashi Tofu | 9 | 0 (0%) | No | Nessuna |
| **120825** | Cinese | Cookbook:Baozi (Steamed Yeasted Dumplings) | 8 | 5 (62%) | Sì | Nessuna |
| **200783** | Giapponese | Cookbook:Beef Yakiniku Pizza | 18 | 3 (17%) | Sì | Nessuna |
| **56592** | Cinese | Cookbook:Cantonese Roast Duck | 8 | 0 (0%) | No | Nessuna |
| **30168** | Giapponese | Cookbook:Carrots Cooked Kinpira Style | 4 | 1 (25%) | No | Nessuna |
| **120785** | Cinese | Cookbook:Char Siu (Chinese BBQ pork) | 8 | 0 (0%) | Sì | Nessuna |
| **22344** | Giapponese | Cookbook:Dashi (Japanese Soup Stock) | 8 | 0 (0%) | Sì | Nessuna |
| **21757** | Cinese | Cookbook:Egg Roll | 13 | 0 (0%) | No | `File:CookbookEggrollFilling.jpg`, `File:CookbookEggrollFirstFold.jpg` |
| **26355** | Cinese | Cookbook:Fried Corn | 8 | 0 (0%) | No | Nessuna |
| **371258** | Thai | Cookbook:Khanom Salim | 12 | 4 (33%) | Sì | Nessuna |
| **38175** | Giapponese | Cookbook:Meat and Shrimp Potstickers | 14 | 0 (0%) | Sì | Nessuna |
| **20904** | Giapponese | Cookbook:Miso Soup | 8 | 0 (0%) | No | `File:Miso Soup 001.jpg` |
| **371717** | Thai | Cookbook:Nam Phrik Ong | 10 | 1 (10%) | No | Nessuna |
| **282629** | Giapponese | Cookbook:Natto (Japanese Fermented Soybeans) | 7 | 0 (0%) | Sì | Nessuna |
| **14077** | Giapponese | Cookbook:Onigiri | 8 | 0 (0%) | Sì | `File:Onigiri by yomi955.jpg` |
| **17921** | Thai | Cookbook:Pad Thai | 16 | 2 (12%) | Sì | `File:SamedFEB10 - 102.JPG` |
| **4347** | Thai | Cookbook:Peanut Curry Sauce | 6 | 0 (0%) | Sì | Nessuna |
| **291017** | Cinese | Cookbook:Pot Stickers | 2 | 0 (0%) | No | Nessuna |
| **190214** | Cinese | Cookbook:Shark Fin Soup | 13 | 2 (15%) | Sì | Nessuna |
| **26047** | Cinese | Cookbook:Steamed Buns with BBQ Pork | 16 | 1 (6%) | Sì | Nessuna |
| **415698** | Cinese | Cookbook:Steamed Tuna Bao Buns | 18 | 0 (0%) | No | Nessuna |
| **145660** | Giapponese | Cookbook:Sukiyaki | 11 | 0 (0%) | No | Nessuna |
| **123460** | Cinese | Cookbook:Taro Fish | 9 | 0 (0%) | Sì | Nessuna |
| **159190** | Thai | Cookbook:Thai Lemonade | 6 | 0 (0%) | Sì | Nessuna |
| **447456** | Thai | Cookbook:Thai Peanut Fried Rice | 12 | 0 (0%) | No | Nessuna |
| **136641** | Thai | Cookbook:Thai Red Curry Paste | 9 | 0 (0%) | Sì | Nessuna |
| **56158** | Thai | Cookbook:Thai Rice Balls in Coconut Milk | 6 | 1 (17%) | Sì | Nessuna |
| **134187** | Thai | Cookbook:Tom Yum Gai | 10 | 1 (10%) | Sì | Nessuna |
| **372276** | Thai | Cookbook:Tub Tim Krob | 5 | 0 (0%) | No | Nessuna |
| **400036** | Giapponese | Cookbook:Yubeshi | 6 | 2 (33%) | No | Nessuna |

---

### 2.3 RecipeNLG

- **URL verificato:** [https://recipenlg.cs.put.poznan.pl/](https://recipenlg.cs.put.poznan.pl/)
  - Repository GitHub del codice: [https://github.com/Glorf/recipenlg](https://github.com/Glorf/recipenlg)
  - Dataset card Hugging Face: [https://huggingface.co/datasets/mbien/recipe_nlg](https://huggingface.co/datasets/mbien/recipe_nlg)
  - Pubblicazione ACL INLG 2020: [https://www.aclweb.org/anthology/2020.inlg-1.4/](https://www.aclweb.org/anthology/2020.inlg-1.4/)
- **Licenza esatta:** Licenza accademica personalizzata restrittiva ([Poznań University of Technology Agreement](https://huggingface.co/datasets/mbien/recipe_nlg)):
  - Testo clausola 1: *"Researcher shall use the Dataset only for non-commercial research and educational purposes."*
  - Testo clausola 3: L'utente solleva l'università da ogni responsabilità per violazione del copyright sui testi originali estratti dal web (scraping di Recipe1M, cookbooks.com, ecc.).
  - **Uso privato:** Consentito esclusivamente per studio/ricerca accademica non commerciale.
  - **Redistribuzione:** **NON consentita**. Proibita la redistribuzione a terzi o l'incorporazione in software commerciale/aperto non accademico.
- **Numero di ricette:** **2.231.142 ricette** (circa 1,6 milioni ottenute con scraping diretto "Gathered", il resto derivato da Recipe1M+).
- **Lingua:** Inglese monolingue.
- **Formato:** Dump tabellare compresso (CSV / Parquet di 2.19 GB).
- **Presenza porzioni:** **Nessun campo strutturato** per le porzioni (`servings` è assente dallo schema `[id, title, ingredients, directions, link, source, ner]`). Solo nel **10.0%** (3 su 30) le porzioni appaiono per puro caso nel titolo o nel testo dei passaggi.
- **Presenza foto e licenza:** **0.0%**. Il dump non contiene immagini né URL a immagini (solo link alla pagina web originale di cookbooks.com).
- **Misurazione Dosi in Grammi (Campione Casuale di 30 Ricette, seed 42):**
  - Ingredienti totali esaminati: **245**
  - Ingredienti con peso in grammi: **0** (**0.0%**)
  - Tutte le misure sono rigorosamente imperiali statunitensi: *c.*, *tsp.*, *Tbsp.*, *oz.*, *lb.*, *cans*, *pkg.*

#### Dettaglio del campione di 30 ricette (RecipeNLG):

| ID Record | Titolo Ricetta | Ingr. Totali | Ingr. in Grammi (%) | Porzioni Strutturate | Link Originale |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **654** | Cherry Wink Cookies | 12 | 0 (0%) | No | www.cookbooks.com/Recipe-Details.aspx?id=892360 |
| **114** | Pasta Chicken Salad(268 Calories Per Serving) | 10 | 0 (0%) | No (nel titolo) | www.cookbooks.com/Recipe-Details.aspx?id=312742 |
| **25** | Smothered Round Steak(Servings: 4) | 11 | 0 (0%) | No (nel titolo) | www.cookbooks.com/Recipe-Details.aspx?id=982859 |
| **759** | Date Nut Balls | 6 | 0 (0%) | No | www.cookbooks.com/Recipe-Details.aspx?id=136387 |
| **281** | Rocky Road Fudge | 8 | 0 (0%) | No | www.cookbooks.com/Recipe-Details.aspx?id=375201 |
| **250** | Best Brownies | 8 | 0 (0%) | No | www.cookbooks.com/Recipe-Details.aspx?id=667352 |
| **228** | Mayonnaise Rolls | 4 | 0 (0%) | No | www.cookbooks.com/Recipe-Details.aspx?id=965986 |
| **142** | Dill Dip | 5 | 0 (0%) | No | www.cookbooks.com/Recipe-Details.aspx?id=306450 |
| **754** | Persimmon Cake | 14 | 0 (0%) | No | www.cookbooks.com/Recipe-Details.aspx?id=750527 |
| **104** | Jan'S Winter Soup | 14 | 0 (0%) | No | www.cookbooks.com/Recipe-Details.aspx?id=51724 |
| **692** | Dressed Eggs | 7 | 0 (0%) | No | www.cookbooks.com/Recipe-Details.aspx?id=64175 |
| **758** | Sausage And Egg Quiche | 6 | 0 (0%) | No | www.cookbooks.com/Recipe-Details.aspx?id=600748 |
| **913** | Kentucky Pecan Pie | 7 | 0 (0%) | No | www.cookbooks.com/Recipe-Details.aspx?id=921819 |
| **558** | Kim'S Chicken Alfredo Pizza | 12 | 0 (0%) | No | www.cookbooks.com/Recipe-Details.aspx?id=6859 |
| **89** | Cheese Ball | 9 | 0 (0%) | No | www.cookbooks.com/Recipe-Details.aspx?id=443102 |
| **604** | Flaky Pie Crust | 3 | 0 (0%) | No | www.cookbooks.com/Recipe-Details.aspx?id=118460 |
| **432** | Hot Cheese Balls | 6 | 0 (0%) | No | www.cookbooks.com/Recipe-Details.aspx?id=79467 |
| **32** | Cherry Pizza | 4 | 0 (0%) | No | www.cookbooks.com/Recipe-Details.aspx?id=1072589 |
| **30** | Punch Bowl Fruit Salad | 9 | 0 (0%) | No | www.cookbooks.com/Recipe-Details.aspx?id=1059877 |
| **95** | Baked Beans | 9 | 0 (0%) | No | www.cookbooks.com/Recipe-Details.aspx?id=775763 |
| **223** | Snickerdoodles | 10 | 0 (0%) | No | www.cookbooks.com/Recipe-Details.aspx?id=292551 |
| **238** | Corn Pudding | 8 | 0 (0%) | No | www.cookbooks.com/Recipe-Details.aspx?id=162191 |
| **517** | Scalloped Potatoes | 10 | 0 (0%) | No | www.cookbooks.com/Recipe-Details.aspx?id=337402 |
| **616** | Vienna Coffee | 4 | 0 (0%) | No | www.cookbooks.com/Recipe-Details.aspx?id=881293 |
| **27** | Easy Fudge | 5 | 0 (0%) | No | www.cookbooks.com/Recipe-Details.aspx?id=812407 |
| **574** | Preacher Cookies | 6 | 0 (0%) | No | www.cookbooks.com/Recipe-Details.aspx?id=774571 |
| **203** | Nana'S Cornbread | 8 | 0 (0%) | No | www.cookbooks.com/Recipe-Details.aspx?id=917184 |
| **733** | Whole Wheat Carrot Cake | 13 | 0 (0%) | No | www.cookbooks.com/Recipe-Details.aspx?id=227296 |
| **665** | Cabbage Rolls | 11 | 0 (0%) | No | www.cookbooks.com/Recipe-Details.aspx?id=954345 |
| **718** | Hominy Casserole | 6 | 0 (0%) | No | www.cookbooks.com/Recipe-Details.aspx?id=702142 |

---

### 2.4 Food.com / Kaggle

- **URL verificati:**
  - Versione classica di ricerca (shuyangli94, EMNLP 2019): [https://www.kaggle.com/datasets/shuyangli94/food-com-recipes-and-user-interactions](https://www.kaggle.com/datasets/shuyangli94/food-com-recipes-and-user-interactions)
  - Versione estesa (irkaal, 522k ricette): [https://www.kaggle.com/datasets/irkaal/foodcom-recipes-and-reviews](https://www.kaggle.com/datasets/irkaal/foodcom-recipes-and-reviews)
  - Mirror Hugging Face con CSV decompresso: [https://huggingface.co/datasets/AkashPS11/recipes_data_food.com](https://huggingface.co/datasets/AkashPS11/recipes_data_food.com)
- **Licenza esatta:**
  - Nel dataset originale `shuyangli94`: *"Data files © Original Authors"* (nessuna licenza aperta).
  - Nel dataset `irkaal`: etichettato su Kaggle come *CC0*, ma i testi, le ricette e le immagini appartengono legalmente a Food.com / Scripps Networks Interactive LLC (Warner Bros. Discovery) e agli utenti contributori. I Termini di Servizio di Food.com proibiscono esplicitamente lo scraping sistematico commerciale.
  - **Uso privato:** Tollerato per sperimentazione locale.
  - **Redistribuzione:** **NON consentita legalmente**.
- **Numero di ricette:** **231.637 ricette** (versione `RAW_recipes.csv`) fino a **522.517 ricette** (versione estesa `recipes.csv`).
- **Lingua:** Inglese.
- **Formato:** Dump CSV tabellare.
- **Presenza porzioni:** **73.3%** (22 su 30 ricette hanno il campo `RecipeServings` valorizzato).
- **Presenza foto e licenza:** **23.3%** (7 su 30 contengono URL a immagini `img.sndimg.com`). Le immagini sono coperte da copyright proprietario Scripps Networks Interactive LLC / Food.com, **nessuna licenza aperta**.
- **Misurazione Dosi in Grammi (Campione Casuale di 30 Ricette, seed 42):**
  - Ingredienti totali esaminati: **267**
  - Ingredienti con peso in grammi: **0** (**0.0%**)
  - In `RAW_recipes.csv` le quantità numeriche sono state del tutto eliminate durante il preprocessing accademico (rimangono solo i nomi degli ingredienti). Nella versione estesa `recipes.csv`, la colonna `RecipeIngredientQuantities` riporta solo numeri scalari adimensionati riferiti al volume imperiale originario (es. `4` per 4 tazze, `1/4` per 1/4 di tazza), senza alcuna indicazione di grammi.

#### Dettaglio del campione di 30 ricette (Food.com):

| ID Ricetta | Titolo Ricetta | Ingr. Totali | Ingr. in Grammi (%) | Porzioni | Immagini Presenti (CDN Food.com) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **000394** | Carrot and Orange Loaf | 10 | 0 (0%) | Sì (12) | No |
| **000099** | Chaat Masala | 8 | 0 (0%) | No | No |
| **000050** | Biscotti Di Prato | 8 | 0 (0%) | No | Sì (`img.sndimg.com/...`) |
| **000189** | Claudi Sanders' Refrigerator Rolls | 9 | 0 (0%) | No | No |
| **000172** | Chicken Pot Pie Lasagna | 13 | 0 (0%) | Sì (10) | No |
| **000161** | Chicken in Pizza Dough | 7 | 0 (0%) | No | No |
| **000115** | A New Spaghetti with Clams | 11 | 0 (0%) | Sì (1) | No |
| **000092** | Brown Bag Apple Salad | 10 | 0 (0%) | Sì (4) | No |
| **000414** | Moussaka | 22 | 0 (0%) | Sì (12) | Sì (`img.sndimg.com/...`) |
| **000341** | Grilled Pineapple Salsa | 4 | 0 (0%) | Sì (2) | No |
| **000084** | Braised Brussels Sprouts With Vinegar and Dill | 3 | 0 (0%) | Sì (12) | Sì (`img.sndimg.com/...`) |
| **000367** | Vinegar Pie | 7 | 0 (0%) | Sì (8) | No |
| **000273** | Winter Pear Butter | 4 | 0 (0%) | Sì (1) | No |
| **000054** | Carrot Cake | 14 | 0 (0%) | Sì (12) | Sì (`img.sndimg.com/...`) |
| **000053** | Jimmy G's Carrot Cake | 12 | 0 (0%) | No | No |
| **000087** | Brownies | 8 | 0 (0%) | Sì (12) | No |
| **000158** | Chicken Flambe | 7 | 0 (0%) | Sì (4) | No |
| **000166** | Chicken Liver Pate III | 8 | 0 (0%) | No | No |
| **000318** | French Pecan Pie II | 5 | 0 (0%) | No | No |
| **000373** | Tiramisu - Balducci's in New York City | 9 | 0 (0%) | Sì (6) | No |
| **000051** | Chai Tea | 11 | 0 (0%) | Sì (4) | No |
| **000350** | Spaetzle - Basic Recipe - Art Culinaire Issue | 5 | 0 (0%) | Sì (4) | No |
| **000148** | Bugwiches | 9 | 0 (0%) | Sì (1) | No |
| **000437** | Calzones II | 5 | 0 (0%) | Sì (4) | No |
| **000400** | Spaetzle - German | 5 | 0 (0%) | No | Sì (`img.sndimg.com/...`) |
| **000429** | Apple-Cinnamon Bread Pudding | 8 | 0 (0%) | Sì (10) | No |
| **000271** | Lemon Curried Lamb Chops | 6 | 0 (0%) | Sì (4) | Sì (`img.sndimg.com/...`) |
| **000159** | Chicken Curry | 22 | 0 (0%) | Sì (4) | Sì (`img.sndimg.com/...`) |
| **000287** | Feijoada (Brazilian Bean Soup) | 11 | 0 (0%) | Sì (15) | No |
| **000366** | Jarrett House Vinegar Pie | 6 | 0 (0%) | Sì (8) | No |

---

### 2.5 Dataset Accademici Italiani (Zenodo e Hugging Face)

#### 2.5.1 Zenodo Record 7265253 (*Italian gastronomic recipes dataset*)

- **URL verificato:** [https://doi.org/10.5281/zenodo.7265253](https://doi.org/10.5281/zenodo.7265253)
  - Pubblicazione collegata: *D. Fossemò et al., Using Inductive Logic Programming to globally approximate Neural Networks for preference learning*, BEWARE-22 / AIxIA 2022 ([CEUR-WS Vol. 3319](https://ceur-ws.org/Vol-3319/paper5.pdf)).
- **Licenza dichiarata:** [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) nel record Zenodo.
- **Origine effettiva dei dati:** Nella documentazione inclusa (`readme.md`), gli autori dichiarano esplicitamente: *"folder containing files of food dataset (starting data from giallozafferano.it)"*. Le colonne `Link` del file `recipes.csv` puntano direttamente alle URL del sito GialloZafferano.
- **Numero di ricette:** **900 ricette** italiane.
- **Formato:** Archivio RAR (`italian gastronomic recipes dataset.rar`, 156 KB compresso) contenente CSV, XLSX e TXT.
- **Presenza porzioni:** Non indicate nei campi strutturati (è presente solo `Preparation Time`).
- **Presenza foto:** Nessuna (0.0%).
- **Dosi in grammi:** **0.0%**. Il campo `W` associato a ogni ingrediente non è una misura ponderale in grammi, ma un peso ordinale discreto da 1 a 5 assegnato per l'apprendimento delle preferenze utente.
- **Valutazione:** **Inadatto ed escluso** sia per l'assenza di dosi in grammi, sia perché derivato da scraping non autorizzato di GialloZafferano.

#### 2.5.2 Hugging Face: `KanuSaru/italian-recipes` e `AntonelloS01/RicetteItaliane`

- **URL verificati:**
  - `KanuSaru/italian-recipes`: [https://huggingface.co/datasets/KanuSaru/italian-recipes](https://huggingface.co/datasets/KanuSaru/italian-recipes)
  - `AntonelloS01/RicetteItaliane`: [https://huggingface.co/datasets/AntonelloS01/RicetteItaliane](https://huggingface.co/datasets/AntonelloS01/RicetteItaliane)
- **Licenza:** Non specificata (*Unlicensed*).
- **Origine effettiva dei dati:** Scraping massivo non autorizzato di `ricette.giallozafferano.it` (tutti i record riportano come link originario GialloZafferano).
- **Numero di ricette:** **5.939 ricette**.
- **Lingua:** Italiano.
- **Formato:** CSV (`italian_recipes.csv`, 12 MB) e Parquet.
- **Presenza porzioni:** 100% (campo `Persone/Pezzi` presente su tutte le ricette).
- **Presenza foto:** Nessuna foto nel file (solo URL HTML).
- **Misurazione Dosi in Grammi (Campione Casuale di 30 Ricette, seed 42):**
  - Ingredienti totali esaminati: **320**
  - Ingredienti con peso in grammi/kg: **192** (**60.0%**)
- **Valutazione:** **ESCLUSO per violazione legale dei Termini di Servizio** del portale originario (vedi Sezione 3).

---

## 3. Siti Esclusi con Condizioni d'Uso che Vietano lo Scraping

I seguenti siti italiani contengono eccellenti raccolte di ricette con dosi sistematiche in grammi, ma sono **esclusi categoricamente da qualsiasi estrazione o importazione**, in ossequio ai loro Termini di Servizio e alle normative vigenti sul diritto d'autore:

### 3.1 GialloZafferano (Mondadori Media S.p.A.)

- **URL Termini e Condizioni:** [https://digital.mondadori.it/docs/giallozafferano/condizioni_di_partecipazione.html](https://digital.mondadori.it/docs/giallozafferano/condizioni_di_partecipazione.html)
- **Robots.txt:** [https://ricette.giallozafferano.it/robots.txt](https://ricette.giallozafferano.it/robots.txt)
- **Clausole legali ostative:**
  - **Art. 5.1:** Riserva espressa di tutti i diritti di proprietà industriale e intellettuale ai sensi della Legge sul Diritto d'Autore (L. 633/1941) e del Codice Civile (artt. 2575-2594 c.c.).
  - **Art. 5.3 (Divieto specifico TDM e AI):** *"Tutti i Contenuti presenti nel Sito sono di titolarità esclusiva di Mondadori Digital S.P.A. Pertanto, è vietata ogni forma di estrazione e acquisizione degli stessi per le finalità di alimentazione di sistemi di Intelligenza Artificiale."*
  - **Art. 9.7 & 10.5:** Divieto categorico di uso commerciale ed estrazione non autorizzata dei dati.
- **Conseguenza per il progetto:** Divieto assoluto di scraping del portale; divieto di importare dataset terzi derivati da scraping di GialloZafferano (come `KanuSaru/italian-recipes`, `AntonelloS01/RicetteItaliane` o Zenodo 7265253).

### 3.2 Cookaround (Mondadori Media S.p.A.)

- **URL:** [https://www.cookaround.com/](https://www.cookaround.com/)
- Fa parte del medesimo network editoriale di Mondadori Media S.p.A., applicando le identiche condizioni generali di riserva dei diritti e divieto di estrazione dati automatizzata.

### 3.3 Il Cucchiaio d'Argento (Editoriale Domus S.p.A.)

- **URL Note Legali:** [https://www.cucchiaio.it/note-legali.html](https://www.cucchiaio.it/note-legali.html)
- I contenuti, testi e immagini sono di proprietà esclusiva di Editoriale Domus S.p.A. e protetti dalla legge sul diritto d'autore. È espressamente vietata la riproduzione, l'archiviazione sistematica e l'estrazione non autorizzata.

### 3.4 La Cucina Italiana (Edizioni Condé Nast S.p.A.)

- **URL Termini e Condizioni:** [https://www.lacucinaitaliana.it/termini-e-condizioni/](https://www.lacucinaitaliana.it/termini-e-condizioni/)
- Condé Nast applica la riserva espressa contro il text and data mining (TDM opt-out) ai sensi dell'art. 4 della Direttiva UE 2019/790 (recepita dal D.Lgs. 177/2021).

---

## 4. Altri Candidati Esaminati

### 4.1 foodose (già integrato a catalogo)

- **URL verificato:** [https://www.foodose.co/glp1-recipes/nutrition-data](https://www.foodose.co/glp1-recipes/nutrition-data)
- **Licenza:** [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)
- **Dimensione:** 333 ricette, 2.439 righe ingredienti.
- **Pesi in grammi:** 300 ricette su 333 (**90.1%**) hanno tutti i pesi espliciti in grammi e ID USDA FDC per ogni ingrediente.
- **Valutazione:** Fonte di altissima qualità ingegneristica per pesi e macro, ma limitata a sole 333 ricette e fortemente specializzata su diete ipocaloriche/iperproteiche orientate GLP-1 (pochissime ricette tradizionali italiane o asiatiche).

### 4.2 UniTools (già integrato a catalogo)

- **URL verificato:** [https://github.com/farcrak/unitools-recipes](https://github.com/farcrak/unitools-recipes)
- **Licenza:** [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/)
- **Dimensione:** 501 ricette (81 italiane, 6 cinesi).
- **Pesi in grammi:** 0 ricette hanno il 100% dei pesi in grammi; la maggior parte degli ingredienti usa cucchiai, tazze, spicchi o pezzi.
- **Valutazione:** Già importato a catalogo per consultazione e testi dei procedimenti in italiano; richiede la prosecuzione delle sessioni di mapping ponderale (`conversions-*.json`) per poter ammettere le ricette al solver.

### 4.3 RecipeDB (Computational Gastronomy — IIIT Delhi)

- **URL verificato:** [https://cosylab.iiitd.edu.in/recipedb/](https://cosylab.iiitd.edu.in/recipedb/)
  - Paper: *RecipeDB: A resource for exploring recipes*, Database (Oxford), 2020 ([DOI: 10.1093/database/baaa077](https://doi.org/10.1093/database/baaa077))
- **Dimensione:** 118.171 ricette da 26 cucine mondiali.
- **Licenza:** Ricerca accademica non commerciale con consultazione via interfaccia web; nessun download massivo pubblico libero e nessuna licenza aperta di redistribuzione.
- **Dosi:** Le ricette derivano da scraping di portali anglosassoni (*Allrecipes*, *Food.com*), con dosi espresse in unità imperiali e volumetriche.

### 4.4 Pellegrino Artusi — *La scienza in cucina e l'arte di mangiar bene* (1891)

- **URL verificato:** [https://it.wikisource.org/wiki/La_scienza_in_cucina_e_l%27arte_di_mangiar_bene_(1895)](https://it.wikisource.org/wiki/La_scienza_in_cucina_e_l%27arte_di_mangiar_bene_(1895))
- **Licenza:** **Pubblico Dominio** (autore deceduto nel 1911, opera pubblicata originariamente nel 1891).
  - Uso privato: Libero.
  - Redistribuzione: Libera.
- **Numero di ricette:** **790 ricette** storiche della tradizione italiana regionale.
- **Formato:** Wikitext / Testo strutturato per capitoli su Wikisource.
- **Dosi in grammi:** Artusi fu uno dei primi gastronomi a promuovere il sistema metrico decimale in Italia post-unitaria: abbondano le indicazioni in grammi ed etti ("grammi 300 di farina", "un etto di parmigiano"), affiancate però da dosi a pezzi ("due uova") o descrizioni qualitative.
- **Limite:** Testo in prosa letteraria ottocentesca; necessita di un estrattore NLP per isolare la lista formale degli ingredienti e le quantità.

---

## 5. Conclusioni e Raccomandazioni Strategiche

1. **Il problema strutturale dei dataset in lingua inglese (RecipeNLG, Food.com/Kaggle, en.wikibooks):**
   Tutti i grandi dataset in lingua inglese hanno una percentuale di dosi in grammi prossima allo zero (**0.0%** in RecipeNLG e Food.com, **8.0%** in en.wikibooks). Tali dataset utilizzano unità imperiali e volumetriche (cups, tablespoons, ounces). Per il nostro obiettivo (portare le ricette nel solver nutrizionale con pesi esatti), l'uso di questi dataset richiederebbe centinaia di nuove regole euristiche di conversione volumetrica densità/alimento, introducendo margini di errore significativi.

2. **I dataset italiani sul web (conflitto legale):**
   I dataset accademici italiani reperibili su Hugging Face (`KanuSaru`, `AntonelloS01`) e Zenodo (record 7265253) che presentano alte percentuali di dosi in grammi (circa 60%) sono, all'analisi dei dati sorgente, **copie non autorizzate estratte da GialloZafferano**. Il loro utilizzo esporrebbe il progetto a violazioni dei diritti di proprietà intellettuale di Mondadori Media S.p.A. e dell'art. 4 della Direttiva UE 2019/790.

3. **La migliore fonte aperta legale per la cucina italiana:**
   **it.wikibooks «Libro di cucina»** (768 ricette) è l'unico corpus italiano nativamente aperto, sotto licenza **CC BY-SA 4.0**, con un quarto abbondante degli ingredienti già in grammi (**27.4%**) e le porzioni indicate nel **76.7%** dei casi. L'estrazione tramite MediaWiki API è pulita, documentata e pienamente conforme alla policy Wikimedia.

4. **Per le ricette asiatiche con dosi in grammi:**
   La sezione asiatica di *en.wikibooks* conta solo 104 ricette con l'8% di grammi. Se si desiderano ricette cinesi o giapponesi con dosi metriche rigorose, le fonti più promettenti e conformi sono:
   - Sottomoduli aperti di comunità Wikimedia locali (es. [zh.wikibooks «美食»](https://zh.wikibooks.org/wiki/%E7%BE%8E%E9%A3%9F) e [ja.wikibooks «料理»](https://ja.wikibooks.org/wiki/%E6%96%99%E7%90%86), dove la metrica asiatica usa regolarmente grammi e millilitri).
   - Espansione mirata con ricette canoniche curate manualmente con licenza aperta o formule standard del Compendium/LARN.
