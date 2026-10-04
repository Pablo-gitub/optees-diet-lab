# Revisione T3 e rilavorazioni per Gemini (passi 0.3–0.5)

Revisione di Claude del 2026-10-04 sul lavoro descritto in [gemini-phase0-report.md](gemini-phase0-report.md). Il rapporto originale resta com'è; i numeri validi sono quelli qui sotto.

## Esito della revisione

| Passo | Dichiarato | Verificato | Interventi della revisione |
|---|---|---|---|
| 0.3 immagini esercizi | 20 corrette | **20 corrette** (controllo a vista) | nessuno |
| 0.3 video | 20 da canali riconosciuti | 20 esistenti; **3 deboli** | titoli e canali riallineati agli originali via oEmbed (erano traduzioni automatiche); `review_note` sui 2 esercizi interessati |
| 0.4 foto ricette | 142 verificate, «tutte le italiane» | **80** valide; italiane 20/81, solver 11/25 | rimossi 50 ID inesistenti nel catalogo (es. `unitools:apple-pie`); 13 ID rimappati sull'ID reale (es. `shakshouka` → `shakshuka`); rimosse 25 foto errate; 5 miniature a larghezza non standard corrette; pasta al pomodoro passata al file reale dopo redirect |
| 0.5 titoli | 834/834 | **834/834** | integrazione UI (titolo italiano, ricerca in italiano, ricette con foto prima) |

Foto rimosse perché errate o inutilizzabili, da **non** riproporre: rösti (una cantante), fondue (Cervino), arepas (scaffale di supermercato), pelmeni (confezione), sauerbraten (carne in vaschetta), tabbouleh (vaschetta di carne), shepherd's pie (dolce), banh mi (arredo di un locale), pierogi (sfoglia cruda), plov (persone attorno a un pentolone), pad thai (tavolo dall'alto), coq au vin, couscous algerino (semola cruda), mapo tofu, murgh makhani (vaschetta da asporto), jollof rice, tagine (quaglie), tarte tatin, beef stroganoff, e per `foodose`: R027, R052, R057, R094, R143, R331 (piatti diversi da quelli indicati).

Inoltre il CSP del server non consentiva `thumb.wikimedia.org`, dominio di 92 miniature: aggiunto da Claude in `web/app.py`.

## Regole per le rilavorazioni

1. **ID reali.** Prima di aggiungere una voce, verifica che l'ID esista in `dataset/recipes/catalog.sqlite` (`SELECT id FROM recipes`) o in `config/recipe-solver.json`. Mai costruire un ID a partire dal nome del piatto.
2. **URL dalle API.** Usa `imageinfo` con `iiurlwidth=960` e salva `thumburl`, `url`, `descriptionurl` restituiti. Non costruire URL di miniature a mano: le larghezze non standard restituiscono errore 400.
3. **Controllo a vista vero.** Scarica la miniatura e guardala. Va scartata se mostra: confezioni o vaschette, scaffali, persone in primo piano, paesaggi, dipinti, ingredienti crudi, un piatto diverso o una variante diversa (khachapuri adjaruli ≠ imeruli).
4. **Rapporto onesto.** Scrivi i conteggi verificati con lo script di controllo qui sotto, non stime.
5. **Nessuna modifica** a engine, API, UI, test o cataloghi originali; nessun commit. Le modifiche restano per la revisione.

Controllo da eseguire prima della consegna:

```bash
python - <<'EOF'
import json, sqlite3
d = json.load(open('config/recipe-images.json'))['images']
ids = {r[0] for r in sqlite3.connect('dataset/recipes/catalog.sqlite').execute('SELECT id FROM recipes')}
solver = {r['id'] for r in json.load(open('config/recipe-solver.json'))['recipes']}
print('voci', len(d), 'ID inesistenti', sorted(set(d) - ids - solver))
print('miniature non standard', [k for k, v in d.items() if '/640px-' in v['thumbnail_url']])
EOF
```

## R1 — Video da sostituire

- `bodyweight-squat`: entrambi (Passion.io, Mind Body Soul). Cercare canali di istruzione (es. Calisthenicmovement, Squat University, Jeremy Ethier, Mayo Clinic).
- `stationary-bike`: il video di «Zero Healthcare_Official» (promozionale).
- Verificare ciascun video con `https://www.youtube.com/oembed?format=json&url=...` e salvare **titolo e canale restituiti**, non tradotti. Rimuovere `review_note` quando sostituiti.

## R2 — Foto ricette fino ad almeno 100

Priorità: italiane mancanti (61), poi composizioni del solver mancanti (14), poi il resto del catalogo. Elenco delle mancanti:

```bash
python - <<'EOF'
import json, sqlite3
d = json.load(open('config/recipe-images.json'))['images']
db = sqlite3.connect('dataset/recipes/catalog.sqlite')
for i, t in db.execute("SELECT id, title FROM recipes WHERE cuisine='Italian' ORDER BY id"):
    if i not in d: print(i, t)
for r in json.load(open('config/recipe-solver.json'))['recipes']:
    if r['id'] not in d: print(r['id'], r['title'])
EOF
```

Per le ricette `foodose` descrittive («Merluzzo al cartoccio con finocchio») può non esistere una foto fedele: meglio nessuna foto che una foto di un altro piatto. Documentare le lacune.

## R3 — Titoli con parole inglesi

Tradurre in `config/recipe-titles-it.json` i titoli che contengono aggettivi d'origine o nomi comuni inglesi, mantenendo il nome proprio del piatto:

- «Argentinian empanadas» → «Empanadas argentine»
- «Bosnian burek» → «Burek bosniaco»
- «Algerian couscous» → «Couscous algerino»
- «Spanish tortilla» → «Tortilla spagnola»
- «Jiaozi dumplings» → «Ravioli jiaozi»

Casi noti: Imeretian khachapuri, Iraqi dolma, Tunisian lablabi, Afghan mantu, Sudanese ful, Guatemalan tamales, Dominican/Panamanian/Colombian sancocho, Nicaraguan gallo pinto, Panamanian ropa vieja, Turkish mantı, Jamaican patties, Kenyan chapati, Azerbaijani dolma, Iraqi biryani, Tunisian chakchouka, Ecuadorian ceviche, Carniolan sausage, Omani halwa, Kuwaiti gereesh, Moldovan sarmale, Shan noodles. I nomi propri senza parti inglesi (Khinkali, Nasi goreng, Rogan josh, Okonomiyaki) restano invariati.
