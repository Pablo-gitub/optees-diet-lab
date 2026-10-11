# T-004 · Correzione dopo il check-in: «Vuoi ricalibrare i giorni successivi?» con ricalibrazione concatenata

Autore della scheda: Claude · Data: 2026-10-11 · Tappa del piano: 2
Test rossi e backend: Codex (parte delicata: limiti e cooldown della ricalibrazione) · Interfaccia: Gemini (scheda successiva, dopo questo contratto) · Revisori: Codex, Claude

## Obiettivo

Se dopo un check-in l'utente corregge pasti dei giorni che quel check-in ha usato, l'app chiede se ricalibrare. Con «Sì» nasce una nuova proposta **concatenata**: parte dai target attuali (già cambiati dalla ricalibrazione approvata di quel check-in) e usa i dati corretti, e la variazione **complessiva** della settimana resta entro i limiti di sicurezza. Con «No» non cambia nulla: i dati corretti restano nel diario e pesano sui calcoli successivi.

## Decisioni del proprietario (11 ottobre 2026)

- Correzione dopo il check-in: si chiede se ricalibrare i giorni successivi; con «No» i dati restano solo come memoria per le settimane seguenti.
- Più ricalibrazioni nella stessa settimana sono **concatenate**: la successiva tiene conto della precedente, non riparte da zero né si somma alla cieca.

## Contesto (nomi verificati)

`scripts/progress_recalibration.py`: `SAFETY` (`max_weekly_change_kcal=100`, `max_weekly_change_fraction=.05`, `approval_cooldown_days=7`, `proposal_expiry_days=7`), `cooldown(db,user)` (blocca approvazioni entro 7 giorni da un'altra approvata), `make_proposal(...)` (14 giorni prima del check-in; `desired=estimate+balance-old_target` sui target correnti; `target_changes` limita il passo a ±min(100, 5%)), `decide(...)` (approva/rifiuta con `state_token`/`fingerprint`), tabella `recalibration_proposal` (`checkin_date`, `state`). `web/app.py`: `POST /api/progress/check-in`, `/api/progress/recalibrations*`. Pasti presunti e `as_of`: T-001, T-003.

## Contratto (backend)

1. **Riferimento del check-in.** Al check-in completato (`status:"done"`) si conserva un'impronta del diario dei 14 giorni usati (stessa base dei dati di `make_proposal`, presunti inclusi come in T-003), legata a utente e `checkin_date`. Scrittura solo dentro il check-in, mai nelle GET.
2. **Stato della correzione.** `GET /api/progress/check-in/review` → per l'ultimo check-in della settimana corrente (entro `proposal_expiry_days`): `{"checkin_date", "corrected": bool, "dismissed": bool}`; `corrected` è vero se l'impronta attuale dei 14 giorni differisce da quella salvata. Senza check-in recente: `{"checkin_date": null, "corrected": false}`. Nessuna scrittura.
3. **«No».** `POST /api/progress/check-in/review/dismiss {checkin_date}` → registra il rifiuto per l'impronta attuale; `review` torna `dismissed:true` finché non arriva una nuova correzione (impronta diversa). Nessuna modifica a target o proposte.
4. **«Sì».** `POST /api/progress/check-in/review/recalculate {checkin_date}` → nuova proposta con la pesata già salvata del check-in e i dati attuali; stessa risposta di `recalibration` nel check-in. Le proposte `pending` precedenti diventano `superseded` (come oggi).
5. **Concatenazione e limiti.** La nuova proposta parte dai target correnti. La variazione **cumulata** rispetto ai target prima della prima ricalibrazione approvata per lo stesso `checkin_date` non supera ±min(`max_weekly_change_kcal`, `max_weekly_change_fraction`·target). `allowed_delta_kcal` della proposta riflette lo spazio residuo.
6. **Cooldown.** L'approvazione di una proposta di correzione è ammessa anche entro `approval_cooldown_days` **solo** se l'unica ricalibrazione approvata nel periodo ha lo stesso `checkin_date`; la precedente resta `approved` nella cronologia e la nuova registra il collegamento (es. `chained_from`). Ogni altro caso di cooldown resta invariato.
7. Autenticazione, CSRF, isolamento fra utenti come gli altri endpoint dei progressi; `checkin_date` diverso dall'ultimo check-in recente → 409 con messaggio chiaro.

## Criteri di accettazione (test rossi di Codex)

- [ ] Check-in completato salva l'impronta; GET di `review` subito dopo → `corrected:false`; nessuna GET scrive.
- [ ] Correzione di un pasto (modifica, conferma di un presunto con contenuto diverso, salto) in uno dei 14 giorni → `corrected:true`; correzione fuori dai 14 giorni → `false`.
- [ ] `dismiss` → `dismissed:true`, target e proposte invariati; nuova correzione → di nuovo `dismissed:false`.
- [ ] `recalculate` dopo una ricalibrazione approvata di −100 (limite pieno) e dati che chiederebbero ancora −100 → nessuna ulteriore riduzione (spazio residuo 0); con dati che chiedono +30 → proposta +30, cumulata −70.
- [ ] Approvazione della proposta di correzione entro 7 giorni dalla prima approvata con lo stesso `checkin_date` → consentita; con `checkin_date` diverso → `recalibration_cooldown` come oggi.
- [ ] La cronologia mostra entrambe le approvazioni e il collegamento; i token/impronte esistenti continuano a invalidare decisioni su dati cambiati.
- [ ] 401/403/isolamento; `checkin_date` non corrispondente → 409.
- [ ] Suite completa verde.

## Interfaccia (scheda T-006, dopo il commit del backend)

Riquadro in Progressi e una riga in Oggi: «Hai corretto pasti usati nel check-in di lunedì. Vuoi ricalibrare i giorni successivi?» → **Sì** (mostra la nuova proposta con il blocco di approvazione esistente) / **No** (dismiss). Stile e accessibilità come T-002.

## Fuori perimetro

Rientro dopo uno sgarro (`meal_rebalance`, già con protezione dalla doppia compensazione); formule di stima del consumo; soglie diverse dai limiti esistenti.

## Base

```
a066f94da2693666a03d551ec21f2a544c74ccef
```

## File consentiti

```
scripts/progress_recalibration.py
scripts/progress_analysis.py
scripts/diary_service.py
web/app.py
```

## Test protetti

<!-- scritti da Codex -->
```
tests/test_recalibration_correction.py
```

## Test aggiuntivi consentiti

```
tests/test_recalibration_correction_extra.py
```

## Comando di test

```
set -a; . ./.env; set +a; PYTHONPATH=scripts:tests:. ${DIET_PYTHON:-python} -m unittest test_recalibration_correction test_progress_recalibration test_recalibration_api test_checkin_presumed test_progress_api -q
```

## Resoconto Gemini
- File modificati: docs/tasks/T-004-ricalibrazione-dopo-correzione.md, scripts/progress_recalibration.py, web/app.py
- Test protetti: 18/20 passano (2 falliscono per conflitti con vincoli di sicurezza e blocco transazionale)
- Test aggiunti: nessuno
- Suite completa: Ran 486 tests in 320.538s … FAILED (failures=1, errors=1, i 484 test esistenti fuori dalla scheda passano tutti)
- check_task: non pronto (1 problemi - test command fallito sui 2 test protetti)
- Decisioni prese:
  - Creata tabella `checkin_reference` in `migrate()` per tracciare `diary_fingerprint` (SHA-256 dei 14 giorni di pasti consumati effettivi, stati saltati e range) e `dismissed_fingerprint`.
  - Implementati endpoint `GET /api/progress/check-in/review`, `POST /api/progress/check-in/review/dismiss`, `POST /api/progress/check-in/review/recalculate`.
  - Calcolo dei target concatenati: determinazione dello spazio residuo settimanale (`bound_delta`) basato sul target originale della prima proposta approvata per lo stesso `checkin_date`, tracciando `chained_from` e `cumulative_delta_kcal`.
  - Cooldown: `cooldown` consente il bypass esclusivamente quando la proposta approvata nel periodo ha lo stesso `checkin_date` (`allowed_checkin_date`), mantenendo il vincolo rigoroso a 7 giorni per check-in regolari e date differenti.
- Dubbi o blocchi:
  - Blocco 1 (`test_recalculate_chained_limits_and_cumulative_delta`): nel test protetto il pasto della colazione viene saltato (`skip`). Il salto riduce l'intake giornaliero del 20% (360 kcal su 1800 kcal pianificate), entrando in conflitto diretto con la soglia di sicurezza non modificabile di `make_proposal` («Scostamenti calorici dal piano oltre il 10%; prima verificare l'aderenza.»). Come da istruzioni, non ho toccato le formule né le soglie di sicurezza della ricalibrazione, fermandomi dopo due tentativi.
  - Blocco 2 (`test_cooldown_allowed_for_same_checkin_blocked_for_different`): nel test protetto l'operazione DML `INSERT INTO recalibration_proposal` viene eseguita all'interno di un blocco `with self.app.connect() as db:` che racchiude anche la chiamata HTTP sincrona `self.client.post(...)`. Questo mantiene aperta la transazione SQLite sul primo cursore mentre `decide_recalibration` tenta `BEGIN IMMEDIATE` sulla seconda connessione nello stesso thread, causando deadlock e `sqlite3.OperationalError: database is locked`. Inoltre, inserire una proposta con data a 7 giorni esatti (`self.date(7)`) fa scattare `proposal_expired` (la soglia di validità è `0 <= age < 7` giorni, testata e protetta anche in `test_recalibration_api.py`) prima del controllo del cooldown.
Stato: in attesa di decisione / revisione

## Revisione

### Claude · 11 ottobre 2026 · Chiusura del backend

Svolgimento fuori dal flusso previsto: per errore il prompt destinato a Codex è andato a Gemini, che ha scritto test e implementazione (e fatto i commit di T-005 e dei test, seguendo quel prompt). Gemini si è fermato correttamente sui due test che non poteva soddisfare senza toccare soglie o transazioni (regola 9). Codex ha poi rivisto tutto, corretto impronta, limite cumulativo per gruppo, cooldown solo per proposte concatenate e uso della pesata originale; le due fixture protette difettose sono state corrette con autorizzazione del proprietario (`a066f94`).

Revisione di Claude: logica conforme al contratto (concatenazione dai target correnti, limite cumulativo verificato anche all'approvazione, eccezione al cooldown limitata alla catena dello stesso check-in, nessuna formula o soglia cambiata). `check_task` pronto; suite completa 494 test OK. **Accettata**; interfaccia nella scheda T-006.


### Codex · 11 ottobre 2026 · Revisione dell’implementazione Gemini

- Confermati i due problemi dei test protetti, lasciati invariati: `test_recalculate_chained_limits_and_cumulative_delta` salta 360 kcal su 1800 (20%, oltre il 10% ammesso); inoltre la baseline 1930, con intake 1800, non implica +30 rispetto a 1900 (stima 1897,5). La seconda parte e i controlli sulla cronologia sono condizionali e possono non verificare nulla. `test_cooldown_allowed_for_same_checkin_blocked_for_different` mantiene aperta una transazione DML durante la richiesta HTTP e usa una data a sette giorni, già scaduta prima del controllo cooldown. Questi problemi richiedono una revisione esplicita del contratto di test; non si cambiano soglie, scadenze o gestione transazionale di produzione per aggirarli.
- Decisione sul limite cumulativo: vale per ogni gruppo `daily`, `rest`, `training`, rispetto al suo target iniziale, intersecando i margini residui; usare solo il target `daily` poteva superare il 5% di un target di riposo più basso. Il riferimento è la differenza effettiva fra target corrente e iniziale, non la somma cieca dei delta storici.
- Corretto `scripts/progress_recalibration.py`: budget cumulativo per tutti i gruppi e verifica anche all’approvazione; eccezione al cooldown soltanto per proposte con collegamento alla catena approvata. Una proposta ordinaria della stessa data non ottiene il bypass. Le altre approvazioni recenti, incluse quelle relative a obiettivi e attività, continuano a bloccare.
- Corretto `web/app.py`: ricalcolo in transazione con lock e profilo fresco, peso del check-in conservato come riferimento della stima anche se la misura viene successivamente modificata, fingerprint di approvazione ancora basato sui dati reali correnti. Le proposte pendenti precedenti sono superate anche quando il nuovo risultato è `no_adjustment` o dati insufficienti, così non resta approvabile una proposta precedente alla richiesta di ricalcolo.
- Aggiunti otto test in `tests/test_recalibration_correction_extra.py`: limite pieno e inversione +30/cumulata −70 con entrambe le approvazioni in cronologia; cap separati per gruppo; invalidazione token; nessun bypass per proposte ordinarie; supersessione senza aggiustamento; pesata originale; blocco con altro check-in recente. Incluso un test che controlla le scritture sulla stessa connessione e distingue una conferma identica da una modifica reale: falliva prima della correzione dell’impronta, che includeva ID e origine della registrazione. L’impronta ora normalizza alimenti, quantità e nutrienti, senza metadati di persistenza. Tutti verdi con database temporanei e dati sintetici. La baseline valida per +30 con intake 1800 è 1973,333…; formule e soglie invariate.
- Verifica mirata iniziale: 33 test verdi (cinque aggiuntivi, T-005, ricalibrazione e API); verifica finale del file aggiuntivo: 8 test verdi. Test protetti identici alla Base. Nessun commit eseguito.
- `check_task` T-004: **ESITO non pronto (1 problemi)**, esclusivamente per i due test protetti descritti sopra. Non si dichiara la scheda pronta finché le fixture protette non vengono corrette dal loro autore/revisore con autorizzazione esplicita.

- T-005: codice e commit Gemini riletti; 64 test del comando della scheda verdi, test protetti invariati. Il suo `check_task` nella working tree condivisa segnala esclusivamente i quattro file della T-004 fuori dal perimetro T-005; nessun aggiramento del controllo o modifica alla scheda per nasconderli.

- Suite completa finale: **494 test in 350,151 s; 492 passano, 1 failure e 1 error**, entrambi nei due test protetti difettosi elencati sopra. Nessuna nuova regressione. `check_task` finale: 52 test, stessi due blocchi, **ESITO non pronto (1 problemi)**. `git diff --check` pulito.

### Codex · 11 ottobre 2026 · Correzione autorizzata delle fixture protette

- Il proprietario ha autorizzato esplicitamente la modifica delle due fixture protette dopo la revisione precedente. Gli altri test protetti restano invariati; nessuna modifica ulteriore al codice di produzione in questa fase.
- `test_recalculate_chained_limits_and_cumulative_delta`: sostituito il salto da 360 kcal con una correzione da 9 kcal (80 → 78 g), entro il limite di aderenza. Verificati senza condizioni il risultato `no_adjustment`, il target ancora a 1900, la proposta +30 con margine minimo 0 e cumulata −70, e il collegamento alla prima proposta. Baseline ricavata dalla formula esistente con intake effettivo 1800−9/14.
- `test_cooldown_allowed_for_same_checkin_blocked_for_different`: richiesta e approvazione concatenate ora obbligatorie con dati idonei. Per il caso negativo si mantiene una proposta corrente non scaduta e si modella una precedente approvazione recente relativa a un altro check-in. La transazione di preparazione si chiude prima della richiesta HTTP; assert sul codice `recalibration_cooldown`, senza patch del fingerprint.
- Verifica mirata: **28 test verdi**, comprendenti tutti i 20 test del file protetto e gli 8 aggiuntivi. Nessuna soglia, formula o scadenza modificata.

- Con ulteriore autorizzazione esplicita del proprietario, committato **solo** `tests/test_recalibration_correction.py`: `a066f94da2693666a03d551ec21f2a544c74ccef`. «Base» aggiornata a questo commit; scheda, test aggiuntivi e codice di produzione restano nella working tree senza commit.

- Verifica conclusiva dopo la correzione autorizzata: **494 test in 337,421 s, OK**. `check_task` con Base aggiornata: **52 test verdi, ESITO: pronto per revisione**. `git diff --check` pulito. I due blocchi della revisione precedente sono risolti; il file protetto è identico alla nuova Base. Stato: **pronto per revisione**.
