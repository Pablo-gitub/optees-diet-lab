# T-002 · Pasti presunti: banner «da confermare» in Oggi e pasti presunti nella giornata (interfaccia)

Autore della scheda: Claude · Data: 2026-10-11 · Tappa del piano: 2
Esecutore: Gemini · Revisore: Claude (codice e prova visiva nel browser)

## Obiettivo

Nella pagina Oggi un banner piccolo ricorda i pasti degli ultimi 7 giorni ancora da confermare; dalla sua tendina si conferma un pasto, si apre il suo giorno o si conferma tutto. Nei giorni passati i pasti presunti appaiono come «presunti», non come «da registrare».

## Contesto

Backend già pronto (T-001, commit `c2e13ff`):
- `GET /api/diary/pending` → `{from, to, count, days:[{date, meals:[{slot, kcal, items:[{name, grams}]}]}]}`; giorni in ordine decrescente; solo giorni passati, ultimi 7.
- `POST /api/diary/confirm-all` con `{meals:[{date, slot}]}` → `{confirmed, skipped, pending}` (`pending` ha la stessa forma di GET).
- `GET /api/day?date=…`: ogni pasto ha `presumed` (booleano); per un presunto `state` resta `'unknown'`, `eaten` contiene gli elementi pianificati; `totals.coverage.presumed_slots`.
- Conferma di un singolo pasto: `mutate('diary/confirm','POST',{date, slot})` in `today.js` (aggiunge da sé la `revision` se il giorno è quello mostrato; altrimenti usare `api('diary/confirm', 'POST', {date, slot})`).

Interfaccia esistente (`web/static/today.js`, nomi verificati): `homeDate`, `loadHome()`, `renderDay(day)`, `mealCard(m, day)`, `mutate()`, `renderDayProgress(day)`, `stateMeta`, `mealMeta[slot][0]` (nome del pasto). In `renderDay` il «prossimo pasto» è il primo con `state==='unknown'`; l'elenco dei pasti tratta come aperti quelli `unknown` e come riepiloghi chiusi (`details.registered-meal`) gli altri. In `index.html`, dentro `<section id="home">`: `#taste-invite`, `#home-load-error`, `.home-progress-link`, `.day-head`. Navigazione a un giorno: `homeDate=<data>; history.pushState(null,'','#oggi?data='+homeDate); loadHome()`.

Decisioni del proprietario: promemoria solo per giorni passati e ultimi 7 giorni; i presunti valgono come confermati; banner discreto (la pagina era stata giudicata affollata).

## Contratto (comportamento)

**Banner** — nuovo modulo `web/static/pending.js`, caricato in `index.html` dopo `today.js`, contenitore `<div id="pending-meals" hidden>` in `#home` subito prima di `.home-progress-link`.
1. Si carica con `GET /api/diary/pending` ogni volta che si apre Oggi (agganciarsi a `loadHome` senza bloccare il rendering del giorno: un errore del banner non mostra nulla e non tocca `#home-load-error`).
2. `count === 0` → banner nascosto.
3. Chiuso: una sola riga «Hai N pasti da confermare» (singolare «1 pasto da confermare») con pulsante che apre/chiude la tendina (`aria-expanded`, `aria-controls`) e pulsante ✕ «Nascondi» (`aria-label`).
4. Tendina: gruppi per giorno con titolo leggibile (es. «Ieri», poi «Giovedì 8 ottobre»); per ogni pasto una riga con nome del pasto, kcal e i primi alimenti (massimo 3 nomi, poi «…»). Ogni riga ha:
   - **Conferma** → conferma quel pasto; la riga sparisce, il conteggio cala; se il giorno confermato è quello mostrato in Oggi, aggiornare la giornata;
   - il **nome del pasto è un pulsante** che porta a quel giorno in Oggi (stessa navigazione di `day-prev`) e porta in vista la sua scheda.
5. In fondo alla tendina **Conferma tutti** → `POST /api/diary/confirm-all` con tutti i pasti elencati; dopo la risposta il banner si ridisegna da `pending` della risposta e la giornata mostrata si ricarica. Se `skipped` non è vuoto, una riga discreta «N pasti erano già stati registrati».
6. Durante una richiesta i pulsanti coinvolti sono disabilitati; errore → messaggio vicino al banner con «Riprova», niente perdita dello stato della tendina.
7. ✕ nasconde il banner. Ricompare solo se in un caricamento successivo compare **almeno un pasto non presente** quando è stato nascosto. Memoria in `localStorage`, chiave per utente `'diet-pending-dismissed:' + profile.display_name` (`profile` è il globale di `app.js`), letture e scritture dentro `try/catch`: senza storage il banner semplicemente ricompare.

**Pasti presunti nella giornata** (`today.js`):
8. Il «prossimo pasto da registrare» (`#day-next-action`) ignora i pasti con `presumed: true`.
9. Un pasto presunto è mostrato come riepilogo chiuso (`details.registered-meal`), con sommario «<Pasto> · Presunto · come previsto · <kcal>» e un distintivo «Presunto» (stile neutro, non di errore). Aperto, mostra la scheda del pasto con le azioni già esistenti (Conferma come previsto, Modifica, Salta).
10. `renderDayProgress`: la frase «Giornata incompleta…» non conta i pasti presunti.

**Aspetto e accessibilità**
11. Il banner è un'unica superficie compatta (variabili di `style.css`, tema chiaro e scuro), non un nuovo pannello grande; chiuso occupa una riga.
12. A 360 e 390 px: nessuno scorrimento orizzontale, aree di tocco ≥ 48 px per Conferma, Conferma tutti, ✕ e apertura tendina; testo ≥ 12 px.
13. Tastiera: tutto raggiungibile con Tab; Escape chiude la tendina e riporta il focus al pulsante che la apre.
14. Testi in italiano semplice; niente «slot», «pending», «presumed» visibili.

## Criteri di accettazione (verificati da Claude nel browser con database temporaneo)

- [ ] Nessun pasto da confermare → banner assente.
- [ ] Tre pasti presunti su due giorni passati → «Hai 3 pasti da confermare»; tendina con due gruppi, giorno più recente in alto.
- [ ] Conferma di un pasto → riga sparisce, «Hai 2 pasti…»; ricaricando la pagina resta 2.
- [ ] Nome del pasto → Oggi mostra quel giorno, URL `#oggi?data=…`, scheda del pasto visibile.
- [ ] Conferma tutti → banner sparisce; ricaricando resta assente.
- [ ] ✕ → banner nascosto anche dopo ricarica; un nuovo pasto presunto lo fa ricomparire.
- [ ] Giornata di ieri non confermata: pasti come «Presunto · come previsto», nessun «da registrare» in alto, nessuna «Giornata incompleta».
- [ ] Oggi: i pasti di oggi non compaiono mai nel banner.
- [ ] Errore simulato di `/api/diary/pending` → la giornata si carica normalmente.
- [ ] 360 / 390 px e desktop, tema chiaro e scuro: nessuna sovrapposizione né scorrimento orizzontale.
- [ ] Tab ed Escape come al punto 13.
- [ ] Suite completa verde (nessun file Python toccato).

## Fuori perimetro

- Nessuna modifica a `scripts/`, `web/app.py`, `tests/`.
- Check-in del lunedì e proposta di ricalibrare (T-003).
- Nessuna notifica, nessun conteggio nella barra di navigazione.

## Base

```
c2e13ff2cfe792e17940c2fe4f9884bbb59f6160
```

## File consentiti

```
web/static/pending.js
web/static/today.js
web/static/index.html
web/static/style.css
```

## Test protetti

<!-- Nessun test Python: la scheda è di sola interfaccia; il comportamento si verifica nel browser.
     La suite resta il controllo di non regressione. -->
```
tests/test_presumed_meals.py
tests/test_presumed_meals_extra.py
```

## Test aggiuntivi consentiti

```
```

## Comando di test

```
set -a; . ./.env; set +a; PYTHONPATH=scripts:tests:. ${DIET_PYTHON:-python} -m unittest test_presumed_meals test_presumed_meals_extra test_web -q
node --check web/static/pending.js
node --check web/static/today.js
```

## Riferimento visivo (solo interfaccia)

Chiuso (una riga, sotto eventuale invito ai gusti, sopra «Vedi i progressi →»):

```
┌───────────────────────────────────────────────────────┐
│ ● Hai 3 pasti da confermare                ⌄     ✕   │
└───────────────────────────────────────────────────────┘
```

Aperto:

```
┌───────────────────────────────────────────────────────┐
│ ● Hai 3 pasti da confermare                ⌃     ✕   │
│ IERI                                                  │
│  Pranzo · 640 kcal          Pasta, zucchine, pollo    │
│                                         [ Conferma ]  │
│  Cena · 520 kcal            Merluzzo, patate…         │
│                                         [ Conferma ]  │
│ GIOVEDÌ 8 OTTOBRE                                     │
│  Spuntino · 180 kcal        Yogurt greco              │
│                                         [ Conferma ]  │
│                                   [ Conferma tutti ]  │
└───────────────────────────────────────────────────────┘
```

Stile: superficie `--surface-2` con bordo `--line`, punto colorato `--warn` a sinistra, titoli dei giorni come `.user-menu-label` (maiuscoletto piccolo), «Conferma» `secondary small`, «Conferma tutti» `primary small`. Su telefono kcal e alimenti vanno sotto al nome del pasto.

## Resoconto Gemini

- File modificati: web/static/index.html, web/static/style.css, web/static/today.js, web/static/pending.js
- Test protetti: 39/39 passano
- Test aggiunti: nessuno
- Suite completa: Ran 433 tests in 306.684s … OK
- check_task: ESITO: pronto per revisione
- Decisioni prese:
  - Agganciato loadPendingBanner() anche al termine positivo di mutate() in today.js, così che la conferma o salto di un pasto effettuata direttamente dalla giornata aggiorni subito anche il banner.
  - Al click sul nome del pasto nella tendina di pending.js, se l'elemento di destinazione è un details.registered-meal, viene impostato card.open = true per mostrare immediatamente la scheda aperta oltre a portarla in vista e focalizzarla.
- Dubbi o blocchi: nessuno
Stato: pronto per revisione

## Revisione

### Claude · 11 ottobre 2026 · Esito: accettata con una correzione di stile

Codice: perimetro rispettato, nomi verificati esistenti (`longDate`, `shortDate`, `fmt0`, `addDays`, `isoDate`, `mealMeta`, `currentDay`), colori solo da variabili, errori del banner isolati dalla giornata. Il commento iniziale cita un inesistente «api-contract.md §1» (innocuo, corretto).

Prova nel browser (database temporaneo, 4 pasti passati + 1 di oggi + 1 di 9 giorni fa):
- banner «Hai 3 pasti da confermare»: esclusi oggi e il pasto di 9 giorni fa; gruppi «Ieri» / «Giovedì 8 ottobre»;
- Conferma singola → «2 pasti», confermato dopo ricarica; nome del pasto → `#oggi?data=2026-10-10`, scheda aperta, «Presunto · come previsto · 317 kcal», distintivo «Presunto»;
- Conferma tutti → banner assente anche dopo ricarica; il pasto diventa «Come previsto»;
- ✕ → nascosto dopo ricarica; un pasto nuovo lo fa ricomparire («1 pasto»);
- errore simulato di `/api/diary/pending` → giornata caricata, nessun errore mostrato;
- Escape chiude la tendina e riporta il focus sul pulsante; pulsanti 48 px; nessuno scorrimento orizzontale a 360/390 px; tema chiaro e scuro.

Correzione di Claude (`style.css`): su telefono ogni pasto occupava quattro righe con «Conferma» isolato; ora nome e kcal su una riga, alimenti sotto, «Conferma» a destra.

Nota: nei giorni passati un pasto **non pianificato** resta «da registrare» (corretto: non c'è nulla da presumere).

