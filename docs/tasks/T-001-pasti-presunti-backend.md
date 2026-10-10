# T-001 · Pasti presunti: calcolo in lettura, elenco da confermare, «Conferma tutti» (backend)

Autore della scheda: Claude · Data: 2026-10-10 · Tappa del piano: 2
Esecutore: Gemini · Test rossi: Codex · Revisore: Codex (backend)

## Obiettivo

Un pasto pianificato di un giorno passato, mai toccato, conta come mangiato da piano nei totali e viene restituito come «presunto»; l'API elenca quelli degli ultimi 7 giorni da confermare e permette di confermarli uno per uno o tutti insieme.

## Contesto

Decisioni del proprietario (10 ottobre 2026):
- Un pasto vecchio mai toccato conta come presunto e **nei conti vale come confermato**.
- Promemoria solo per i **giorni passati** (mai oggi) e solo per gli **ultimi 7 giorni**; i più vecchi restano presunti ma non vengono riproposti.
- Se l'utente conferma o modifica più tardi, le stime si ricalcolano con i dati corretti.

Codice esistente (nomi verificati):
- `scripts/diary_service.py`: `state()` restituisce `'unknown'` se non c'è riga in `meal_log`; `day_view()` costruisce `meals`, `totals.eaten`, `totals.coverage.logged_slots/planned_slots`; `diary_mutation(..., action='confirm', ...)` registra un pasto come da piano (`set_state(..., 'as_planned')`); `week_view()` calcola `remaining` dai pasti `'unknown'`; `local_today()` usa Europe/Rome.
- `web/app.py`: `POST /api/diary/confirm`, `/skip`, `/reset`, bozze `/api/diary/draft*`.
- `scripts/progress_dashboard.py`: saldo energetico che oggi richiede tutti gli slot registrati.

## Contratto

**Definizione.** Un pasto è *presunto* se, per l'utente: esiste un `planned_meal` nella settimana attiva per (data, slot); la data è **precedente** a `local_today()`; `state()` è `'unknown'`; non c'è una bozza aperta per quel (data, slot); non ci sono righe in `diary_entry` per quel (data, slot). È una proprietà **calcolata in lettura**: nessuna riga viene scritta per renderlo presunto.

**`day_view` (e quindi `GET` del giorno):**
- ogni pasto ha il campo booleano `presumed`;
- per un pasto presunto `state` resta `'unknown'` e `actions` restano quelle di oggi (`confirm`, `edit`, `skip`…);
- `eaten` del pasto presunto = gli elementi pianificati (stessa forma di un pasto `as_planned`);
- `totals.eaten` include i pasti presunti;
- `totals.coverage` aggiunge `presumed_slots` (intero); `logged_slots` conta solo i registrati davvero.

**`week_view`:** i pasti presunti non sono contati fra quelli rimanenti (`remaining`).

**`GET /api/diary/pending`** (autenticato, nessuna scrittura):
```json
{ "from": "2026-10-03", "to": "2026-10-09", "count": 6,
  "days": [ { "date": "2026-10-09",
              "meals": [ { "slot": "lunch", "kcal": 640.0, "items": [ {"name": "...", "grams": 80} ] } ] } ] }
```
`from` = oggi − 7 giorni, `to` = ieri; giorni in ordine decrescente; solo pasti presunti; `count` = numero di pasti.

**`POST /api/diary/confirm-all`** (autenticato, CSRF come le altre mutazioni del diario), corpo:
```json
{ "meals": [ { "date": "2026-10-09", "slot": "lunch" } ] }
```
- conferma ogni pasto con la stessa logica di `diary_mutation(..., 'confirm', ...)`, in **un'unica transazione**;
- accetta solo pasti presunti dentro la finestra di `pending`; un pasto già registrato nel frattempo viene saltato e riportato in `skipped`, senza errore;
- data fuori finestra, data di oggi o futura → 422, nessuna modifica;
- risposta: `{ "confirmed": [...], "skipped": [...], "pending": <stessa forma di GET /api/diary/pending> }`;
- ripetere la stessa richiesta è idempotente.

**Saldo in `progress_dashboard.py`:** i pasti presunti contano come registrati per il saldo del giorno; la risposta del giorno riporta `presumed_slots`. Nessun'altra regola del cruscotto cambia.

## Criteri di accettazione

- [ ] Ieri con pranzo pianificato e mai toccato: `day_view` → `presumed: true`, `totals.eaten` lo include, `coverage.presumed_slots = 1`, `logged_slots` invariato.
- [ ] Oggi con pasto non toccato: `presumed: false`, escluso da `pending`.
- [ ] Giorno di 8 giorni fa non toccato: `presumed: true` in `day_view`, assente da `pending`.
- [ ] Pasto saltato, modificato, con voci in `diary_entry` o con bozza aperta: non presunto.
- [ ] Nessuna `GET` (giorno, settimana, pending, cruscotto) scrive nel database (conteggio righe e `total_changes` invariati).
- [ ] `confirm-all` su 3 presunti → 3 `as_planned`, `pending.count` cala di 3; ripetuta → nessun cambiamento.
- [ ] `confirm-all` con un pasto nel frattempo registrato → quel pasto in `skipped`, gli altri confermati.
- [ ] `confirm-all` con data di oggi, futura o fuori finestra → 422 e nessuna modifica.
- [ ] Senza autenticazione → 401; senza CSRF → rifiutato come le altre mutazioni; un utente non vede né conferma i pasti di un altro.
- [ ] Applicare un nuovo piano o un rientro non cambia i pasti presunti dei giorni passati.
- [ ] Il saldo del cruscotto considera i presunti e riporta `presumed_slots`.
- [ ] Suite completa verde.

## Fuori perimetro

- Interfaccia: banner, tendina, distintivo (scheda T-002, `web/static/`).
- Check-in del lunedì e proposta di ricalibrare dopo una correzione (scheda T-003, Codex).
- Nessuna nuova colonna o tabella: il presunto non si salva.

## Base

<!-- Codex aggiorna questo valore con il commit che contiene i test rossi -->
```
3a34903a722c8014920746140c0d9ad37e00a99a
```

## File consentiti

```
scripts/diary_service.py
scripts/progress_dashboard.py
web/app.py
```

## Test protetti

<!-- scritti da Codex prima che Gemini inizi -->
```
tests/test_presumed_meals.py
```

## Test aggiuntivi consentiti

```
tests/test_presumed_meals_extra.py
```

## Comando di test

```
set -a; . ./.env; set +a; PYTHONPATH=scripts:tests:. ${DIET_PYTHON:-python} -m unittest test_presumed_meals test_diary_service test_progress_dashboard test_web -q
```

## Istruzioni per Codex (test rossi)

Scrivere `tests/test_presumed_meals.py` coprendo **ogni** criterio di accettazione, con database temporaneo e data odierna controllata (patch di `diary_service.local_today`). Confermare che falliscano sul codice attuale per assenza della funzionalità, poi committare i soli test e aggiornare «Base» con quel commit.

## Resoconto Gemini

<!-- compilato da Gemini secondo GEMINI.md -->

## Revisione

<!-- compilata da Codex: esito, correzioni; commit di Claude -->

## Ambiguità e conflitti rilevati da Codex (test rossi)

- `confirm-all`: manca la risposta per un pasto dentro la finestra che non è presunto ma non è nemmeno registrato (mai pianificato, bozza aperta, sole righe `diary_entry`, piano non attivo). I test non assegnano uno status a questi casi. L’isolamento richiede comunque che un altro utente non possa confermare il pasto del proprietario.
- Non sono specificati duplicati, lista vuota, slot inesistente, date malformate e contenuto dettagliato di `confirmed`/`skipped` oltre alla coppia data/slot. Non vengono introdotte regole per questi input.
- «Nessuna GET … cruscotto scrive»: i test coprono `/api/progress/energy`, pertinente al saldo. Se si intende anche `/api/progress/milestones`, il codice attuale persiste proiezioni in lettura; serve chiarire il perimetro anziché estenderlo implicitamente.
- Applicazione del piano: il criterio vieta di cambiare i presunti passati, mentre `apply_plan` oggi protegge registrati, voci del diario e slot bloccati, non gli `unknown` dei giorni passati. Il test rende esplicito il requisito di conservazione senza scegliere un nuovo codice di errore o una struttura `skipped`.
- «Suite completa verde» è il criterio finale dell’implementazione e non può essere soddisfatto nella consegna dei test deliberatamente rossi. Non viene aggiunto un test che esegue ricorsivamente la suite. La verifica finale resta all’esecutore/revisore.
- `GEMINI.md` vieta i commit e le modifiche ai test protetti per il ruolo esecutore Gemini; l’incarico esplicito del proprietario autorizza Codex a scrivere questi test e committarli, aggiornando solo «Base» e queste note nella scheda. Nessun file di implementazione modificato.

### Verifica dei test rossi

Commit dei soli test: `3a34903a722c8014920746140c0d9ad37e00a99a`.
18 test in `tests/test_presumed_meals.py`, con database temporaneo distinto per test, `diary_service.local_today` fissato al 10 ottobre 2026 e alimenti sintetici. Bootstrap del proprietario evitato per non caricare le preferenze personali.
Comando della scheda: 62 test eseguiti, 28 failure di asserzione (incluse le sotto-prove) tutte in `test_presumed_meals`, nessun errore di esecuzione; i 44 test preesistenti passano. Cause: campi presunti mancanti, endpoint pending/confirm-all assenti (404), conteggi settimanali non aggiornati, saldo senza presunti e applicazione che sovrascrive gli unknown passati. Nessuna funzionalità implementata.
