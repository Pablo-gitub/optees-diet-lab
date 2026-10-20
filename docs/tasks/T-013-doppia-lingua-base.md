# T-013 · Doppia lingua italiano/inglese: infrastruttura e prime schermate

**Per Gemini.** Autore della scheda: Claude · Data: 2026-10-20 · Tappa del piano: pubblicazione
Esecutore: Gemini · Revisore: Claude (codice e prova nel browser)

## Obiettivo

L'interfaccia ha due lingue, italiano (predefinito) e inglese, scelte dal menu dell'avatar. In questa scheda: l'infrastruttura, `index.html` e i moduli `app.js`, `today.js`, `pending.js`, `checkin-review.js` senza testi scritti nel codice. Gli altri moduli seguiranno in T-014; i messaggi prodotti dal server (errori, motivi) in una scheda Codex separata.

## Contesto

- Oggi i testi sono scritti direttamente nel codice in italiano: `index.html` (`<html lang="it">`), `mealMeta` e `macroMeta` in `app.js`, `fmt0` con `toLocaleString('it-IT')`, date con `toLocaleDateString('it-IT', …)`, `longDate`/`shortDate` in `today.js`.
- Script caricati con `defer` da `index.html`, nessun modulo ES, CSP `script-src 'self'` (niente script in linea, niente `eval`).
- Il tema usa già `localStorage` con chiave `diet-theme` (`app.js`, `applyTheme`): stessa logica per la lingua.
- Gli errori del server arrivano in `error.message` da `api()` e restano in italiano finché non arriva la scheda Codex: **non tradurli e non cambiarli** qui.
- I nomi degli alimenti (tabelle CREA) e delle ricette sono dati: restano come arrivano.

## Contratto

**File di traduzione** — `web/static/locales/it.js` e `web/static/locales/en.js`. Ognuno contiene **una sola** assegnazione `I18N_MESSAGES.it = { … };` (risp. `.en`) con un oggetto piatto in formato JSON valido (chiavi e valori tra doppi apici, niente commenti, niente virgola finale), così il test lo legge con `json.loads`. Chiavi a punti per area: `nav.today`, `meal.breakfast`, `today.pending.title`, `common.retry`, ecc. Segnaposto `{name}`; stessi segnaposto nelle due lingue. Plurali con due chiavi `.one` / `.other`.

**Runtime** — `web/static/i18n.js`, caricato **dopo** i due file di traduzione e **prima** di `app.js`:
1. `window.I18N_MESSAGES` creato dal primo file caricato se manca (`window.I18N_MESSAGES = window.I18N_MESSAGES || {}` all'inizio di ogni file di traduzione, prima dell'assegnazione: va bene, il test cerca solo l'assegnazione finale).
2. `lang`: da `localStorage['diet-lang']` (letture e scritture in `try/catch`), altrimenti `navigator.language` che inizia con `en` → `en`, altrimenti `it`.
3. `t(key, params)`: testo nella lingua corrente, segnaposto sostituiti; chiave assente → testo italiano; assente anche lì → la chiave stessa e un `console.warn` una volta per chiave.
4. `tn(key, n, params)`: sceglie `.one` / `.other` con `Intl.PluralRules(lang)` e passa `{n}`.
5. `applyI18n(root = document)`: per ogni `[data-i18n]` imposta `textContent`; per ogni `[data-i18n-attr="attr:chiave;attr:chiave"]` imposta gli attributi. Imposta `document.documentElement.lang` e `document.title`.
6. `locale()` → `'it-IT'` o `'en-GB'`; `fmtDate(date, options)` e `fmtNumber(value, options)` basati su `Intl` con quel locale. Tutti gli usi di `'it-IT'` nei moduli di questa scheda passano da qui.
7. `setLang(code)`: salva, imposta `lang`, e **ricarica la pagina** (`location.reload()`): niente ridisegno a caldo.

**HTML** — ogni testo visibile di `index.html` ha `data-i18n`; ogni `placeholder`, `aria-label`, `title`, `alt` con testo ha `data-i18n-attr`. Il testo italiano resta nell'HTML come contenuto iniziale (si vede anche se il JS fallisce). `applyI18n()` va chiamato all'avvio prima di tutto il resto.

**Selettore di lingua** — nel menu dell'avatar, gruppo «Impostazioni», accanto al tema: voce «Lingua: Italiano» / «Language: English» che apre una scelta a due opzioni (o alterna; a tua scelta, purché con tastiera e `role="menuitem"` coerenti con il menu esistente). Il nome di ogni lingua è scritto nella lingua stessa.

**Moduli** — in `app.js`, `today.js`, `pending.js`, `checkin-review.js` ogni testo per l'utente passa da `t()`/`tn()`; date e numeri da `fmtDate`/`fmtNumber`. `mealMeta` e `macroMeta` diventano chiavi (`meal.<slot>`, `macro.<nome>`) lette con `t()` al momento dell'uso, non al caricamento. Le classi CSS, gli id e le chiavi di API restano come sono.

**Inglese** — semplice e naturale, stesso tono dell'italiano (britannico: «optimise», date «Monday 5 October»). Glossario fisso:

| Italiano | English |
|---|---|
| Oggi / Piano / Allenamento / Progressi | Today / Plan / Training / Progress |
| Colazione · Metà mattina · Pranzo · Metà pomeriggio · Cena | Breakfast · Mid-morning snack · Lunch · Afternoon snack · Dinner |
| Presunto | Presumed |
| Pasti da confermare | Meals to confirm |
| Conferma · Conferma tutti | Confirm · Confirm all |
| Fuori programma | Off plan |
| Rientro della settimana | Week catch-up |
| Check-in del lunedì | Monday check-in |
| Ricalibrare / ricalibrazione | Recalibrate / recalibration |
| Come previsto | As planned |
| Salta | Skip |

## Criteri di accettazione (verificati da Claude nel browser con database temporaneo)

- [ ] Primo avvio con browser in inglese → interfaccia in inglese; altrimenti italiano.
- [ ] Menu avatar → lingua cambiata, pagina ricaricata, scelta ricordata dopo un nuovo caricamento; `<html lang>` corretto.
- [ ] Oggi, banner dei pasti da confermare, riga della ricalibrazione, menu, login e navigazione interamente nella lingua scelta; date («Monday 5 October» / «lunedì 5 ottobre») e numeri coerenti.
- [ ] In italiano la pagina è identica a prima (stessi testi, nessun testo mancante, nessuna chiave visibile).
- [ ] Nessun avviso di chiave mancante nella console in nessuna delle due lingue sulle schermate di questa scheda.
- [ ] Gli altri moduli (Piano, Allenamento, Progressi…) funzionano come prima, anche se ancora in italiano.
- [ ] 360/390 px in inglese: nessuno scorrimento orizzontale (i testi inglesi possono essere più lunghi).
- [ ] Suite completa verde.

## Fuori perimetro

- Moduli diversi da quelli elencati (T-014).
- Messaggi del server, `web/app.py`, `scripts/` (scheda Codex).
- Nomi di alimenti e ricette; documenti in `docs/`; immagini del README.
- Nessuna libreria esterna.

## Base

```
DA COMPILARE AL COMMIT
```

## File consentiti

```
web/static/i18n.js
web/static/locales/it.js
web/static/locales/en.js
web/static/index.html
web/static/app.js
web/static/today.js
web/static/pending.js
web/static/checkin-review.js
web/static/style.css
```

## Test protetti

```
tests/test_i18n_catalog.py
```

## Test aggiuntivi consentiti

```
```

## Comando di test

```
set -a; . ./.env; set +a; PYTHONPATH=scripts:tests:. ${DIET_PYTHON:-python} -m unittest test_i18n_catalog test_web -q
node --check web/static/i18n.js
node --check web/static/locales/it.js
node --check web/static/locales/en.js
node --check web/static/app.js
node --check web/static/today.js
node --check web/static/pending.js
node --check web/static/checkin-review.js
```

## Riferimento visivo (solo interfaccia)

Menu dell'avatar, gruppo Impostazioni:

```
IMPOSTAZIONI
  Tema: chiaro
  Lingua: Italiano          → in inglese: «Language: English»
```
