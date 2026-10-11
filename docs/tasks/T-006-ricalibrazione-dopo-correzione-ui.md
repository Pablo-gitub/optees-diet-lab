# T-006 · Interfaccia: «Vuoi ricalibrare i giorni successivi?» dopo una correzione

**Per Gemini.** Autore della scheda: Claude · Data: 2026-10-11 · Tappa del piano: 2
Esecutore: Gemini · Revisore: Claude (codice e prova nel browser)

## Obiettivo

Se l'utente ha corretto pasti usati dall'ultimo check-in, Progressi mostra un riquadro con la domanda «Vuoi ricalibrare i giorni successivi?» (Sì / No) e Oggi una riga che porta lì. Con «Sì» compare la nuova proposta con il blocco di approvazione esistente; con «No» il riquadro sparisce finché non arriva una nuova correzione.

## Contesto

Backend già pronto (T-004, commit `9ba85d7`):
- `GET /api/progress/check-in/review` → `{checkin_date, corrected, dismissed}`; senza check-in recente `{checkin_date: null, corrected: false, dismissed: false}`. Nessuna scrittura.
- `POST /api/progress/check-in/review/dismiss` con `{checkin_date}` → `{status: 'dismissed', checkin_date}`.
- `POST /api/progress/check-in/review/recalculate` con `{checkin_date}` → stessa forma di `recalibration` nella risposta del check-in: `{status: 'available', proposal}` oppure `{status: 'no_adjustment' | 'insufficient_data', reason}`. Errori 409 con messaggio (`checkin_mismatch`, `checkin_expired`, `health_import_running`).
- La domanda va mostrata solo se `corrected && !dismissed`.

Interfaccia esistente (nomi verificati): in `web/static/progress.js` `loadProgress()`, `recalibrationBlock(rec)` (mostra una proposta con Approva/Rifiuta, riceve lo stesso oggetto restituito da `recalculate`), contenitore `#checkin-result` dentro la sezione del check-in in `index.html`. In `web/static/today.js` `loadHome()` chiama già `loadPendingBanner()` (T-002) nello stesso modo in cui va caricata la riga di questa scheda. Navigazione a Progressi: `document.querySelector('[data-page="progress"]').click()`. Date leggibili: `longDate(date)` in `today.js`.

## Contratto (comportamento)

**Progressi** — nuovo contenitore `<div id="checkin-review" hidden>` in `index.html` subito **prima** di `#checkin-result`, logica in un nuovo `web/static/checkin-review.js` caricato dopo `progress.js`.
1. Ad ogni `loadProgress()` (agganciarsi senza bloccarla) si legge `review`. Se `corrected && !dismissed`: riquadro con titolo «Hai corretto pasti usati nel check-in di <giorno, es. lunedì 5 ottobre>» e testo «Vuoi ricalibrare i giorni successivi? Se rispondi no, le correzioni restano nel diario e contano nei prossimi check-in.» Altrimenti nascosto. Errore della lettura: nascosto, nessun messaggio.
2. **Sì, ricalibra** (`primary small`) → `recalculate`; il riquadro viene sostituito da `recalibrationBlock(risposta)`, che gestisce già proposta, nessuna variazione e dati insufficienti (con il motivo): non aggiungere altri messaggi. Dopo la decisione della proposta il comportamento è quello esistente.
3. **No** (`secondary small`) → `dismiss`; riquadro nascosto; `message('Va bene: le correzioni restano per i prossimi calcoli.')`.
4. Durante le richieste i pulsanti sono disabilitati; errore → testo vicino ai pulsanti con «Riprova», riquadro ancora visibile.

**Oggi** — nella stessa colonna del banner T-002, sotto `#pending-meals`: `<div id="checkin-review-hint" hidden>`.
5. Ad ogni `loadHome()` si legge `review`; se `corrected && !dismissed`, **una sola riga** compatta (stesso stile del banner T-002 chiuso, senza tendina): «Hai corretto pasti del check-in: vuoi ricalibrare?» con pulsante «Apri» che porta a Progressi e mette in vista `#checkin-review`. Altrimenti nascosta. Errori: nascosta.

**Aspetto e accessibilità**
6. Colori solo da variabili di `style.css`, tema chiaro e scuro; il riquadro di Progressi non più grande del riquadro «Prima di calcolare» di T-003.
7. 360/390 px: nessuno scorrimento orizzontale; pulsanti ≥ 48 px; testo ≥ 12 px. Tab raggiunge tutto; focus visibile.
8. Testi in italiano semplice: niente «fingerprint», «dismiss», «cooldown», «proposta concatenata».

## Criteri di accettazione (verificati da Claude nel browser con database temporaneo)

- [ ] Nessun check-in recente o nessuna correzione → riquadro e riga assenti.
- [ ] Check-in fatto, poi un pasto dei 14 giorni modificato → riquadro in Progressi con il giorno del check-in; riga in Oggi; «Apri» porta al riquadro.
- [ ] «No» → riquadro e riga spariscono e restano assenti dopo ricarica; una nuova correzione li fa ricomparire.
- [ ] «Sì, ricalibra» → compare il blocco della proposta (o il motivo se non c'è variazione); approvazione/rifiuto come oggi.
- [ ] Errore simulato di `review` → Progressi e Oggi si caricano normalmente.
- [ ] 360/390 px, tema chiaro e scuro, tastiera.
- [ ] Suite completa verde (nessun file Python toccato).

## Fuori perimetro

Backend, test Python, regole della ricalibrazione; banner dei pasti da confermare (T-002) e passo «Prima di calcolare» (T-003) restano come sono.

## Base

```
9ba85d757a6ca6ecd7e159d4b205cf1274f77bda
```

## File consentiti

```
web/static/checkin-review.js
web/static/progress.js
web/static/today.js
web/static/index.html
web/static/style.css
```

## Test protetti

<!-- Scheda di sola interfaccia: suite di non regressione sui contratti usati -->
```
tests/test_recalibration_correction.py
tests/test_checkin_presumed.py
tests/test_presumed_meals.py
```

## Test aggiuntivi consentiti

```
```

## Comando di test

```
set -a; . ./.env; set +a; PYTHONPATH=scripts:tests:. ${DIET_PYTHON:-python} -m unittest test_recalibration_correction test_checkin_presumed test_presumed_meals test_web -q
node --check web/static/checkin-review.js
node --check web/static/progress.js
node --check web/static/today.js
```

## Riferimento visivo (solo interfaccia)

Progressi, sopra il risultato del check-in:

```
┌──────────────────────────────────────────────────────┐
│ Hai corretto pasti usati nel check-in di             │
│ lunedì 5 ottobre                                     │
│ Vuoi ricalibrare i giorni successivi? Se rispondi    │
│ no, le correzioni restano nel diario e contano nei   │
│ prossimi check-in.                                   │
│ [ Sì, ricalibra ]  [ No ]                            │
└──────────────────────────────────────────────────────┘
```

Oggi, sotto il banner dei pasti da confermare:

```
┌──────────────────────────────────────────────────────┐
│ ● Hai corretto pasti del check-in: vuoi ricalibrare? [Apri] │
└──────────────────────────────────────────────────────┘
```

## Resoconto Gemini

<!-- compilato da Gemini secondo GEMINI.md -->

## Revisione

<!-- Claude -->
