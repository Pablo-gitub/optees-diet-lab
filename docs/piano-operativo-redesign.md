# Piano operativo del redesign · Optees Diet Lab (v2.3)

9 ottobre 2026 · Bozza di Gemini dalla [guida dei requisiti v2.1](guida-requisiti-optees-diet.md), rivista da Claude sul codice attuale. Si innesta sulle fasi 0–5 ([roadmap UX](ux-redesign-roadmap.md), [registro lacune](registro-lacune.md)): niente va riprogettato se esiste già. Ogni tappa indica chi fa cosa.

## Regole di lavoro

Gemini è l'esecutore principale; Claude e Codex intervengono nei punti delicati. Regole complete per Gemini in [GEMINI.md](../GEMINI.md).

**Flusso di ogni compito**

1. **Scheda** in `docs/tasks/T-NNN-*.md` dal [modello](tasks/TEMPLATE.md): obiettivo, contratto, criteri di accettazione, commit di base, elenco chiuso dei file consentiti, test protetti, comando di test. Un comportamento per scheda.
2. **Test rossi** scritti da Codex (logica, edge case, permessi, migrazioni, cose che non devono cambiare) o da Claude (comportamento dell'interfaccia). Gemini può aggiungere test semplici, mai modificare quelli protetti.
3. **Implementazione** di Gemini finché i test passano, solo nei file consentiti.
4. **Controllo automatico**: `python scripts/check_task.py docs/tasks/<scheda>.md` verifica perimetro, test protetti invariati rispetto alla base, comando di test verde.
5. **Revisione**: Codex per il backend, Claude per l'interfaccia (anche visiva nel browser). Correzioni piccole le fa il revisore; altrimenti la scheda torna a Gemini con il motivo.
6. **Commit** di Claude, solo dopo revisione e suite completa verde.

**Chi fa cosa**

| Ruolo | Compiti |
|---|---|
| Gemini | Implementazione delle schede; dati lunghi (reparti, catalogo, esercizi, media); test semplici aggiuntivi |
| Codex | Test rossi del backend; parti delicate: formulazione del solver, regole di bilancio e check-in, migrazioni su dati reali, sicurezza e permessi; revisione backend |
| Claude | Schede e specifiche; test rossi dell'interfaccia; pagine più delicate e revisione visiva; script di controllo; commit |

- Test con il comando del progetto, mai sul database personale:
  `set -a; . ./.env; set +a; PYTHONPATH=scripts:tests:. ${DIET_PYTHON:-python} -m unittest discover -s tests`
- Ogni tappa chiude con suite verde, prova in browser a 360/390 px e desktop, voce aggiornata nel registro lacune.

## Decisioni del proprietario

| Decisione | Stato |
|---|---|
| Stato `presunto` per i pasti non toccati | Da confermare |
| Lettore audio dopo attrezzatura e carichi | Da confermare |
| HTTPS con `tailscale serve` (necessario solo per la fotocamera, tappa 6) | Da confermare: modifica di configurazione persistente |

## Già presente: verificare, non rifare

| Requisito | Dove esiste | Azione |
|---|---|---|
| Diversità tra alternative (~90%) | `week_orchestration.py`: `overlap_target=10`, `diversity_relaxed`, `ingredient_overlap.py` | Misurare sulle diete reali (tappa 3) |
| «Calcolane altre» | `week-planning.js`: `moreAlternativesButton` | Verificare che proponga davvero piani diversi |
| Compensazione con camminata | `rebalance_activity.py` (8.6) | Inserire nelle tre opzioni (tappa 3) |
| Prossimo pasto in primo piano, bozze dei pasti | Fase 3: `meal_drafts.py`, `meal-editor.js` | Mantenere |
| Questionario iniziale, gusti | Fase 2: `taste_onboarding.py` | Mantenere |
| Grafici energia, traguardi ordinati | Fase 5: `progress_dashboard.py`, `goal_milestones.py` | Mantenere; un criterio per traguardo (GOAL-01) |
| Obiettivi corporei, intervista sugli obiettivi | Profilo a tre passi, `setup.js`, fase 2 | Verificare circonferenze |
| Timing dei pasti oltre 60 min | 8.13: `nutrient_timing`, `mealTimingBlock` | Mantenere |
| Abbinamenti a scorrimento | 8.12: `meal_matches.py`, `matches.js` | Rifiniture touch (tappa 6) |
| Fotocamera e lettore codici | `barcode.js`: `getUserMedia` + `BarcodeDetector` | Aggiungere ripiego ZXing (tappa 6) |
| Importazione Salute | `POST /api/health/import` da `sanitary_data_export/` | Caricamento dal browser (tappa 6) |

## Sequenza

```
1 Navigazione e catalogo pulito
2 Diario a zero attrito (presunto)
3 Verifica varietà e sgarro a tre opzioni
4 Attrezzatura reale, carichi, lettore audio
5 Pasto composto (piatto principale + complementi)
6 Spesa per reparto, caricamento Salute, codice a barre
```

Motivo dell'ordine: 1–2 sono l'uso quotidiano e le lacune più visibili; 3 misura prima di cambiare il solver; 4 chiude WORK-02/03 (priorità alta nel registro); 5 è la modifica più profonda al MILP e richiede una specifica; 6 dipende da dati nuovi e dall'HTTPS.

---

## 1 · Navigazione e catalogo pulito

Chiude UX-01, UX-02, UX-03, FOOD-01.

**Claude** (`index.html`, `app.js`, `style.css`)
- Barra in basso a 4 voci: Oggi, Settimana, Allenamento, Cucina. Aree di tocco ≥ 48 px, etichette leggibili a 360 px.
- Header con avatar e menù: Profilo, Progressi, Gusti e abbinamenti, Impostazioni (con il tema), Esci separato. Tastiera, focus ed Escape.
- `aria-current="page"` sulla voce attiva; collegamento ai Progressi da Oggi.
- Le pagine esistenti restano raggiungibili; gli hash `#oggi`, `#settimana`… continuano a funzionare.

**Codex** (`recipe_diet_compatibility.py`, `web/app.py`)
- Catalogo di Cucina, ricerca e filtri restituiscono per default solo ricette `ready`.
- Preferiti diventati non utilizzabili: restano salvati, segnalati con il motivo.
- Test: `test_recipe_diet_compatibility`, `test_web`.

**Fatto quando**: nessuna ricetta non utilizzabile in Cucina; navigazione senza sovrapposizioni a 360/390 px, zoom 200% e desktop.

## 2 · Diario a zero attrito

Assegnazione: Claude scrive la regola nella scheda; Codex i test rossi (presunto calcolato in lettura, nessuna scrittura nelle GET, bilancio e check-in); Gemini implementa backend e distintivo in `today.js`; Codex e Claude rivedono.

**Codex** (`diary_service.py`, `progress_dashboard.py`)
- `presunto` è **calcolato in lettura**, non scritto da un aggancio: un pasto di un giorno passato ancora pianificato e non toccato viene restituito come `presumed`. Nessuna scrittura durante le GET; nessun conflitto con bozze e revisioni.
- Il diario restituisce `logged_slots` e `presumed_slots` separati.
- Regola del bilancio scritta nel contratto: il saldo del giorno si calcola anche con pasti presunti, marcato «con N pasti presunti»; il check-in del lunedì riporta la quota di presunti e non ricalibra se superano una soglia da definire.
- Test: `test_diary_service`, `test_progress_dashboard`, `test_progress_recalibration`.

**Claude** (`today.js`)
- Distintivo «presunto» sui pasti passati non toccati; «Salta» e «Modifica / Ho mangiato altro» a un tocco, con l'editor delle bozze esistente.

**Fatto quando**: un giorno lasciato invariato appare presunto il giorno dopo, il check-in lo distingue, nessun dato cambia aprendo una pagina.

## 3 · Verifica varietà e sgarro a tre opzioni

Assegnazione: la misura della varietà e la diagnosi del solver restano a Codex; le tre opzioni dello sgarro vanno a Gemini dopo i test rossi di Codex; schede di scelta a Gemini con revisione di Claude.

**Codex**
- Misura su profili sintetici simili alle diete reali (con banana e barrette): diversità ottenuta, quante volte scatta il rilassamento, perché. Rapporto in `docs/`. Si interviene sul solver solo se la misura mostra un problema.
- Sgarro in `meal_rebalance.py`: tre scenari confrontabili. Oggi (pasti rimanenti, con minimo per pasto); attività (riusa `rebalance_activity`, sempre proposta, mai imposta); giorni successivi (2–3 giorni). Ognuno con l'effetto sulla settimana.
- Test: `test_meal_rebalance`, `test_rebalance_activity`, `test_week_orchestration`, `test_ingredient_overlap`.

**Claude** (`rebalance.js`, `week-planning.js`)
- Tre schede di scelta con l'effetto in chiaro; confronto delle alternative che mostra cosa cambia.

**Fatto quando**: tre alternative visibilmente diverse sulle diete di prova, o motivo dichiarato quando non è possibile.

## 4 · Attrezzatura reale, carichi, lettore audio

Assegnazione: Codex scrive i test rossi di inventario, carichi componibili e migrazione; Gemini implementa modello, catalogo esercizi e lettore; la migrazione dei dati esistenti la rivede Codex prima del commit.

Chiude WORK-02, WORK-03, WORK-04.

**Codex** (`workout_configuration.py`, `workout_sessions.py`)
- Inventario: manubri fissi, manubri componibili, bilancieri, dischi con peso e quantità. Carichi montabili simmetrici, con dischi sufficienti per due manubri. Migrazione dei dati esistenti senza inventare dotazioni.
- Esercizi e protocolli per ogni attrezzo dichiarato; la UI mostra solo ciò che i programmi usano davvero.
- Carichi: si chiede il peso per 8–12 ripetizioni pulite nel contesto dell'esercizio; il massimale si **stima** (Epley/Brzycki), quello reale è facoltativo. Nessun invito a testare il massimale. Ultimo carico riusato nelle sessioni successive.
- Test: `test_workout_configuration`, `test_workout_sessions`, `test_workout_api`, `test_load_curve`.

**Claude** (`workout.js`, nuovo `workout-player.js`)
- Inventario con preset modificabili; unità sempre esplicite (per manubrio / totale sul bilanciere).
- Lettore: il tocco su «Avvia» sblocca l'audio (Safari lo richiede) e chiede lo schermo acceso (Wake Lock); bip di lavoro, recupero e cadenza; Pausa/Riprendi; «Serie completata» con un tocco. Dichiarato in UI: funziona con la pagina aperta in primo piano. Recupero basato su `rest_until` esistente.

**Fatto quando**: una sessione con bilanciere e dischi reali si genera, si esegue dal lettore su iPhone e si registra.

## 5 · Pasto composto

Assegnazione: formulazione nel solver a Codex (parte delicata); Gemini prepara l'insieme dei complementi e la scheda pasto dopo la specifica.

**Prima**: specifica breve di Claude + Codex in `docs/` — complementi ammessi per pasto, passi di porzione (es. 150/200/250 g), interazione con piatti fissati (8.7), preferiti e diete personali, cosa succede se non c'è soluzione.

**Codex** (`plan_diet_day.py`, `week_orchestration.py`)
- Piatto principale a porzione discreta + 1–2 complementi da un insieme qualificato.
- Test: `test_diet_day`, `test_recipe_solver`, `test_week_meal_e2e`.

**Claude**: scheda pasto che mostra piatto e complementi.

**Fatto quando**: una ricetta preferita (es. lasagne) entra nella settimana con porzione realistica e i vincoli rispettati.

## 6 · Spesa per reparto, caricamento Salute, codice a barre

Assegnazione: Gemini tabella dei reparti, spesa, ripiego ZXing e interfaccia; Codex scrive i test di sicurezza del caricamento Salute e decide il legame abbinamenti–bandit.

**Gemini**: tabella alimento → reparto per gli alimenti del catalogo, con fonte; revisione di Claude.

**Codex**
- `shopping_list.py`: raggruppamento per reparto, finestra 3 o 7 giorni, aromatici con «controlla in dispensa». Test: `test_week_report`.
- Caricamento Salute dal browser: stesso permesso di `health_import_allowed`, limite di dimensione, file temporaneo con permessi 0600, stessa importazione asincrona esistente. Nessuna apertura a utenti registrati. Test: `test_apple_health`, `test_web`.
- Abbinamenti: decidere e motivare se i giudizi alimentano `contextual_bandit.py` o restano nel sistema di preferenze di 8.12; un solo modo di imparare i gusti.

**Claude**
- Spesa per reparto con spunte; caricamento con barra di avanzamento; ripiego ZXing in `web/static/vendor/` per `barcode.js`; rifiniture touch degli abbinamenti.

**Prerequisito**: HTTPS con `tailscale serve`, solo dopo il sì del proprietario.

**Fatto quando**: spesa leggibile per reparto; import da iPhone o computer senza terminale; scansione funzionante su Safari iOS.

---

## Fuori da questo piano

Criteri multipli per traguardo (GOAL-01), verifica trasversale completa (QA-01/02, ex fase 6 UX): da pianificare dopo la tappa 2.
