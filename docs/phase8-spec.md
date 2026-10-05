# Fase 8 — Obiettivi, attività e varietà

Specifica del 2026-10-05. Nasce dalla richiesta di Paolo: un'intervista iniziale, carichi personali, obiettivi di allenamento con punteggi per il solver, sedute di durata limitata, attività anche fuori dalla palestra, calorie che seguono l'attività, rientro dagli sgarri anche con il movimento, dieta più varia e ricette collegate ai prodotti reali.

Oggi il sistema ottimizza bene, ma rispetto a obiettivi che nessuno gli ha dato: il bilancio calorico si sceglie a mano, gli obiettivi riposo/allenamento si scrivono a mano, la palestra è l'unica attività pianificabile e le ricette non entrano nel solver.

## 0. Principi

1. **Tutto è una proposta.** Bilancio calorico, obiettivi del giorno, carichi e attività aggiuntive si propongono; li applica solo l'utente. Restano i limiti di sicurezza già in uso: soglie minime, variazione massima, intervallo minimo fra due ricalibrazioni.
2. **Ogni domanda dell'intervista si può saltare.** Un dato mancante resta mancante, non diventa zero né un valore inventato: il sistema lavora con meno vincoli e dice cosa manca.
3. **La palestra non è obbligatoria.** Camminare, andare in bici, nuotare o ballare sono attività di pieno diritto, per chi non ama la palestra e per chi la fa già.
4. **L'attività non è una punizione.** Una passeggiata per compensare uno sgarro si propone solo se l'utente la chiede, entro limiti fissi, e la dieta resta la leva principale.
5. **Ogni parametro di scienza dello sport ha una fonte** in `config/` con URL, data di verifica e ambito, come fanno già `workout-protocols.json` e `meal-presets.json`. Quando non esiste un valore scientifico, il parametro è marcato come euristica configurabile.

## 1. Intervista iniziale (8.1)

Procedura a passi, proposta al primo accesso e riapribile da Profilo → «Obiettivi e intervista». Quattro blocchi indipendenti, ognuno con il proprio salvataggio.

### 1.1 Corpo

| Campo | Tipo | Note |
|---|---|---|
| `target_weight_kg` | numero, facoltativo | 30–300 |
| `target_body_fat_pct` | numero, facoltativo | 3–60; se c'è, il peso obiettivo può essere ricavato dalla massa magra attuale (si mostra, non si impone) |
| `target_date` | data, facoltativa | almeno 4 settimane da oggi |
| `pace` | `gentle` \| `moderate` \| `custom` | ritmo desiderato, vedi §1.5 |
| `pace_pct_per_week` | numero, solo per `custom` | entro i limiti del §1.5 |
| `circumferences` | elenco di misure da seguire | `waist` esiste già; aggiungere `hip`, `chest`, `arm`, `thigh` alle misure del diario (cm, 10–300) |

Peso, massa grassa e circonferenze attuali **non** si salvano nel profilo: sono misure del diario (`POST /api/measurements`) con la loro data, così l'andamento si calcola come per il peso. La massa grassa della bilancia a bioimpedenza è rumorosa: per il confronto con l'obiettivo si usa il suo andamento filtrato, mai il valore del singolo giorno.

### 1.2 Attività e tempo

| Campo | Tipo | Note |
|---|---|---|
| `gym` | `yes` \| `no` \| `maybe` | con `no` la settimana congiunta non propone sessioni di palestra |
| `liked_activities` | elenco di id dal catalogo attività (§3) | per esempio camminata, bici, nuoto |
| `disliked_activities` | elenco di id | mai proposte |
| `max_session_minutes` | intero, 20–240, predefinito 90 | euristica dell'utente, non limite fisiologico (§4.2) |
| `max_sessions_per_day` | 1 \| 2, predefinito 1 | con 2 una seduta lunga si può dividere (§4.2) |
| `min_gap_hours` | intero, predefinito 4 | distanza minima fra due sedute dello stesso giorno |

Le disponibilità per giorno (minuti, giorni esclusi) restano quelle già inserite in Piano/Allenamento: l'intervista ne propone solo i valori iniziali.

### 1.3 Obiettivi di allenamento

L'utente distribuisce priorità da 0 a 3 sugli obiettivi del §2 (0 = non mi interessa). Al massimo tre obiettivi con priorità 3, per non chiedere al solver cose incompatibili senza dirlo. Gli obiettivi incompatibili nella stessa settimana (per esempio massima forza e massima resistenza) vengono segnalati ma non vietati.

### 1.4 Carichi di riferimento (solo con `gym` ≠ `no`)

Per gli esercizi multiarticolari dei protocolli scelti si chiedono due serie recenti:

- una **pesante**: kg e ripetizioni pulite fra 2 e 6 (per esempio 3 ripetizioni);
- una **leggera**: kg e ripetizioni pulite fra 10 e 15 (per esempio 12 ripetizioni).

Il massimale su una ripetizione **non** si chiede: è inutile per il modello e sconsigliato senza esperienza e senza assistenza. Una sola delle due serie basta per partire (formula generale); con due si ricava la curva personale (§4.1). Le serie registrate durante gli allenamenti aggiornano la stima: l'intervista serve solo a partire.

Si integra con `starting_loads_kg` di `workout_configuration.py`: un carico di partenza inserito a mano resta valido e prevale finché non ci sono serie registrate.

### 1.5 Bilancio calorico proposto dall'obiettivo

Dal peso attuale (andamento filtrato, non il singolo valore), dall'obiettivo e dal ritmo:

- **Ritmo in perdita:** `gentle` = 0,25% del peso a settimana, `moderate` = 0,5%, `custom` fino a 1%.
- **Ritmo in aumento:** `gentle` = 0,1%, `moderate` = 0,25%, `custom` fino a 0,5%.
- **Bilancio giornaliero proposto** ≈ variazione settimanale in kg × 7700 / 7, arrotondato a 50 kcal e limitato a ±1000. La regola dei 7700 kcal/kg è un'approssimazione che sovrastima la perdita nel lungo periodo: la ricalibrazione del lunedì, che misura il peso reale, resta il correttore.
- Con una `target_date` si calcola il ritmo necessario. Se supera il massimo, si propone il ritmo massimo e una data più realistica, senza forzare.
- Il risultato è una **proposta** di `energy_balance_target_kcal`, da approvare come la ricalibrazione, con motivazione e incertezza.

Tutte le soglie del §1.5 sono marcate come da verificare in 8.2, con fonti.

### 1.6 Contratto API (da implementare in 8.1)

```
GET  /api/goals                        → { body, activity, training_priorities, strength_anchors, missing[] }
PUT  /api/goals/body                   ← §1.1 (sostituisce il blocco)
PUT  /api/goals/activity               ← §1.2
PUT  /api/goals/training               ← { priorities: { <goal_id>: 0..3 } }
PUT  /api/goals/strength-anchors       ← { anchors: [{ exercise_key, heavy: {kg, reps, date}?, light: {kg, reps, date}? }] }
POST /api/goals/energy-proposal        → { status: available|insufficient_data, proposal?: { id, state_token,
                                            current_kcal, proposed_kcal, pace_pct_per_week, expected_date,
                                            reasoning[], uncertainty[], limits_applied[] }, reason? }
POST /api/goals/energy-proposal/{id}/approve|reject   ← { state_token }
```

- Gli obiettivi stanno in un campo `goals` del profilo, ma `PUT /api/profile` **non** deve cancellarli quando non li riceve: è lo stesso problema già visto per i campi del profilo, da non ripetere.
- `missing[]` elenca le domande senza risposta che limitano qualcosa, con il testo da mostrare: per esempio «Senza peso obiettivo il bilancio resta quello scelto da te».
- L'approvazione della proposta di bilancio segue le regole della ricalibrazione: `state_token` sullo stato corrente, risposta 409 se il profilo è cambiato, scrittura atomica.

## 2. Matrice obiettivi → dosi (8.2)

`config/training-goal-matrix.json`, scritta da Claude con fonti verificate. Per ogni obiettivo:

```json
{
  "id": "hypertrophy",
  "name_it": "Ipertrofia",
  "dose": {
    "reps":            { "ideal": [6, 15],   "acceptable": [5, 30] },
    "rir":             { "ideal": [0, 3],    "acceptable": [0, 4] },
    "weekly_hard_sets_per_muscle": { "ideal": [10, 20], "acceptable": [4, 30] },
    "rest_seconds":    { "ideal": [90, 180], "acceptable": [60, 300] },
    "cardio_minutes_by_zone": null
  },
  "evidence": "moderate",
  "sources": [{ "id": "...", "url": "...", "checked_on": "...", "supports": "weekly_hard_sets_per_muscle" }],
  "notes_it": "..."
}
```

**Punteggio.** Per ogni grandezza si usa una funzione a trapezio: vale 1 dentro `ideal`, scende linearmente a 0 al bordo di `acceptable`, vale 0 fuori. Una funzione concava e lineare a tratti si rappresenta in un MILP con una variabile ausiliaria e due vincoli, senza variabili binarie. Il punteggio di una settimana per un obiettivo è la media delle sue grandezze. Il punteggio complessivo è la somma pesata con le priorità del §1.3, e diventa il `training_fit` già usato dalla settimana congiunta.

**Obiettivi** (i valori si fissano in 8.2 con le fonti):

| id | Obiettivo | Leve principali |
|---|---|---|
| `strength` | Forza | carichi alti (circa 80–100% del massimale stimato), 1–6 ripetizioni, recuperi lunghi |
| `hypertrophy` | Ipertrofia | serie settimanali per muscolo vicino al cedimento; ripetizioni in un intervallo ampio |
| `muscular_endurance` | Resistenza muscolare | 15 o più ripetizioni, recuperi brevi, circuiti |
| `power` | Potenza | carichi leggeri o moderati spostati veloci, pliometria, ripetizioni lontane dal cedimento |
| `cardio_fitness` | Fiato e resistenza | minuti settimanali per zona di intensità, intervalli |
| `fat_loss` | Perdere grasso | deficit dalla dieta; pesi per conservare la massa magra; minuti di attività |
| `health` | Salute e mantenimento | minimi raccomandati: minuti settimanali di attività moderata e giorni di rinforzo muscolare |
| `mobility` | Flessibilità e mobilità | minuti di stretching, yoga o pilates a settimana |
| `agility` | Agilità | cambi di direzione e pliometria |

- **Aumentare il metabolismo** non è un obiettivo a sé: l'effetto reale è piccolo e prometterebbe più di quanto mantiene. Rientra in `fat_loss` e `hypertrophy`.
- **Postura** non è un obiettivo a sé: le prove sono deboli. Esercizi per core e muscoli posturali compaiono come contenuto di `health` e `mobility`, descritti come utili per funzione e dolore.

**Fatto quando:** ogni grandezza ha almeno una fonte primaria o una presa di posizione verificata (ACSM, OMS, NSCA, meta-analisi), con `checked_on`; ciò che resta euristico è marcato `"evidence": "heuristic"`.

## 3. Attività oltre la palestra (8.3)

### 3.1 Catalogo

`config/activity-catalog.json`: camminata (lenta, normale, veloce, in salita), bici (tranquilla, moderata), corsa leggera, nuoto, ballo, escursione, yoga, pilates, stretching, giardinaggio. Ogni voce contiene:

- `id`, `name_it`, `met` e il codice del **Compendium of Physical Activities**, edizione 2024, con URL e data di verifica;
- `healthkit_types`: i tipi di allenamento Apple Salute corrispondenti, per la stima personale e per evitare il doppio conteggio;
- `goals`: gli obiettivi del §2 a cui contribuisce, con la zona di intensità;
- `duration_minutes`: valori ammessi, per esempio da 10 a 90 a passi di 5.

### 3.2 Energia di un'attività pianificata

1. **Stima personale** se Apple Salute ha almeno N allenamenti di quel tipo: quantili di kcal attive al minuto, come per la palestra (`workout_energy_models` di `joint_energy.py`).
2. **Altrimenti stima dal catalogo:** kcal **nette** = (MET − 1) × peso in kg × ore. Si sottrae il riposo, già compreso nel dispendio di base. È marcata come stima, con un intervallo di ±30% come scenari basso e alto, da confermare in 8.2.
3. **Doppio conteggio:** la base Salute «senza allenamenti» contiene già il movimento abituale, passi inclusi. Un'attività pianificata conta solo se è in più rispetto a quel movimento. Per questo si pianifica come allenamento registrato (con inizio e fine), non come «passi in più».

### 3.3 Nella settimana congiunta

Le attività diventano sessioni pianificabili accanto a quelle della palestra, con durata scelta dal solver fra i valori ammessi: è una variabile intera, quindi resta nel MILP. Con `gym: no` si pianificano solo attività. Il punteggio `health` premia il raggiungimento dei minimi settimanali; senza priorità, l'attività non è imposta.

Nel diario un'attività pianificata si conferma «fatta» con un tocco, come un pasto. Se non viene fatta, la differenza di energia entra nel rientro della settimana (B13) come ogni altra deviazione.

## 4. Palestra personalizzata (8.4)

### 4.1 Curva carico–ripetizioni personale

Per ogni esercizio, la relazione fra carico e ripetizioni massime si modella così:

```
carico(r) = M / (1 + r / k)
```

- Con una sola serie si usa `k = 30` (formula di Epley) e si ricava `M`.
- Con due serie, `M` e `k` si ricavano risolvendo due equazioni lineari. `k` deve restare in un intervallo plausibile, da fissare in 8.2; altrimenti si torna a 30 e lo si segnala.
- Il carico prescritto per `reps` ripetizioni a `RIR` dalla fine è `carico(reps + RIR)`, arrotondato al carico disponibile più vicino **per difetto** (`available_loads_kg`).
- **Aggiornamento dai registri:** ogni serie con kg, ripetizioni e RPE dà un punto, con `RIR = 10 − RPE` limitato a 0–4. La stima di `M` si aggiorna con una media mobile robusta delle ultime serie, e il carico prescritto non sale più del 5% a settimana. Il 5% è un'euristica da confermare in 8.2.

### 4.2 Durata massima e sedute doppie

- Nessuna sessione supera `max_session_minutes`. È un vincolo dell'utente, non un limite fisiologico: la soglia dei 60–90 minuti legata al cortisolo non è dimostrata.
- È invece fondato limitare le **serie impegnative per muscolo in una stessa seduta**, perché oltre un certo numero il beneficio cala. Il valore va in 8.2; come euristica iniziale, circa 10.
- Se il volume settimanale richiesto non entra, il solver può:
  - dividere su due sedute nello stesso giorno, se `max_sessions_per_day` = 2 e c'è `min_gap_hours`;
  - spostare su un altro giorno disponibile;
  - ridurre il volume, dicendolo.

### 4.3 Poco tempo

Ogni protocollo riceve un attributo calcolato di **efficienza**: serie impegnative per minuto e muscoli coinvolti per minuto. Con poco tempo disponibile (soglia da definire, per esempio meno di 40 minuti a seduta), il solver preferisce multiarticolari, superserie di muscoli antagonisti e circuiti; per il cardio, gli intervalli. Al catalogo servono almeno due protocolli nuovi: «Superserie a corpo intero» e «Circuito multiarticolare a tempo».

## 5. Calorie del giorno dall'attività (8.5)

Oggi gli obiettivi dei giorni di riposo e di allenamento si scrivono a mano. In 8.5 il sistema li **propone**:

```
kcal del giorno = base senza allenamenti (scenario centrale Salute)
                + energia netta delle attività e sessioni pianificate (scenario basso: prudente)
                + bilancio approvato (§1.5)
```

- **Proteine:** per kg di peso, costanti fra i giorni.
- **Grassi:** sopra la soglia minima.
- **Carboidrati:** assorbono la differenza, quindi crescono nei giorni attivi.
- **Senza Salute:** si usa il catalogo e si dichiara la stima.

La proposta compare nel blocco «Obiettivi riposo/allenamento» della pagina Piano con «Usa i valori proposti». Restano le soglie minime e la variazione massima.

## 6. Rientro con l'attività (8.6)

Estende `POST /api/rebalance/preview` con un campo facoltativo:

```json
"activity": { "mode": "none" | "walk" | "liked", "max_minutes_per_day": 45 }
```

- **`none`** (predefinito): come oggi, solo dieta.
- **`walk`:** la dieta più passeggiate. La UI la offre come pulsante «Aggiungi una passeggiata», mai preselezionato.
- **`liked`:** la dieta più una delle attività gradite (§1.2); mai una sessione di palestra intera aggiunta in automatico.

**Limiti.** Sono euristiche configurabili, mostrate all'utente:

- l'attività copre al massimo il **50%** della correzione; il resto, o tutto, viene dalla dieta;
- al massimo **45 minuti** in più al giorno e **una** attività in più al giorno;
- niente attività in più nei giorni con una sessione intensa già pianificata.

**Energia.** Si conta lo scenario **basso** (§3.2), perché è meglio sottostimare. Le attività aggiunte compaiono nel giorno come voci da confermare. Se non vengono fatte, la differenza torna nel rientro della settimana, senza colpe e senza doppie compensazioni (B13).

**Risposta.** Ai giorni dell'anteprima si aggiunge `activities: [{ activity_id, minutes, energy_kcal: {low, central, high}, source }]`. Nel budget compaiono `correction_diet_kcal` e `correction_activity_kcal`. Il testo di `workout.explanation` cambia di conseguenza.

## 7. Varietà della dieta e piatti scelti (8.7)

1. **Piatto bloccato.** «Giovedì a cena voglio le lasagne»: l'utente fissa un piatto in un pasto futuro della settimana prima di generarla. Il piatto può essere:
   - una ricetta del solver, in porzioni;
   - un preset degli sgarri, con il suo intervallo di kcal;
   - una stima libera.

   Il solver costruisce il resto della settimana intorno al piatto. È il rientro fatto in anticipo, quindi riusa la stessa logica e gli stessi limiti.
2. **Ricette nel solver.** Una ricetta approvata diventa un elemento con il suo vettore nutrizionale per porzione (variabile intera di porzioni), completabile con contorni e alimenti singoli fino al bersaglio. Entrano solo le ricette con **tutti** gli ingredienti approvati (§8).
3. **Varietà nella settimana.** Si aggiunge un termine che penalizza la ripetizione dello stesso alimento o piatto principale oltre una soglia, oltre alla diversità fra alternative che esiste già. Prima va misurato quanto si somigliano oggi le settimane: Codex lo verifica su una settimana demo e sulle diete personali, senza pubblicare dati personali.

## 8. Ricette → alimenti CREA → prodotti del supermercato (8.8)

**Stato.**
- Le ricette sono 834, con 7.843 occorrenze di ingredienti raggruppate in 1.019 gruppi.
- Il dizionario conta 101 ingredienti canonici.
- 24 ricette sono approvate e ne restano 18 sospese.

**Strumento.** C'è già: `scripts/match_recipe_ingredients.py`, con dizionario, coda di revisione e approvazioni esplicite. Manca il lavoro lungo e ripetitivo: estendere il dizionario e proporre le associazioni, gruppo per gruppo. È il compito di Gemini, a sessioni, secondo [gemini-handoff-phase8.md](gemini-handoff-phase8.md).

**Ordine di lavoro.**
1. Gli ingredienti più frequenti, che sbloccano più ricette.
2. Le ricette italiane.
3. Il resto.

**Chi fa cosa.** Gemini **propone**; Claude **approva** con `--approve` dopo la verifica, ingrediente per ingrediente e stato per stato (crudo/cotto, secco/cotto, fresco/in scatola). Per i prodotti del supermercato, l'associazione a un record Open Food Facts locale è facoltativa e serve per «quale prodotto compro», non per i valori nutrizionali, che restano CREA quando esiste la voce corretta.

## 9. Cosa resta fuori

- Programmazione periodizzata su mesi (blocchi, scarichi).
- Stima del massimale da video.
- Ricerca generale in tutto Open Food Facts in tempo reale.
- Prezzi.
