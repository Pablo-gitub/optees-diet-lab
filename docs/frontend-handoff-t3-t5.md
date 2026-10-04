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
