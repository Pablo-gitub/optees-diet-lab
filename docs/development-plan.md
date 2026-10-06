# Piano di sviluppo — da prototipo a piattaforma dieta + palestra

Piano operativo a turni. La visione e i requisiti restano in [roadmap.md](roadmap.md); la catena algoritmica è specificata in [orchestration.md](orchestration.md). Aggiornato il 2026-10-05.

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

- **M1 — Utilizzabile** (fine fase 3, **raggiunto il 2026-10-04**): settimana pianificata, alternative davvero diverse, diario con conferma rapida, palestra con registro delle sessioni.
- **M2 — Fatta bene** (fine fase 6): ottimizzazione congiunta dieta + palestra, check-in del lunedì con ricalibrazione, bandit sulle prove reali, ribilanciamento dopo uno sgarro.
- **M3 — Rifinita** (fine fase 7): app installabile sul telefono, job in background, QA completa.
- **M4 — Personale** (fine fase 8): intervista iniziale con obiettivi, attività anche fuori dalla palestra, carichi personali, calorie che seguono l'attività, rientro anche con una passeggiata, ricette preferite nel solver, alternative diverse almeno al 90%, codice a barre, prodotti del supermercato e lista della spesa.

## Sequenza dei turni

| Turno | Operatore | Passi | Parallelo |
|---|---|---|---|
| T1 | Claude | 1.1 | — |
| T2 | Codex | 0.1 · 0.2 · 1.2 · 1.4 | Gemini: 0.3 · 0.4 · 0.5 |
| T3 | Claude | 1.3 · revisione 0.3–0.5 · 2.1 | — |
| T4 | Codex | 2.2 · 2.3 | Gemini: 2.5 |
| T5 | Claude | 2.4 | **fatto** — pagina Oggi (diario con conferma, modifica, ricerca, alternative per pasto), striscia Settimana con budget, riquadri Statistiche, Piano settimanale, Progressi con misure; palestra e statistiche complete attendono 3.1 e 5.1 |
| T6 | Codex | 3.1 · 3.3 | **fatto** — `18ab5c6`, `dd599f5` |
| T7 | Claude | 3.2 → **M1** | Gemini: 3.4 · **fatto** — `fcacbf2`, Gemini 6.4 `ce54515`, 3.4 `804caae`; **M1 raggiunto** |
| T8 | Codex | 4.1 · 4.2 | **fatto** — W1–W3 `652da35`, `a8c411a`, `ee2fa5b` |
| T9 | Claude | 4.3 · 5.3 (UI su dati demo) | **fatto** — 4.3 `c732350`; 5.3 (vedi riga 5.3); Gemini 5.4 rivisto `21c128a` |
| T10 | Codex | 5.1 · 5.2 | **fatto** — B6 `72f9660`, B7 `882f5cf`, 5.1 `dc4df6b`, `824daba`; Gemini 5.4 separato |
| T11 | Claude | revisione 5.x · 6.3 (UI sgarro) | Gemini: 6.4 · **fatto** — Gemini 6.4 `c2bc4dd`; UI B11/B13 collegata (handoff); B14/B15 corretti nel backend |
| T12 | Codex | 6.2 → 6.1 → **M2** | **backend fatto** — B9/B10 e B11–B15 chiusi, 263 test verdi; UI B11/B13 collegata, correzioni compatibili B14/B15 consegnate |
| T13 | Claude | 7.1 · 7.3 | Gemini: 7.4 · QA visiva |
| T14 | Codex | 7.2 → **M3** | — |
| T15 | Claude | 8.0 specifica · 8.2 matrice obiettivi → dosi con fonti | Gemini: 8.3a catalogo attività · 8.8 sessione 1 |
| T16 | Codex | 8.1 backend · 8.10 API codice a barre e prodotti personali · 8.9 alternative diverse | Gemini: 8.8 sessione 2; Claude rivede le sessioni 8.8 |
| T17 | Claude | UI 8.1 intervista · 8.10 scanner · 8.9 «Calcola altre» | Gemini: 8.8 sessione 3 |
| T18 | Codex | 8.3 attività · 8.4 carichi, durata, poco tempo · 8.5 calorie dall'attività | **fatto backend** — contratto aggiornato, UI T19 da fare. Gemini: 8.8 sessione 4 · equivalenti supermercato (S1) |
| T19 | Claude | UI 8.3–8.5 | Gemini: 8.8 sessioni successive |
| T20 | Codex | 8.6 rientro con attività · 8.7 piatti bloccati e preferite · 8.11 supermercati e lista della spesa | Gemini: equivalenti supermercato (S2…) |
| T21 | Claude | UI 8.6, 8.7, 8.11 · QA della fase → **M4** | — |

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
| 3.2 | UI **Allenamento**: settimana, dettaglio sessione con cronologia (riscaldamento/lavoro/recuperi), immagini e video, registrazione serie rapida durante l'allenamento | Claude | L | sessione registrabile da telefono senza digitare più del necessario | **fatto** — pagina Allenamento: settimana con generazione per disponibilità, sessione con cronologia, foto e video, registro serie con timer di recupero, conclusione con RPE, configurazione personale; scheda attività e striscia settimana in Oggi |
| 3.3 | Configurazione personale dei protocolli: livello, carichi di partenza, attrezzatura reale, varianti eseguibili; le bozze demo restano marcate | Codex | M | nessun carico inventato; i campi mancanti sono chiesti all'utente | **fatto** — `dd599f5`, 175 test verdi; configurazione privata, domande sui campi mancanti, nessun carico inventato; audit Optees reale con profilo sintetico completo; [consegna backend](backend-handoff-workouts.md) |
| 3.4 | QA media nella UI: ogni esercizio mostra immagini corrette e video funzionanti; elenco delle anomalie | Gemini | S | rapporto con screenshot; correzioni in `exercise-media.json` | **fatto** — rapporto in [gemini-rework-phase0.md](gemini-rework-phase0.md); 11 sessioni e 20 video verificati; foto errata del plank corretta (revisione Claude: confermata) |

### Fase 4 — Ottimizzazione congiunta dieta + palestra

| # | Passo | Chi | Dim. | Fatto quando | Stato |
|---|---|---|---|---|---|
| 4.1 | Candidati congiunti: tipo di giornata (allenamento/riposo) → target del giorno; dispendio da scenari Salute + modelli per attività senza doppio conteggio; `training_fit` in S3 | Codex | L | settimana congiunta con ruoli e diff che includono le sessioni | **fatto** — `a8c411a`; 188 test verdi e audit Optees di una settimana completa |
| 4.2 | Robustezza S4 completa (Min-Max e regret sugli scenari) ed estensione a `scenario.linear.min_max_loss` di Optees quando la formulazione è lineare | Codex | M | ruolo `robust` presente quando Salute è disponibile; test con scenari sintetici | **fatto** — `ee2fa5b`; 196 test verdi; audit Optees Min-Max/regret, verificati indipendentemente |
| 4.3 | UI: card settimana con allenamenti, spiegazione della robustezza in linguaggio semplice | Claude | M | verifica visiva | **fatto** — Piano → «Pianifica anche l’allenamento»: minuti per giorno, obiettivi riposo/allenamento con intervalli, bilancio calorico esplicito; card a piena larghezza con tipo di giornata, sessioni, kcal/obiettivo, differenze di sessioni e alimenti; riquadro «Se il tuo consumo cambia» con i tre scenari, caso peggiore e rimpianto; motivi di indisponibilità in chiaro. Verificato con Optees reale (76 s, 3 piani, applicazione di 35 pasti e 3 allenamenti) e con scenari sintetici per la robustezza; telefono e tema scuro |

### Fase 5 — Progressi e check-in del lunedì

| # | Passo | Chi | Dim. | Fatto quando | Stato |
|---|---|---|---|---|---|
| 5.1 | Trend del peso (EMA separata, Kalman diretto sulle mediane giornaliere dopo B9); aderenza dieta/allenamento; confronto atteso vs osservato separando «piano non seguito» da «risposta diversa dal previsto» | Codex | M | test su serie sintetiche con rumore | **fatto** — `dc4df6b`; 209 test unittest verdi; EMA/Kalman, copertura, aderenza, confronto e check-in; [consegna backend](backend-handoff-progress.md) |
| 5.2 | Proposta di ricalibrazione: dispendio personale stimato con limiti di sicurezza fissi (variazione massima settimanale, minimi nutrizionali); l'utente approva | Codex | M | nessuna modifica automatica dei target; limiti mai superati | **fatto** — `824daba`; 221 test unittest verdi; proposte motivate, limiti fissi, decisioni CSRF atomiche e conflitti 409; [consegna frontend 5.3](backend-handoff-progress.md) |
| 5.3 | UI **Progressi**: inserimento peso del lunedì, grafico reale vs atteso, aderenza, proposta di ricalibrazione con motivazione | Claude | M | verifica visiva; grafici leggibili in chiaro e scuro | **fatto** — check-in del lunedì con analisi della settimana; grafico SVG pesate + andamento filtrato + peso atteso per settimana (fasce, mai collegate); settimane con aderenza dieta/allenamento e confronto in chiaro; proposta di ricalibrazione con prima/dopo, motivazione, consumo stimato con intervallo, limiti e Approva/Non ora; cronologia. Piano: bilancio e obiettivi per tipo di giornata salvati nel profilo. Verificato su dati sintetici (proposta +90 kcal limitata da +466, approvazione 1800→1890), telefono e tema scuro |
| 5.4 | Guida all'aggiornamento periodico dell'export Apple Salute/Withings e controllo della copertura | Gemini | S | `docs/apple-health-import.md` aggiornato | **fatto** — guida di Gemini rivista da Claude: importazione il lunedì mattina dopo la pesata (non la domenica), soglie verificate nel codice |

### Fase 6 — Apprendimento e ribilanciamento → **M2**

| # | Passo | Chi | Dim. | Fatto quando | Stato |
|---|---|---|---|---|---|
| 6.1 | Bandit contestuale sui bracci-caratteristica con ricompensa da voto + aderenza (S6 completo) | Codex | M | test: solo piani provati; contesti separati | **fatto** — `3f78cfc`; 236 test verdi; ricompensa voto + aderenza, provenienza delle applicazioni, UCB1 contestuale per dieta e protocolli; [consegna backend](backend-handoff-bandit.md) |
| 6.2 | **Ribilanciamento**: «Ho sgarrato» → stima a intervallo del pasto → riottimizzazione dei giorni rimanenti con il consumato bloccato; deficit giornaliero massimo, proteine protette, correzione distribuita; palestra solo come opzione aggiuntiva | Codex | L | la settimana rientra nei confini quando possibile; altrimenti lo dice, senza punire | **fatto** — `d0d701a`; 228 test verdi alla chiusura, 237 nella verifica finale (anche spuntino pomeridiano facoltativo disattivato); anteprima Optees senza scritture, limiti fissi, consumato bloccato, azioni CSRF/409; [contratto 6.3](backend-handoff-rebalance.md) |
| 6.3 | UI sgarro: scelta tipo (pizzeria, ristorante, aperitivo, dolce, libero) e taglia, impatto sul budget, anteprima del diff sui giorni successivi, Accetta/Modifica/Non compensare; tono non colpevolizzante | Claude | M | flusso completo in meno di 4 tocchi | **fatto** — «Fuori programma» su ogni pasto non registrato della settimana: 7 tipi con taglie e kcal, «Altro» con intervalli, anteprima Optees (≈7 s) con stato, margine residuo e giorni toccati, Accetta il rientro / Lascia il piano com’è; pasto mostrato come intervallo con provenienza. 3 tocchi. Verificato su piano reale con scenari Salute sintetici. Riserva B12 chiusa dal backend; nuovi collegamenti B13/B11 da integrare nella UI |
| 6.4 | Catalogo preset degli sgarri con intervalli di kcal e macro e fonti citate | Gemini | S | `config/meal-presets.json` con fonti; rivisto da Claude | **fatto** — 53 fonti CREA; McDonald's verificati il 2026-10-05 (URL corretti da Claude); sushi da USDA FoodData Central; kebab senza fonte verificabile, resta indisponibile |

### Fase 7 — Rifinitura → **M3**

| # | Passo | Chi | Dim. | Fatto quando | Stato |
|---|---|---|---|---|---|
| 7.1 | PWA: manifest, icone, service worker per la shell offline, installazione su iPhone | Claude | M | icona sulla home, apertura a schermo intero | da fare |
| 7.2 | Processo Optees MCP riutilizzato, coda dei job con stato e annullamento | Codex | M | generazione settimanale non blocca il server; stato visibile | da fare |
| 7.3 | Accessibilità e QA mobile completa (contrasti, focus, lettori di schermo, dark mode) | Claude | M | checklist superata | da fare |
| 7.4 | README e documentazione aggiornati; screenshot delle schermate | Gemini | S | documenti coerenti con il codice | **fatto** — README riscritto da Gemini (seconda consegna) e corretto da Claude; screenshot di un profilo demo rifatti da Claude |

### Fase 8 — Obiettivi, attività e varietà → **M4**

Specifica: [phase8-spec.md](phase8-spec.md). Consegna a Gemini a sessioni: [gemini-handoff-phase8.md](gemini-handoff-phase8.md).

| # | Passo | Chi | Dim. | Fatto quando | Stato |
|---|---|---|---|---|---|
| 8.0 | Specifica della fase: principi, intervista, contratto API, attività, rientro con attività, piatti bloccati | Claude | M | [phase8-spec.md](phase8-spec.md) approvato da Paolo | **bozza** |
| 8.1 | Intervista e obiettivi: corpo, attività e tempo, priorità di allenamento, carichi di riferimento; nuove circonferenze nel diario; proposta di bilancio dall'obiettivo da approvare | Codex (backend) · Claude (UI) | L | contratto §1.6 con test; `PUT /api/profile` non cancella `goals`; intervista completabile da telefono saltando ogni domanda | **fatto** — backend `192ef84`; UI Profilo → «Obiettivi e intervista»: quattro blocchi saltabili, proposta di bilancio approvabile (verifica: −450 kcal approvate su DB temporaneo) |
| 8.2 | Matrice obiettivi → dosi (`config/training-goal-matrix.json`) con fonti verificate; soglie del §1.5, §3.2, §4 confermate o marcate euristiche | Claude | M | ogni grandezza con fonte e `checked_on`; punteggio a trapezio documentato | da fare |
| 8.3 | Attività oltre la palestra: catalogo (8.3a, Gemini, rivisto da Claude), energia personale o da MET netti, sessioni di attività nella settimana congiunta, conferma «fatta» nel diario | Codex · Gemini (8.3a) | L | settimana con `gym: no` solo attività; nessun doppio conteggio con la base Salute; test | **fatto backend** — attività nel MILP con durata intera, energia netta e provenienza, gym:no, conferma atomica, scostamento B13; contratto UI aggiornato |
| 8.4 | Palestra personalizzata: curva carico–ripetizioni personale aggiornata dai registri, durata massima e sedute doppie, efficienza dei protocolli e due protocolli per poco tempo | Codex | L | nessuna seduta oltre il limite; carichi arrotondati per difetto al disponibile; test | **fatto backend** — curve dai riferimenti/registri, griglia per difetto, limiti di durata e volume, doppie fasce con pausa effettiva, due protocolli brevi; euristiche esplicite in attesa di 8.2 |
| 8.5 | Obiettivi del giorno proposti dall'attività pianificata (base + attività + bilancio) | Codex · Claude (UI) | M | «Usa i valori proposti» in Piano; soglie rispettate; stima dichiarata senza Salute | **fatto backend** — proposta per data e tipo, base senza allenamenti + energia netta prudente + bilancio approvato, minimi e variazioni protetti, approva/rifiuta atomici con CSRF/409; UI da realizzare |
| 8.6 | Rientro con attività facoltativa: solo dieta (predefinito), dieta + passeggiata, dieta + attività gradita; limiti fissi; scenario prudente | Codex · Claude (UI) | M | mai attività senza richiesta; attività non fatta torna nel rientro senza doppia compensazione | **backend fatto**; UI da fare |
| 8.7 | Piatti scelti e ricette preferite: piatto bloccato in un pasto futuro, cuore sulle ricette, preferite premiate nel solver (max 2/settimana), ricette approvate come elementi del solver | Codex · Claude (UI) | L | «lasagne giovedì» compensata nella settimana; preferita non inseribile spiegata | **backend fatto**; UI da fare |
| 8.8 | Ingredienti delle ricette → CREA → prodotti: dizionario e proposte a sessioni (preferite per prime), approvazioni verificate | Gemini (proposte) · Claude (approvazione) | L | ricette con tutti gli ingredienti approvati in crescita a ogni sessione; nessun id inesistente | da fare |
| 8.9 | Alternative davvero diverse: sovrapposizione pesata sui grammi ≤ 10% per ingrediente canonico, condimenti esclusi per categoria; minimo 3 alternative; «Calcola altre alternative»; nelle diete strette massima diversità possibile dichiarata | Codex · Claude (UI) | L | test: coppie di alternative entro la soglia o sovrapposizione minimizzata e mostrata; vincoli nutrizionali mai rilassati | **fatto con limite documentato B16** — backend `6713e3e`, B16 `ee6ba5a`; UI: percentuale di ingredienti cambiati e «Calcola altre alternative». Con i due frutti del dominio demo, tre settimane al 10% sono impossibili (limite 10,8696%); serve ampliare i candidati liberi. Timeout non certificati. |
| 8.10 | Codice a barre: ricerca nel catalogo locale, registrazione dall'etichetta (per 100 g, 100 ml o per porzione → ricalcolo per 100 g), controllo di coerenza delle kcal, prodotti personali; lettura da fotocamera (HTTPS con `tailscale serve`) o da foto | Codex (API) · Claude (UI, libreria di decodifica locale) | M | scansione → diario in 3 tocchi; prodotto registrato ritrovato alla scansione successiva; GTIN validato | **fatto** — API `fe2216e`; UI «▥ Codice a barre» nella ricerca alimenti: cifre, foto o fotocamera dove il browser legge i codici, registrazione dall'etichetta con avviso di coerenza. Libreria di decodifica per Safari e HTTPS ancora da fare |
| 8.11 | Supermercati preferiti: prodotto da comprare accanto a ogni alimento generico, «uso sempre questo» porta il prodotto nel solver, lista della spesa settimanale con confezioni | Codex · Claude (UI) · Gemini (proposte di equivalenti) | L | lista della spesa dalla settimana applicata; prodotti nel solver solo se coerenti | **backend fatto**, PDF incluso; UI da fare |

## Fuori da questo piano

Riconoscimento dei pasti da foto, sincronizzazione live con Withings/HealthKit (app iOS ponte), WorkoutKit, prezzi automatici, ottimizzazione fine della progressione dei carichi, multiutente oltre i profili locali.

## Correzioni dopo la consegna T3/T5

| Passo | Stato | Verifica |
|---|---|---|
| B1–B5 | **fatto** — `9e45ae0` | 162 test verdi; end-to-end HTTP con Optees reale: settimana generata e applicata → alternative pranzo applicate, cena invariata; binarie bloccate con uguaglianze; warning unico; ricerca ordinata, incluso mela → mele CREA (regressione sui dati reali); provenienza del passato separata dal nome |

| W1–W3 | **fatto** — `652da35` | 176 test verdi; più sessioni per giorno, spiegazione dello snapshot e minuti visualizzati arrotondati, secondi del modello esatti |

| B6 | **fatto** — `72f9660` | 197 test unittest verdi; profilo nuovo mai salvato: stessi default in UI e owner, richiesta congiunta accettata per le abitudini personali abilitate |

| B7 | **fatto** — `882f5cf` | 198 test unittest verdi; explore preferisce schede diverse da varied sul fronte, fallback solo dieta spiegato |

| B9 | **fatto** — `7a4e12e` | 222 test verdi; Kalman diretto sulle mediane, trend settimanale con regressione, parametri progress-v2 |

| B10 | **fatto** — `919e014` | 222 test verdi; riepilogo del lunedì sull’ultima settimana conclusa, week_start esplicito nei tre riquadri |

Verifica finale T12 (2026-10-05): **237 test unittest verdi**, compresa anteprima HTTP con Optees reale e database identico prima/dopo. B9, B10, 6.2 e 6.1 hanno commit distinti; ulteriore regressione del ribilanciamento corretta per lo spuntino facoltativo. `web/static/` intatto. UI 6.3 da completare con [contratto ribilanciamento](backend-handoff-rebalance.md); [bandit v2](backend-handoff-bandit.md). Le modifiche concorrenti Gemini a preset e report restano fuori dai commit backend.

### Correzioni backend successive a T12

| Punto | Stato | Verifica |
|---|---|---|
| B12 | **fatto** — porzioni degli stessi prodotti prima delle sostituzioni; colazione/spuntini ultima leva; pizza esclusa; diff e applicazione solo dei pasti cambiati | 239 test verdi; [audit prima/dopo](rebalance-b12-audit.md), Optees reale incluso |
| B13 | **fatto** — diario settimanale aggregato, restituzione entro i massimi, soglia 100 kcal, decisioni monouso e limiti cumulativi | 248 test verdi; [contratto v2 e JSON](backend-handoff-rebalance.md); nessuna nuova registrazione sul percorso dal diario |
| B11 | **fatto** — DayView espone piano applicato, voto salvato e riferimenti dei componenti; piani sostituiti/estranei esclusi, casi multipli e futuri espliciti | 254 test verdi; [contratto §4.1](api-contract.md); lettura senza apprendimento |

Verifica finale correzioni B12 → B13 → B11: **254 test verdi** con il comando completo del piano, inclusa anteprima HTTP con Optees reale. Un commit per punto; contratto del rientro v2 e riferimenti DayView consegnati alla UI. `web/static/` non modificato. README, report Gemini e screenshot esterni al lavoro backend restano fuori dai commit.

### Correzioni dopo B11/B13 nella UI

| Punto | Stato | Verifica |
|---|---|---|
| B14 | **fatto** — verifiche Optees, decodifica e sicurezza restituiscono unavailable leggibile; diagnostica del limite; riferimenti correnti e griglia coerenti nei due modelli | 257 test verdi; due rientri applicati via HTTP con Optees reale su porzioni legacy già modificate; anteprime senza scritture |
| B15 | **fatto** — rientro come revisione atomica dello stesso piano: plan_id, voto e contesto conservati; storico originale e nutrienti attesi aggiornati | 263 test verdi; settimana applicata → rientro → giorno valutabile, doppia revisione, aderenza sul ribilanciato dopo prova/conferma, isolamento utenti e veri cambi di piano |

Verifica finale B14 → B15: **263 test verdi** con il comando completo richiesto. B14 e B15 chiusi con commit separati. Il rientro non accetta risultati Optees non verificabili e mantiene la traccia valutabile delle nuove revisioni del piano. Indagine del vecchio vettore non conservato e contratto aggiornati in [handoff rientro](backend-handoff-rebalance.md). Nessuna modifica a `web/static/`.

Verifica backend Fase 8, ordine 8.1 → 8.10 → 8.9: 267, 272 e **281 test verdi**, database temporanei e Optees reale nella suite completa. Commit distinti per i tre passi. Contratto UI con esempi in [api-contract.md](api-contract.md); sovrapposizione massima demo 100% → 59,46%, entrambe le settimane delle diete con tre alternative, vincoli nutrizionali intatti e limiti del calcolo dichiarati nell’[audit](phase8-diversity-audit.md). Nessuna modifica a `web/static/`; 8.3 non implementato in questo turno, anche dopo l’arrivo del catalogo revisionato.

| Punto | Stato | Verifica |
|---|---|---|
| B16 | **fatto — limite numerico documentato** | Con i candidati liberi correnti, tre alternative al 10% sono impossibili: limite inferiore 10,8696%. Timeout sempre non certificato, testo UI corretto; verifica su DB demo nuovo e regressioni nella suite completa. |
| B17 | **fatto** | GET /api/activities autenticato, catalogo locale revisionato e invariato, nessuna rete; regressione API su database temporaneo. |

Verifica finale T18 / B16–B17 (2026-10-06): **313 test verdi** con il comando
completo richiesto, su database temporanei. Chiusure separate: B16 287 test,
B17 288, 8.3 294, 8.4 302, 8.5 313. B16 documenta il limite analitico del dominio
demo (10,8696% minimo per tre alternative); non dichiara un ottimo dal timeout.
L'API aggiunge una ricerca non certificata anche se un percorso interrotto non
ha prodotto il certificato, così `no_more_alternatives` non prova impossibilità.
Optees reale ha inoltre verificato due attività da 20 minuti alle 08:00 e 14:00
nello stesso giorno. B17 `542bfd4`, 8.3 `30b0c4f`, 8.4 `fcf90f4`; contratto UI
con esempi e indisponibilità per 8.5 in [api-contract.md](api-contract.md).
`web/static/` non modificato. Parametri ancora non fissati da 8.2 dichiarati come
heuristici, senza spacciare proxy di volume o MET per efficacia individuale.

| Punto | Stato | Verifica |
|---|---|---|
| Ricette: sblocchi rapidi | **fatto** | Sale/pepe composto con whitelist stretta; approvazioni delle conversioni con fonte/autore e compatibilità; spezie estendibili in config. 834 ricette, pesi risolti 300→300, pronte 26→26; proposte esterne non approvate automaticamente. |

| Punto | Stato | Verifica |
|---|---|---|
| 8.11 + report settimanale PDF | **fatto** | Spesa aggregata, ingredienti verificati, consumati esclusi, prodotti preferiti/confezioni/reparti; PDF italiano A4 locale con sette giornate e spesa. Fixture sintetiche e controllo visivo del PDF. |

8.6: colonne MILP di durata intera, scenario basso, quota ≤50%, una attività/45 minuti, deficit e distribuzione protetti; applicazione atomica e credito ripristinato se saltata.

8.7: intenzioni per utente, intervalli robusti e snapshot delle ricette, porzioni intere/contorni, preferenza morbida e max due presenze. Preferite sospese in testa alla coda locale del matcher. API/JSON per la UI in api-contract.md; stime senza ingredienti non certificano gli abbinamenti personali.

Consegna T20: ricette 316 test (`437e652`), spesa/PDF 319 (`287c75d`),
rientro con attività 322 (`c48c54a`); 8.7 verificato con 329 test, snapshot
stabili, stime conservate nel diario e priorità effettiva nel matcher.
Verifiche ulteriori: report con esercizi/carichi e attività; scenari energetici
aggiornati dopo il rientro e sessioni già pianificate considerate prima del
rientro anticipato. Cronologia dei test del bandit fissata su date sintetiche.
`web/static/` non modificato; proposte/dizionario esterni al lavoro restano fuori.

| Bug UI fase 8 (2026-10-06) | Stato | Verifica |
|---|---|---|
| 1 — Ricette preferite nella settimana congiunta | **fatto** | Riprodotto 400 con R048/R054; snapshot presenti, profilo ricaricato prima del commit SQL. Un solo profilo nella transazione, applicazione/rilettura ed esposizioni bandit verificate. Suite completa: 333 test verdi. |
| 2 — Conferma di attività future | **fatto** | 409 future_activity prima di qualsiasi scrittura; stato chosen e nessun workout_log, conferma odierna ancora idempotente. Suite completa: 333 test verdi. |
| 3 — Titoli dei preset | **fatto** | Nome italiano e taglia dal catalogo in elenco, solver e diario; vecchi titoli normalizzati senza cambiare gli snapshot. Regressione Pizzeria · medio su lista e piano applicato. Suite completa: 333 test verdi. |
