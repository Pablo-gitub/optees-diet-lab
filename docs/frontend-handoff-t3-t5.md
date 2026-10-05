# Consegna interfaccia T3/T5 e segnalazioni per Codex

Data: 2026-10-04. Passi chiusi da Claude: revisione Gemini (0.3–0.5, R1–R3), 2.1, 1.3, 2.4.

## Cosa usa l'interfaccia

- **Oggi** (`web/static/today.js`): `GET /api/day`, `GET /api/week`, `GET /api/stats/summary`; diario con `POST /api/diary/confirm|skip|reset`, `POST/PATCH/DELETE /api/diary/entries`; ricerca `GET /api/foods/search`; alternative per pasto con `POST /api/plans/meal-alternatives` → `GET /api/jobs/{id}` → `GET /api/plan-sets/{id}` → `POST /api/plan-sets/{id}/apply` (`scope: meal`).
  «✎ Modifica» su un pasto non registrato con piano esegue prima `confirm`, poi apre la modifica delle righe di diario.
- **Piano · Settimana**: `POST /api/plans/week` → job → PlanSet → `apply` con `scope: week`.
- **Piano · Esplora una giornata**: `POST /api/generate` (PlanSet v1), card con `role`, `explanation`, `diff`, `warnings`. Mostra solo l'ultima generazione (piani creati entro 15 s) più l'eventuale piano scelto.
- **Progressi**: `POST/GET /api/measurements`, riquadri da `stats/summary`, sezione Apple Salute invariata.
- **Attività**: legge `day.workout` secondo il contratto §4.1; oggi è sempre `null`.

## Segnalazioni per Codex (da risolvere nel prossimo turno)

| # | Problema | Riproduzione | Proposta |
|---|---|---|---|
| B1 | **Alternative per pasto sempre in errore** («Variabile fuori limite») | applicare una settimana, poi `POST /api/plans/meal-alternatives` su un pasto non registrato. In `values_verified` le variabili `locked_y*` con `lb=1, ub=1, integrality=B` tornano a 0 dal solver | bloccare con vincoli di uguaglianza `y = 1` (e `q = grammi`) invece che con i limiti della variabile; aggiungere un test end-to-end settimana → alternative |
| B2 | Catena della giornata: un solo piano, `min_distance` ridotta a 1 dopo la discretizzazione a 5 g | `POST /api/generate` giorno 0, programma sedentario | verificare la diversità strutturale con le variabili intere; se resta un solo piano va bene, ma il warning deve dirlo una volta sola |
| B3 | La motivazione del piano `best` contiene «0 alimenti principali diversi dal riferimento» | qualsiasi `generate` | omettere le motivazioni di distanza per `best` |
| B4 | Ricerca alimenti: per parole generiche («mela») escono prima prodotti di marca senza valori | `GET /api/foods/search?q=mela` | a parità di pertinenza, prima i risultati con valori completi e le corrispondenze CREA del nome; la UI già sposta in fondo i prodotti senza valori |
| B5 | Nome tecnico visibile: «Passato dimostrativo: 50% zucchine bollite CREA 005735» | settimana sedentaria, mercoledì cena | campo `name` leggibile per gli alimenti composti dimostrativi |

Prossimo turno di Codex: B1–B5, poi 3.1 e 3.3 (palestra).

## Esito Codex — B1–B5

Corretti il 2026-10-04. Suite: 162 test verdi. B1 verificato con il processo MCP Optees reale in `tests/test_week_meal_e2e.py`, dalla generazione e applicazione di una settimana alle alternative e applicazione di un singolo pasto. Gli altri pasti e il consumato restano invariati. B2 mantiene i vincoli interi e strutturali, con un solo warning quando il fronte contiene un solo piano; B3 omette la distanza per best; B4 ordina per pertinenza, completezza e fonte; B5 espone composizione/provenienza separatamente dal nome leggibile.

## Passo 3.2 — Allenamento (2026-10-04)

Pagina **Allenamento** (`web/static/workout.js`), tre schede:

- **Settimana**: sessioni della settimana corrente lette da `GET /api/day` dei 7 giorni; generazione con minuti per giorno (`POST /api/workouts/week`, `excluded_days` = giorni a 0, `demo: true`), card con ruolo e minuti, `apply` con `scope: week`; catalogo con «Inizia oggi» (avvio senza piano).
- **Sessione**: intestazione con intensità (RIR/RPE), avviso bozza e configurazione mancante, cronologia proporzionale (riscaldamento, lavoro, recuperi, defaticamento), esercizi con le due foto locali, video come link esterni (il CSP non consente iframe né miniature YouTube), registro serie (`POST /api/workouts/{id}/sets`) con ripetizioni, kg per manubrio quando `load_basis = kg_per_dumbbell`, secondi o minuti per tenute e cardio; timer di recupero dopo ogni serie; conclusione con RPE 1–10 e note.
- **Configura**: domande da `GET /api/workouts/config` (livello, conferme, attrezzi, pesi disponibili, carichi di partenza, varianti eseguibili); `PATCH` con le mappe complete unite a quelle correnti.

In **Oggi** la scheda Attività ha Inizia/Apri/Salta/Continua; la striscia della settimana mostra 🏋 nei giorni con sessione.

### Segnalazioni per Codex

| # | Osservazione | Proposta |
|---|---|---|
| W1 | `day.workout` espone una sola sessione: se si avvia una sessione libera dal catalogo nello stesso giorno, la sessione pianificata del giorno (es. cyclette) sparisce dalla vista | esporre `workouts: [...]` nel DayView (pianificate + libere), mantenendo `workout` per compatibilità |
| W2 | Una sessione avviata conserva `pending_configuration` del momento dell'avvio anche dopo aver completato la configurazione | comportamento corretto (snapshot immutabile); valutare un campo `configuration_at_start` per spiegarlo in UI |
| W3 | Durate frazionarie (28,5 min, 10,83 min) | arrotondare `minutes` al minuto nelle risposte, mantenendo i secondi esatti in `duration_seconds` |

### Esito Codex W1–W3

176 test verdi. DayView espone `workouts` (piani e log liberi senza duplicare un log collegato), mantenendo `workout` per compatibilità. `configuration_at_start` rende esplicito lo snapshot nei log e nelle schede. `minutes` è arrotondato al minuto, `duration_seconds` e i vincoli del solver restano esatti.

## 4.3 — Settimana congiunta nella UI (Claude, 2026-10-04)

In **Piano → Settimana** l'opzione «Pianifica anche l'allenamento» chiama `POST /api/plans/joint-week` con: minuti per giorno (condivisi con la pagina Allenamento), `day_targets` riposo/allenamento (partono da `daily_meals.targets` del profilo; intervalli modificabili), `energy_balance_target_kcal` esplicito (`null` = non indicato, 0 = mantenimento) e `workout.demo:true`. Le scelte restano nel browser (`diet-joint-settings`). Le card congiunte mostrano tipo di giornata, sessioni, kcal/obiettivo del giorno, differenze di sessioni (aggiunte/tolte/spostate) e, in un riquadro richiudibile, le differenze negli alimenti. La robustezza è spiegata con i tre scenari di consumo (errore medio giornaliero), il caso peggiore e il rimpianto; i warning `robustness_unavailable`/`robust_role_omitted` sono sostituiti da spiegazioni in chiaro. W1 e W2 sono usati: Oggi e Allenamento mostrano tutte le sessioni del giorno (con «fuori piano»), e una sessione avviata prima di completare la configurazione lo spiega.

### Osservazioni per Codex

| # | Osservazione | Proposta |
|---|---|---|
| B6 | `GET /api/profile` aggiunge `daily_meals` di default (abilitato per i profili personali), ma `owner_profile` no: con un profilo mai salvato la settimana congiunta risponde 400 «Attiva colazione e spuntini» anche se il profilo mostra l'opzione attiva | applicare lo stesso default in `owner_profile` (o salvarlo alla creazione dell'utente) |
| B7 | Il ruolo `explore` può avere la stessa scheda palestra di `varied` e differire solo nella dieta | valutare la diversità minima anche sulle sessioni quando il pool palestra ha più candidati |

B6 risolto: default condivisi da GET profilo e owner_profile, senza scritture implicite nel profilo. Test su profilo appena creato e su nuove abitudini personali mai salvate.

B7 risolto: explore preferisce una scheda diversa da varied tra i candidati distinti ancora sul fronte; se non esiste, explanation dichiara l’esplorazione soltanto alimentare. Test della preferenza e del fallback.

## 5.3 — Progressi (Claude, 2026-10-05)

La pagina usa `GET /api/stats/progress`, `POST /api/progress/check-in`, `GET /api/progress/recalibrations` e le decisioni approve/reject (contratto in [backend-handoff-progress.md](backend-handoff-progress.md)). Dopo un'approvazione la UI sostituisce il profilo in memoria con quello restituito e dimentica i target salvati nel browser. In Piano, bilancio e obiettivi per tipo di giornata della settimana congiunta sono salvati nel profilo (`PUT /api/profile` completo), così la ricalibrazione li trova e la pagina li riprende dopo un'approvazione.

### Osservazioni per Codex

| # | Osservazione | Proposta |
|---|---|---|
| B9 | L'andamento filtrato resta molto sopra le pesate recenti: con pesate quotidiane in calo di ~0,3 kg/settimana la linea mostra −0,1 kg in 7 giorni. EMA (emivita 7 giorni) seguita da Kalman sul risultato EMA smussa due volte e introduce un forte ritardo | applicare il Kalman alle mediane giornaliere (non all'EMA), oppure esporre l'EMA da sola come andamento; verificare il ritardo con un test su una discesa lineare nota |
| B10 | Il lunedì i riquadri «della settimana» di `GET /api/stats/summary` (aderenza, kcal medie, allenamenti) sono tutti «dati insufficienti», proprio il giorno del check-in | quando la settimana corrente non ha giorni trascorsi, riportare l'ultima settimana conclusa con `week_start` esplicito |

### Chiusura backend B9–B10 e consegna 6.2

B9: `7a4e12e`, filtro Kalman diretto sulle mediane giornaliere, parametri progress-v2; trend da regressione settimanale. B10: `919e014`, il lunedì riquadri dell’ultima settimana conclusa con week_start. Per Claude 6.3: [contratto ribilanciamento](backend-handoff-rebalance.md), anteprima e decisioni implementate; 228 test verdi, inclusa prova HTTP con Optees reale e database invariato dopo l’anteprima.

Consegna 6.1: [bandit contestuale v2](backend-handoff-bandit.md). Le valutazioni rimangono compatibili, ma `learning` distingue voto salvato da prova eleggibile; `GET /api/bandit/summary` spiega copertura e contesti. 236 test verdi, compresi isolamento training/rest e caratteristiche realmente provate.

## 6.3 — Pasto fuori programma (Claude, 2026-10-05)

In **Oggi** ogni pasto non ancora registrato della settimana corrente (fino a oggi) ha «Fuori programma»: scelta del tipo (la taglia media è preselezionata e l'anteprima parte subito), taglie con kcal, «Altro» con i quattro nutrienti a intervallo, anteprima con stima e fonti, stato (completo/parziale/invariato/non calcolabile), margine residuo, giorni toccati con le modifiche raccolte, limiti, e le due decisioni. Il pasto registrato appare come «Fuori programma ≈ min–max kcal» con la provenienza; si può solo azzerare. Verificato su una settimana reale generata da Optees con scenari Salute sintetici: anteprima in ~7 s, «Lascia il piano com'è» e «Accetta il rientro» funzionanti.

### Osservazioni per Codex

| # | Osservazione | Proposta |
|---|---|---|
| B11 | Il bandit (6.1) impara dai voti, ma `DayView` non espone il piano della giornata: la UI non può offrire «Com'è andata la giornata?» in Oggi | aggiungere a `DayView` `plan_id` (o un riferimento valutabile) e la valutazione già data, così la UI chiama `POST /api/plans/{id}/feedback` |
| B12 | **Bloccante per l'uso reale.** L'anteprima minimizza solo le calorie: per togliere 61 kcal in sei giorni ha prodotto 71 modifiche ai pasti, sostituendo pasti interi (riso → pizza il giorno dopo una pizza, barretta → banane a colazione) | minimizzare lo scostamento dal piano esistente (stessi alimenti, solo grammi; poi, se serve, sostituzioni con un costo), lasciando colazione e spuntini come ultima leva; test: con un surplus piccolo cambiano solo grammi |

### B13 — Rientro da qualunque scostamento registrato (richiesta di Paolo, 2026-10-05)

Lo scostamento non è solo uno «sgarro» con preset: può essere pasta 120 g invece di 100, una mela non prevista, un ingrediente sostituito, un alimento tolto, un pasto saltato. Il diario lo registra già con valori esatti (modifica grammi, aggiungi, togli e, dal 6.3, «⇄ Sostituisci» nella modifica del pasto). Manca il rientro.

| Requisito | Dettaglio |
|---|---|
| Fonte dello scostamento | Differenza fra consumato e previsto dei pasti già registrati della settimana corrente (esatta dove nota; intervallo per i pasti stimati), oltre all'eventuale pasto fuori programma in anteprima. Nessun valore inventato: pasti senza nutrienti noti ⇒ indisponibile con motivo |
| Endpoint | `POST /api/rebalance/preview {"date":"…","from_diary":true}` (o un endpoint dedicato), stessa risposta e stesse decisioni `apply`/`keep` del 6.2; `keep` qui non registra nulla, chiude soltanto |
| Simmetria | Se si è mangiato **meno** del previsto, proporre di restituire parte delle calorie nei giorni successivi entro i massimi dei target (stessa distribuzione e stessi limiti per giorno); mai oltre lo scostamento minimo stimato |
| Cambio minimo (B12) | Prima i grammi degli stessi alimenti, poi sostituzioni con un costo; colazione e spuntini come ultima leva; mai lo stesso piatto dello sgarro nei giorni successivi |
| Soglia | Sotto una soglia dichiarata (es. ±100 kcal sulla settimana) stato `unchanged` con spiegazione: piccoli scostamenti non vanno compensati |
| Test | Pasta +20 g ⇒ `unchanged` o solo grammi; mela aggiunta + cena saltata si compensano; scostamento negativo restituisce kcal senza superare i massimi; pasti registrati e passati intatti |

### Chiusura backend B12

239 test verdi. `change_policy` espone il livello scelto e i costi; il diff e l’applicazione comprendono solo i pasti cambiati. Grammi degli stessi prodotti prioritari, porzioni personali e minimi protetti, colazione/spuntini fissi nel primo livello; tutte le pizze escluse dopo il preset pizzeria. [Audit prima/dopo](rebalance-b12-audit.md). Nessuna modifica a web/static/.
