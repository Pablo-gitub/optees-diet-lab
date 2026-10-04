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
