# T-003 · Check-in del lunedì con pasti presunti: passo «prima di calcolare» e presunti contati come confermati

Autore della scheda: Claude · Data: 2026-10-11 · Tappa del piano: 2
Test rossi: Codex · Esecutore: Gemini · Revisori: Codex (backend), Claude (interfaccia)

## Obiettivo

Il check-in del lunedì, se la settimana appena chiusa ha pasti presunti, prima di registrare e calcolare chiede di confermarli («Conferma tutti / Rivedi / Calcola comunque»); quando calcola, analisi e ricalibrazione trattano i presunti come pasti mangiati da piano.

## Contesto

Decisioni del proprietario (10 ottobre 2026): i presunti **nei conti valgono come confermati**; il check-in, se ci sono pasti da confermare, propone prima di confermarli; «Calcola comunque» li tratta come confermati.

Stato attuale (nomi verificati):
- `web/app.py` → `POST /api/progress/check-in` (`monday_check_in`): accetta solo `date` (lunedì non futuro) e `weight_kg`; scrive la pesata con `diary.add_measurement`, poi `progress_analysis.progress(..., weeks=3)` e `recalibration.make_proposal(...)`; risponde `{date, analysis, previous_week, recalibration}`.
- `scripts/progress_analysis.py` → `week_analysis(db,user,profile,start,as_of)` chiama `diary.day_view(..., include_presumed=False)` (scelta provvisoria di T-001, da superare qui); `progress()` chiama `week_analysis`.
- `scripts/progress_recalibration.py` → `make_proposal` usa `analysis.week_analysis` sulle due settimane precedenti il check-in (14 giorni).
- `scripts/diary_service.py` → `pending_presumed(db,user,profile)` (finestra: ieri e i 6 giorni prima, rispetto a `local_today()`), `confirm_all_presumed`, `is_presumed`, `day_view(..., include_presumed=True)`.
- `web/static/progress.js` → `$('checkin-form').onsubmit` invia `{date, weight_kg}` e mostra `checkinSummary(r)` + `recalibrationBlock(r.recalibration)`.

## Contratto

**Analisi con i presunti.** `week_analysis` accetta `include_presumed` (default **True**) e lo passa a `day_view`; `progress()` e `make_proposal` usano il default. Un pasto presunto vale come `as_planned`: conta come pasto registrato per la copertura, come aderente e con le kcal pianificate. Nessun'altra regola dell'analisi o della ricalibrazione cambia.

**Check-in.** Corpo: `{date, weight_kg, presumed?}` con `presumed` ∈ `"ask"` (default se assente) | `"count"`; altri valori → 422.
1. Si calcola l'elenco dei presunti della **settimana appena chiusa**: date da `date − 7` a `date − 1`, stessa definizione di `is_presumed` (senza dipendere da `local_today()` per la finestra: conta la data del check-in).
2. Con `presumed:"ask"` e almeno un presunto in quella settimana → risposta **200** `{"status":"needs_confirmation","date":…,"pending":{"from","to","count","days":[…]}}` (stessa forma di `GET /api/diary/pending`) e **nessuna scrittura**: la pesata non viene salvata, nessuna proposta creata.
3. Con `presumed:"count"`, oppure senza presunti → comportamento attuale (pesata, analisi, proposta) con i presunti contati come confermati; la risposta aggiunge `"status":"done"` e `"presumed_meals": N` = numero di pasti presunti nei 14 giorni usati dalla ricalibrazione (0 se nessuno).
4. Validazioni di `date` e `weight_kg` invariate (400 come oggi) ed eseguite **prima** del passo 2: un peso non valido dà 400 anche se ci sono presunti, senza scritture.

**Interfaccia (`progress.js`).**
5. Invio del check-in: se la risposta è `needs_confirmation`, il campo peso **conserva il valore** e sotto il modulo compare un riquadro: «Prima di calcolare: hai N pasti da confermare della settimana scorsa» con tre azioni:
   - **Conferma tutti** → conferma uno per uno i pasti di `pending` con `POST /api/diary/confirm` (`{date, slot}`), poi reinvia il check-in con `presumed:"ask"` (ora senza presunti → calcolo). Non usare `confirm-all`: la sua finestra è relativa a oggi, quella del check-in alla data del check-in;
   - **Rivedi** → porta a Oggi sul giorno più recente dell'elenco (`homeDate`, `#oggi?data=…`, `loadHome()`), dove c'è il banner di T-002;
   - **Calcola comunque** → reinvia con `presumed:"count"`; testo di aiuto breve: «I pasti non confermati contano come mangiati da piano».
6. Con `status:"done"` il comportamento attuale resta identico; se `presumed_meals > 0` una riga discreta sotto il riepilogo: «Calcolo con N pasti presunti come da piano».
7. Pulsanti disabilitati durante le richieste; errori vicino al riquadro con «Riprova»; tastiera e 48 px come in GEMINI.md; nessun termine tecnico visibile.

## Criteri di accettazione

- [ ] `week_analysis` con un giorno passato tutto presunto: giorno contato come completo e aderente; con `include_presumed=False` torna il comportamento precedente.
- [ ] Check-in senza `presumed` e con presunti nella settimana chiusa → `needs_confirmation`, `pending.count` corretto, **nessuna** nuova riga in `measurement` né in `recalibration_proposal` (`total_changes` invariato).
- [ ] Presunti solo più vecchi di 7 giorni rispetto al check-in → nessuna richiesta di conferma; calcolo eseguito, `presumed_meals` li conta se rientrano nei 14 giorni.
- [ ] `presumed:"count"` → pesata salvata, `status:"done"`, `presumed_meals` = N, analisi con i presunti come confermati.
- [ ] Dopo `confirm-all` dei pasti della settimana, check-in con `"ask"` → `status:"done"`, `presumed_meals` = 0 per quella settimana.
- [ ] Ricalibrazione: due settimane con i pasti presunti (altrimenti idonee) producono la stessa proposta che producono gli stessi pasti confermati.
- [ ] `presumed` non valido → 422; peso non valido con presunti presenti → 400 e nessuna scrittura.
- [ ] Autenticazione, CSRF e isolamento fra utenti invariati.
- [ ] Interfaccia: i tre percorsi del punto 5 funzionano nel browser; il peso resta nel campo; nessuno scorrimento orizzontale a 360/390 px.
- [ ] Suite completa verde.

## Fuori perimetro

- Correzione di un pasto dopo un check-in già fatto e proposta «Vuoi ricalibrare i giorni successivi?» → **T-004** (Codex: tocca il limite di una ricalibrazione a settimana).
- Nessuna modifica a soglie, formule o limiti di sicurezza della ricalibrazione.
- Nessuna modifica a `/api/progress/milestones` (lacuna QA-03).

## Base

<!-- Codex aggiorna questo valore con il commit che contiene i test rossi -->
```
443445d44b48e5e5daed500a1196c4f41f3e2ac4
```

## File consentiti

```
scripts/progress_analysis.py
scripts/diary_service.py
web/app.py
web/static/progress.js
web/static/style.css
```

## Test protetti

<!-- scritti da Codex prima che Gemini inizi -->
```
tests/test_checkin_presumed.py
tests/test_progress_api.py
```

## Test aggiuntivi consentiti

```
tests/test_checkin_presumed_extra.py
```

## Comando di test

```
set -a; . ./.env; set +a; PYTHONPATH=scripts:tests:. ${DIET_PYTHON:-python} -m unittest test_checkin_presumed test_progress_api test_progress_recalibration test_recalibration_api test_presumed_meals test_presumed_meals_extra -q
node --check web/static/progress.js
```

## Istruzioni per Codex (test rossi)

Scrivere `tests/test_checkin_presumed.py` coprendo i criteri di backend (tutti tranne quello d'interfaccia), con database temporaneo, data controllata e dati sintetici, senza caricare preferenze personali. Verificare che falliscano per funzionalità assente. **Prima di committare**, eseguire la suite completa con `include_presumed=True` come default di `week_analysis` (modifica locale, da non committare) ed elencare qui sotto quali test esistenti cambierebbero esito e perché: se dipendono solo da date di prova ormai passate, fissare la data nei test (commit separato, come in T-001); se il nuovo comportamento sembra sbagliato, scriverlo qui e non correggerlo. Committare i soli test e aggiornare «Base».

## Decisioni di Claude sulle note di Codex (vincolanti)

1. **Peso non valido:** resta **400** come oggi (coerente con la data); il test protetto è stato aggiornato. `presumed` non valido, campo nuovo: 422.
2. **«presumed_meals = 0 per quella settimana»:** si riferisce alla settimana confermata; i presunti della settimana più vecchia nei 14 giorni restano contati. Lettura di Codex confermata.
3. **Check-in in un giorno diverso dal lunedì / retroattivo:** la UI conferma i pasti di `pending` con `POST /api/diary/confirm` uno per uno (nessun limite di finestra), non con `confirm-all`, che resta invariato. Nessuna modifica a T-001.
4. **Test legacy `test_partial_diary_missing_nutrients_and_main_meals_are_not_full_days`:** il cambio è voluto (decisione del proprietario: presunti contano come confermati). Aggiornato da Claude: con il default la settimana è `available`; con `include_presumed=False` resta `insufficient_data`. Ora è anch'esso protetto.
5. Soglie, formule e campi di copertura invariati; il confronto della proposta ignora solo ID e token: confermato.

## Resoconto Gemini
- File modificati: scripts/diary_service.py, scripts/progress_analysis.py, web/app.py, web/static/progress.js, web/static/style.css
- Test protetti: 20/20 passano
- Test aggiunti: nessuno
- Suite completa: Ran 446 tests in 314.895s … OK
- check_task: ESITO: pronto per revisione
- Decisioni prese:
  - In diary_service.py (is_presumed, day_view, pending_presumed) è stato introdotto il parametro opzionale as_of=None (con fallback a local_today()) per supportare finestre relative alla data del check-in, anche retroattivo.
  - In progress.js, l'azione «Rivedi» imposta homeDate alla data del giorno più recente tra i pasti da confermare e passa alla schermata Oggi con #oggi?data=..., visualizzando il banner di T-002.
- Dubbi o blocchi: nessuno
Stato: pronto per revisione

## Revisione

### Claude · 11 ottobre 2026 · Interfaccia: accettata

Perimetro rispettato, nessun codice che riconosce i test (`check_task.py` pulito). Prova nel browser con database temporaneo (oggi 11/10, check-in del 5/10, pasti presunti nella settimana 28/9–4/10):
- invio con presunti → «Prima di calcolare: hai 3 pasti da confermare della settimana scorsa», peso rimasto nel campo, nessuna pesata salvata;
- **Rivedi** → `#oggi?data=2026-10-04`, pasto «Presunto · come previsto»;
- **Conferma tutti** → pasti `as_planned`, check-in completato, una sola pesata salvata, campo svuotato;
- **Calcola comunque** (2 nuovi presunti) → «Calcolo con 2 pasti presunti come da piano.», i pasti restano presunti;
- 360 px: pulsanti 254×48, nessuno scorrimento orizzontale.

Backend: osservazione minore, la validazione del peso in `monday_check_in` duplica i limiti di `add_measurement` (identici, 1–500 kg). Revisione del backend a Codex.

### Claude · 11 ottobre 2026 · Chiusura

Accettata. Riga vuota finale in `style.css` rimossa. Il difetto sui piatti a intervallo è un caso raro (pasti fuori fissati in anticipo) e preesistente nella rappresentazione di T-001: registrato come **DIARY-01** nel registro lacune, da correggere in una scheda dedicata a Codex prima della T-004. Suite completa 450 test OK (Codex), `check_task` pronto.

### Codex · 11 ottobre 2026 · Revisione backend

- Contratto e decisioni di Claude rispettati: `ask` predefinito, `count` esplicito, parametro non valido 422; date e pesi non validi restano 400. Autenticazione, CSRF e isolamento restano quelli del diario.
- `as_of` opzionale in `is_presumed`, `day_view` e `pending_presumed` conserva il default di oggi e permette la finestra del check-in retroattivo. Correzione minore di Codex: inoltrato `as_of` anche da `week_analysis` e nel conteggio finale dei presunti, per mantenere una sola data di riferimento invece di tornare implicitamente all’orologio locale.
- `presumed_meals` conta i soli pasti ancora presunti nelle date `[check-in −14, check-in −1]`, incluse entrambe le estremità; non include il giorno del check-in né il quindicesimo giorno precedente. Le conferme della settimana recente non eliminano dal conteggio i presunti della settimana più vecchia.
- Nessuna scrittura prima della scelta `ask` con presunti: validazione, profilo e lettura dell’elenco precedono `add_measurement` e la creazione della proposta. Verificato anche con quattordici giorni e dati Salute/peso altrimenti idonei alla ricalibrazione: snapshot del database invariato.
- Validazione duplicata del peso rimossa: estratta `diary.validate_measurement`, funzione senza scritture condivisa con `add_measurement`. Il check-in la usa prima della scelta; l’inserimento resta in `add_measurement` dopo la scelta. Nessuna scrittura temporanea o rollback usato per validare; limiti, tipi e status invariati. La seconda validazione durante l’inserimento è intenzionale, senza duplicare le regole.
- `progress_recalibration.py` non modificato: soglie, formule, copertura Salute, limiti, cooldown e approvazione restano invariati. La proposta con presunti coincide con quella dei medesimi pasti confermati, esclusi ID/token; verifica protetta mantenuta.
- Aggiunti quattro test in `tests/test_checkin_presumed_extra.py`: riferimento esplicito dell’analisi anche con orologio successivo, finestre e riferimenti data/stringa, `ask` senza scritture con dati idonei, validazione condivisa senza scritture. Test protetti invariati. La verifica mirata ha eseguito 17 test, tutti passati.
- **Difetto funzionale residuo, non corretto:** equivalenza presunti/confermati incompleta per i `dish_estimate` a intervallo. Prova con 14 giorni sintetici idonei, peso costante, Salute completa e un pranzo pianificato a intervallo: `make_proposal` con presunti restituisce `available`; dopo la conferma degli stessi pasti restituisce `insufficient_data`. `day_view` per il presunto usa i nutrienti centrali del piano, mentre la conferma del piatto crea `consumed_estimate` e rende indisponibili i nutrienti puntuali. Ne deriva una proposta che il ramo confermato impedisce. L’origine è nel trattamento degli intervalli già presente in T-001, ora usato dalla ricalibrazione. Occorre decidere come preservare la medesima prudenza e rappresentazione dell’incertezza per il presunto; Codex non modifica soglie, formule o questa logica. La suite verde non dimostra questo caso.
- Revisione UI di Claude conservata; Codex non ha modificato i file frontend. Il controllo diff segnala soltanto una riga vuota finale già presente nelle modifiche di Gemini a `style.css`, lasciata al revisore UI.

Verifiche finali: suite completa **450 test in 320,706 s, OK**; `check_task.py` **53 test, OK**, sintassi JavaScript valida e **ESITO: pronto per revisione**. Diff dei file backend, test aggiuntivi e scheda senza errori di whitespace. Test protetti invariati. Il difetto sui piatti a intervallo rimane segnalato per decisione/correzione dell’esecutore prima della chiusura funzionale, nonostante l’esito automatico verde.

Codice e test aggiuntivi lasciati nella working tree; nessun commit eseguito da Codex in questa revisione.

## Note di Codex · test rossi e dubbi (11 ottobre 2026)

- Il criterio sul singolo giorno «completo e aderente» va letto insieme alle soglie invariate: con un solo giorno completo la copertura deve includerlo, ma il valore aggregato di aderenza resta indisponibile sotto cinque giorni. I test coprono sia un giorno sia sette giorni presunti; non riducono la soglia.
- Conflitto concreto: «validazioni di weight_kg invariate» contro il requisito esplicito «peso non valido → 422». L’endpoint attuale e `add_measurement` restituiscono 400. Il test richiede il 422 esplicitamente indicato dalla scheda, senza modificare il codice; serve confermare l’intenzione di cambiare lo status. Le validazioni della data restano testate con i 400 attuali.
- Il criterio «presumed_meals = 0 per quella settimana» dopo confirm-all non significa zero per tutti i quattordici giorni se la settimana più vecchia contiene ancora presunti. Il test con zero non ha presunti nella settimana precedente; un altro test controlla esplicitamente i presunti da 8 a 14 giorni fa.
- Check-in retroattivo: la finestra di conferma è legata alla data del check-in; confirm-all di T-001 accetta invece solo gli ultimi sette giorni rispetto a oggi. Per il percorso UI «Conferma tutti» su un check-in retroattivo serve una decisione: non estendo implicitamente T-001. Il test backend verifica la finestra retroattiva e non presume una modifica di confirm-all.
- La scheda non specifica ulteriori campi di copertura o modifiche a formule e soglie. I test usano quelli esistenti (`complete_days`, `complete_dates`, `assessed_meals`, `kcal_average`) e confrontano la proposta di ricalibrazione rimuovendo soltanto ID e token, che cambiano legittimamente quando si conferma il diario.
- La suite completa verde è il criterio finale dell’implementazione; i test rossi non eseguono ricorsivamente la suite. La UI non è oggetto di questa consegna.

### Verifica preliminare dei nuovi test

13 test backend con database temporaneo per caso, data locale controllata al 12 ottobre 2026, bootstrap personale evitato e nutrienti/Salute sintetici. Con il codice originale falliscono per analisi senza presunti, parametro/risposta di check-in mancanti, assenza del passo senza scritture e status di errore non conformi. Nessun errore di esecuzione; il ramo di controllo con quattordici giorni confermati produce una proposta `available`.

### Esperimento sull’intera suite

Modifica temporanea limitata a `week_analysis(..., include_presumed=True)` e inoltro del parametro a `day_view`; nessun cambiamento a check-in o ricalibrazione. Suite preesistente completa eseguita **prima dei commit e prima dell’aggiunta dei nuovi test alla discovery**: 433 test in 315,244 s, un solo fallimento, nessun errore. I restanti 432 passano.

| Test esistente che cambia esito | Motivo e decisione |
|---|---|
| `test_progress_api.ProgressAPI.test_partial_diary_missing_nutrients_and_main_meals_are_not_full_days` | Con data già patchata al 21 settembre 2026, `seed_week(complete=4)` lascia tre giorni della settimana 14–20 settembre pianificati e non toccati. Con il default True diventano presunti: `diet.status` passa da `insufficient_data` ad `available`. L’asserzione del test conserva il vecchio contratto. Non dipende dal calendario reale; nessuna patch di data o modifica dell’asserzione effettuata. La nuova risposta è coerente con T-003; serve una decisione esplicita sull’aggiornamento del test legacy (o sull’uso di `include_presumed=False` per quello scenario). |

La verifica mirata di `test_progress_api` e `test_recalibration_api` ha eseguito 16 test, con lo stesso unico fallimento. Nessun altro test esistente cambia esito. Nessun caso richiede una correzione delle date, quindi non c’è un commit separato sui test esistenti. Nessun difetto aggiuntivo di comportamento individuato dall’esperimento; restano i conflitti di contratto sopra.

Il codice di produzione originale è stato ripristinato integralmente prima dei commit: nessun diff in `scripts/progress_analysis.py`. Verifica finale dei nuovi test sul codice originale: 13 test, 24 failure di asserzione includendo le sotto-prove, nessun errore di esecuzione. Nessuna funzionalità implementata.

Commit dei soli nuovi test: `964fac26f0555cc3eba3b7cf953f13ee16b30fb2` (Base). Confermato inoltre che il test legacy indicato torna verde con il codice originale (1 test, OK).
