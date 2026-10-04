# Piano di sviluppo — da prototipo a piattaforma dieta + palestra

Piano operativo a turni. La visione e i requisiti restano in [roadmap.md](roadmap.md); la catena algoritmica è specificata in [orchestration.md](orchestration.md). Aggiornato il 2026-10-04.

## Chi fa cosa

| Operatore | Compiti tipici | File di sua competenza |
|---|---|---|
| **Codex** | engine, formulazioni MILP, modello dati, servizi Python, endpoint API, import Salute | `scripts/`, schema SQLite, logica in `web/app.py`, `tests/` dell'engine |
| **Claude** | specifiche e contratti, interfaccia, flussi UX, revisione e QA del lavoro degli altri | `docs/` di specifica, `web/static/`, test web/UI |
| **Gemini** | lavori semplici o ad alto consumo di token: media, traduzioni, pulizia dati, fixture, controlli visivi in massa, aggiornamento documentazione | `config/*-media.json`, `config/recipe-images.json`, `web/static/media/`, traduzioni, `tests/fixtures/` |

Il lavoro di Gemini viene sempre **rivisto** da Claude (dati e media) o da Codex (fixture dell'engine) prima del commit. Le immagini vanno verificate guardandole, non solo dal nome del file.

## Regole dei turni

1. **Un solo operatore per area alla volta.** Codex e Gemini possono lavorare in parallelo solo su file disgiunti (vedi tabella sopra).
2. **Ogni passo si chiude con:** test verdi (`python -m pytest -q`), commit con messaggio descrittivo, riga di stato aggiornata qui sotto (stato + hash).
3. **Prima di iniziare un turno:** `git pull`/`git status` pulito; leggere le note di consegna del passo precedente.
4. **Note di consegna:** chi chiude un passo scrive nel commit cosa resta aperto e cosa il prossimo operatore deve sapere.
5. **Contratti prima del codice:** quando un passo cambia l'interfaccia fra engine e UI, si aggiorna prima la specifica (Claude), poi si implementa.
6. **Dati personali:** mai in Git, mai negli esempi, mai nelle fixture.

## Traguardi

- **M1 — Utilizzabile** (fine fase 3): settimana pianificata, alternative davvero diverse, diario con conferma rapida, palestra con registro delle sessioni.
- **M2 — Fatta bene** (fine fase 6): ottimizzazione congiunta dieta + palestra, check-in del lunedì con ricalibrazione, bandit sulle prove reali, ribilanciamento dopo uno sgarro.
- **M3 — Rifinita** (fine fase 7): app installabile sul telefono, job in background, QA completa.

## Sequenza dei turni

| Turno | Operatore | Passi | Parallelo |
|---|---|---|---|
| T1 | Claude | 1.1 | — |
| T2 | Codex | 0.1 · 0.2 · 1.2 · 1.4 | Gemini: 0.3 · 0.4 · 0.5 |
| T3 | Claude | 1.3 · revisione 0.3–0.5 · 2.1 | — |
| T4 | Codex | 2.2 · 2.3 | Gemini: 2.5 |
| T5 | Claude | 2.4 | **fatto** — pagina Oggi (diario con conferma, modifica, ricerca, alternative per pasto), striscia Settimana con budget, riquadri Statistiche, Piano settimanale, Progressi con misure; palestra e statistiche complete attendono 3.1 e 5.1 |
| T6 | Codex | 3.1 · 3.3 | — |
| T7 | Claude | 3.2 → **M1** | Gemini: 3.4 |
| T8 | Codex | 4.1 · 4.2 | — |
| T9 | Claude | 4.3 · 5.3 (UI su dati demo) | — |
| T10 | Codex | 5.1 · 5.2 | Gemini: 5.4 |
| T11 | Claude | revisione 5.x · 6.3 (UI sgarro) | Gemini: 6.4 |
| T12 | Codex | 6.1 · 6.2 → **M2** | — |
| T13 | Claude | 7.1 · 7.3 | Gemini: 7.4 · QA visiva |
| T14 | Codex | 7.2 → **M3** | — |

## Passi

Dimensioni indicative: **S** < 2 h, **M** 2–5 h, **L** > 5 h di lavoro dell'operatore.

### Fase 0 — Pulizia e media

| # | Passo | Chi | Dim. | Fatto quando | Stato |
|---|---|---|---|---|---|
| 0.1 | Committare il lavoro Salute in sospeso (`health_inputs.py`, test, `apple-health-import.md`, tabella in `app.js`, roadmap) | Codex | S | working tree pulito, test verdi | **fatto** — `4bfcb73`, 121 test verdi |
| 0.2 | Target demo coerenti: kcal ≈ 4P+4C+9G (±10%) in `config/demo-diet-day.json` e nei default giornalieri; controllo di coerenza in validazione profilo (S0 di orchestration.md) | Codex | S | test sul controllo; target demo coerenti | **fatto** — `d144771`, 126 test verdi; warning API pronti per la UI |
| 0.3 | **Media esercizi da Free Exercise DB.** Mappare gli esercizi usati nei protocolli (`config/workout-protocols.json`) agli id di `dataset/free_exercise_db/exercises.json`; scaricare solo le loro 2 immagini (pubblico dominio) in `web/static/media/exercises/<id>/`; sostituire le immagini Commons errate in `config/exercise-media.json`; tenere al massimo 2 video YouTube per esercizio, da canali di istruzione riconoscibili, scartando shorts e titoli clickbait | Gemini | M | ogni esercizio dei protocolli ha immagini locali corrette, verificate a vista; nessuna immagine di un esercizio diverso | **fatto con riserva** — revisione Claude: 20/20 immagini corrette; 20 video esistenti, titoli riallineati; 3 video da sostituire (R1) |
| 0.4 | **Foto ricette.** Estendere `config/recipe-images.json` almeno alle ricette italiane (81) e alle 25 composizioni del solver: Wikimedia Commons, licenza libera, foto del **piatto giusto** (non «ossobuco con risotto» per il risotto), attribuzione completa | Gemini | M | copertura ≥ 100 ricette, ogni foto controllata a vista | **parziale** — revisione Claude: 80 foto verificate (obiettivo 100); 50 ID inesistenti e 25 foto errate rimosse (R2) |
| 0.5 | **Titoli in italiano.** Campo `title_it` per le 834 ricette (traduzione fedele, nomi propri invariati: «Ackee and saltfish» resta tale), in un file di overlay versionato invece che nel catalogo originale | Gemini | M | overlay completo; la UI mostra `title_it` con fallback | **fatto** — 834/834; UI con titolo italiano, ricerca anche in italiano; ~25 titoli con aggettivo inglese da tradurre (R3) |

**Perché oggi non si vedono le foto e i video di Gemini:**

Consegna preparata per i passi 0.3–0.5: [prompt per Gemini](gemini-handoff-phase0.md). Revisione e rilavorazioni: [gemini-rework-phase0.md](gemini-rework-phase0.md).

**Rilavorazioni Gemini dopo la revisione T3** (in parallelo al prossimo turno di Codex):

| # | Rilavorazione | Fatto quando | Stato |
|---|---|---|---|
| R1 | Sostituire i 2 video dello squat e il video «Zero Healthcare» della cyclette | canali didattici; titolo e canale originali verificati via oEmbed | **fatto** |
| R2 | Portare le foto ricette verificate da 80 a ≥ 100, priorità alle italiane (20/81) e al solver (11/25) | ogni ID esiste; nessuna foto fra le scartate; controllo a vista | **fatto** — 105 verificate |
| R3 | Tradurre i titoli con aggettivo d'origine o nomi comuni inglesi («Argentinian empanadas» → «Empanadas argentine») | nessun titolo con aggettivo inglese; nomi propri invariati | **fatto** — 33 titoli |

- Il CSP del server bloccava ogni immagine esterna fino al commit `05710e1`.
- Le ricette con foto sono solo 4 su 834, e nel catalogo ordinato per titolo finiscono in pagine lontane.
- Per le 25 composizioni del solver la foto esiste solo per 2 (pasta al pomodoro dimostrativa e panino caprese), e la scheda «Adatta un piatto» non la mostra.
- Per la palestra: i media esistono per 10 esercizi, ma **non c'è ancora nessuna pagina palestra** (passo 3.2).
- Alcune immagini dei media esercizi sono errate: push-up → «Handstand pushup», squat → «squat thrust».

### Fase 1 — Orchestrazione della giornata

| # | Passo | Chi | Dim. | Fatto quando | Stato |
|---|---|---|---|---|---|
| 1.1 | Specifica della catena, vincolo di diversità, formato `PlanSet` (role, explanation, diff) | Claude | M | [orchestration.md](orchestration.md) approvato | **fatto** |
| 1.2 | Implementare S0–S7 per una giornata secondo orchestration.md; `/api/generate` restituisce un `PlanSet`; `strategy` ignorato con warning; bandit sui bracci-caratteristica | Codex | L | i 10 test del §9 di orchestration.md verdi; audit su 4 giornate reali con distanza media ≥ 3 | **fatto** — `608f411`, 134 test verdi; audit Optees su 4 giornate: distanza media 4–5 |
| 1.3 | UI: via il menu Metodo; badge ruolo, headline, chip del diff, warning in alto, dettagli tecnici con objectives/robustness/pool | Claude | M | verifica visiva desktop e mobile; nessun riferimento ai metodi fuori dai dettagli | **fatto** — ruoli, motivazioni, diff e warning; menu Metodo rimosso; solo l'ultima generazione visibile |
| 1.4 | Quantità «pesabili» nel modello: grammi a passi di 5 g (variabile intera × 5) o porzioni discrete per gli alimenti a pezzi; i totali restano verificati sui valori interi | Codex | S | nessuna quantità con decimali nei piani; test di verifica | **fatto** — `c508f92`, 136 test verdi; audit finale: distanze 4–5 dove ci sono alternative, 2 giornate con un solo piano non dominato |

### Fase 2 — Settimana e diario

| # | Passo | Chi | Dim. | Fatto quando | Stato |
|---|---|---|---|---|---|
| 2.1 | **Contratto API e modello dati** (`docs/api-contract.md`): settimana pianificata, pasto pianificato, voce di diario (consumato), misure manuali, stati proposto/scelto/eseguito/saltato, schermate Oggi e Settimana | Claude | M | documento approvato da te e letto da Codex | **fatto** — [api-contract.md](api-contract.md) approvato il 2026-10-04 |
| 2.2 | Schema SQLite con migrazione e endpoint del contratto: diario (conferma pasto, aggiungi, togli, modifica grammi), totali previsto/consumato, ricerca alimenti (CREA + marca + tue etichette) | Codex | L | test API; un dato mancante non vale zero | **fatto** — `1529abd`, 143 test verdi; API pronte per Claude |
| 2.3 | Orizzonte settimanale (v2 di orchestration.md, solo dieta): 7 giorni in un problema, ripetizioni limitate, frequenze della dieta, giorni/pasti bloccati | Codex | L | settimana fattibile per entrambe le diete; nessuna fonte proteica principale > N volte | **fatto** — `388c632`, 158 test verdi; 4 settimane fattibili con Optees (3 partial); limite per alimento principale |
| 2.4 | UI pagina iniziale unica (Oggi → Settimana → Statistiche, §1 di api-contract.md): **Oggi** (timeline dei pasti, «mangiato come previsto» con un tocco, modifica/aggiungi/togli, anello kcal/proteine previsto vs consumato) e **Settimana** (griglia 7 giorni, budget settimanale, «altre opzioni» per pasto) | Claude | L | flusso completo provato su telefono: confermare una giornata intera in meno di 30 s | da fare |
| 2.5 | Fixture: settimana dimostrativa sintetica, diario con deviazioni, casi limite (pasto saltato, extra) in `tests/fixtures/` | Gemini | S | fixture usate dai test di 2.2/2.4; nessun dato personale | da fare |

### Fase 3 — Palestra → **M1**

| # | Passo | Chi | Dim. | Fatto quando | Stato |
|---|---|---|---|---|---|
| 3.1 | API palestra: catalogo sessioni, settimana da `plan_workout_week.py` con disponibilità (minuti per giorno, giorni esclusi), registro sessione eseguita (esercizi, serie, ripetizioni, kg, RPE) | Codex | M | test API; sessioni eseguite separate da quelle pianificate | **fatto** — `18ab5c6`, 166 test verdi; audit Optees reale: 2 settimane candidate verificate (67,83 e 106 minuti); [consegna backend](backend-handoff-workouts.md) |
| 3.2 | UI **Allenamento**: settimana, dettaglio sessione con cronologia (riscaldamento/lavoro/recuperi), immagini e video, registrazione serie rapida durante l'allenamento | Claude | L | sessione registrabile da telefono senza digitare più del necessario | da fare |
| 3.3 | Configurazione personale dei protocolli: livello, carichi di partenza, attrezzatura reale, varianti eseguibili; le bozze demo restano marcate | Codex | M | nessun carico inventato; i campi mancanti sono chiesti all'utente | **fatto** — commit di chiusura 3.3, 175 test verdi; configurazione privata, domande sui campi mancanti, nessun carico inventato; audit Optees reale con profilo sintetico completo; [consegna backend](backend-handoff-workouts.md) |
| 3.4 | QA media nella UI: ogni esercizio mostra immagini corrette e video funzionanti; elenco delle anomalie | Gemini | S | rapporto con screenshot; correzioni in `exercise-media.json` | da fare |

### Fase 4 — Ottimizzazione congiunta dieta + palestra

| # | Passo | Chi | Dim. | Fatto quando | Stato |
|---|---|---|---|---|---|
| 4.1 | Candidati congiunti: tipo di giornata (allenamento/riposo) → target del giorno; dispendio da scenari Salute + modelli per attività senza doppio conteggio; `training_fit` in S3 | Codex | L | settimana congiunta con ruoli e diff che includono le sessioni | da fare |
| 4.2 | Robustezza S4 completa (Min-Max e regret sugli scenari) ed estensione a `scenario.linear.min_max_loss` di Optees quando la formulazione è lineare | Codex | M | ruolo `robust` presente quando Salute è disponibile; test con scenari sintetici | da fare |
| 4.3 | UI: card settimana con allenamenti, spiegazione della robustezza in linguaggio semplice | Claude | M | verifica visiva | da fare |

### Fase 5 — Progressi e check-in del lunedì

| # | Passo | Chi | Dim. | Fatto quando | Stato |
|---|---|---|---|---|---|
| 5.1 | Trend del peso (media mobile esponenziale, poi filtro di Kalman semplice); aderenza dieta/allenamento; confronto atteso vs osservato separando «piano non seguito» da «risposta diversa dal previsto» | Codex | M | test su serie sintetiche con rumore | da fare |
| 5.2 | Proposta di ricalibrazione: dispendio personale stimato con limiti di sicurezza fissi (variazione massima settimanale, minimi nutrizionali); l'utente approva | Codex | M | nessuna modifica automatica dei target; limiti mai superati | da fare |
| 5.3 | UI **Progressi**: inserimento peso del lunedì, grafico reale vs atteso, aderenza, proposta di ricalibrazione con motivazione | Claude | M | verifica visiva; grafici leggibili in chiaro e scuro | da fare |
| 5.4 | Guida all'aggiornamento periodico dell'export Apple Salute/Withings e controllo della copertura | Gemini | S | `docs/apple-health-import.md` aggiornato | da fare |

### Fase 6 — Apprendimento e ribilanciamento → **M2**

| # | Passo | Chi | Dim. | Fatto quando | Stato |
|---|---|---|---|---|---|
| 6.1 | Bandit contestuale sui bracci-caratteristica con ricompensa da voto + aderenza (S6 completo) | Codex | M | test: solo piani provati; contesti separati | da fare |
| 6.2 | **Ribilanciamento**: «Ho sgarrato» → stima a intervallo del pasto → riottimizzazione dei giorni rimanenti con il consumato bloccato; deficit giornaliero massimo, proteine protette, correzione distribuita; palestra solo come opzione aggiuntiva | Codex | L | la settimana rientra nei confini quando possibile; altrimenti lo dice, senza punire | da fare |
| 6.3 | UI sgarro: scelta tipo (pizzeria, ristorante, aperitivo, dolce, libero) e taglia, impatto sul budget, anteprima del diff sui giorni successivi, Accetta/Modifica/Non compensare; tono non colpevolizzante | Claude | M | flusso completo in meno di 4 tocchi | da fare |
| 6.4 | Catalogo preset degli sgarri con intervalli di kcal e macro e fonti citate | Gemini | S | `config/meal-presets.json` con fonti; rivisto da Claude | **respinto** — fonti inventate, da rifare (vedi gemini-rework-phase0.md) |

### Fase 7 — Rifinitura → **M3**

| # | Passo | Chi | Dim. | Fatto quando | Stato |
|---|---|---|---|---|---|
| 7.1 | PWA: manifest, icone, service worker per la shell offline, installazione su iPhone | Claude | M | icona sulla home, apertura a schermo intero | da fare |
| 7.2 | Processo Optees MCP riutilizzato, coda dei job con stato e annullamento | Codex | M | generazione settimanale non blocca il server; stato visibile | da fare |
| 7.3 | Accessibilità e QA mobile completa (contrasti, focus, lettori di schermo, dark mode) | Claude | M | checklist superata | da fare |
| 7.4 | README e documentazione aggiornati; screenshot delle schermate | Gemini | S | documenti coerenti con il codice | da fare |

## Fuori da questo piano

Riconoscimento dei pasti da foto, sincronizzazione live con Withings/HealthKit (app iOS ponte), WorkoutKit, prezzi automatici, ottimizzazione fine della progressione dei carichi, multiutente oltre i profili locali.

## Correzioni dopo la consegna T3/T5

| Passo | Stato | Verifica |
|---|---|---|
| B1–B5 | **fatto** — `9e45ae0` | 162 test verdi; end-to-end HTTP con Optees reale: settimana generata e applicata → alternative pranzo applicate, cena invariata; binarie bloccate con uguaglianze; warning unico; ricerca ordinata, incluso mela → mele CREA (regressione sui dati reali); provenienza del passato separata dal nome |
