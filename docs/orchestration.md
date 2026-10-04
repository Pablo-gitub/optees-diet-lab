# Orchestrazione dei piani — specifica v1

Stato: **specifica approvata per l'implementazione** (passo 1.2 di [development-plan.md](development-plan.md)).
Sostituisce la scelta manuale del metodo descritta in [multiobjective-planner.md](multiobjective-planner.md).

## 1. Principi

1. **Un solo comando.** L'utente preme «Genera»; non sceglie Bilanciato, Pareto, Min-Max o Bandit. I metodi sono **stadi di una catena**, non modalità alternative.
2. **Vincoli rigidi intoccabili.** Limiti nutrizionali, porzioni, regole della dieta, esclusioni, attrezzatura e tempo non vengono mai allentati in silenzio. Solo la **diversità** (§4) può essere ridotta, e la riduzione viene dichiarata.
3. **Poche alternative davvero diverse.** Si restituiscono 2–5 piani con un **ruolo** e una **motivazione**. Mai riempire il risultato con cloni che differiscono per un solo alimento.
4. **Optees calcola, il client verifica.** Ogni piano passa la verifica indipendente già esistente (`constraint_report`).
5. **Spiegazioni deterministiche.** `explanation` e `diff` sono generati da regole e numeri del calcolo, non da un modello linguistico.
6. **Riproducibilità.** Ogni esecuzione salva input, versioni, parametri e seed.

Ambito v1: **una giornata, solo dieta** (stessi dati del pianificatore attuale). La v2 estende l'orizzonte a 7 giorni e aggiunge la palestra con lo stesso formato di uscita (§8).

## 2. Ingresso — `PlanRequest`

```json
{
  "horizon": {"day_index": 0, "days": 1},
  "mode": "sedentary",
  "locked": [],
  "k": 4,
  "pool_size": 12,
  "epsilon": 0.05,
  "diversity": {"min_distance": 3, "structural": true},
  "seed": 20261004
}
```

- `locked`: pasti o alimenti già decisi o consumati (`{"meal": "breakfast", "selections": [...]}`); entrano come variabili fissate. In v1 è vuoto; serve al diario e al ribilanciamento.
- Target, esclusioni, preferenze e politica colazione/spuntini arrivano dal profilo come oggi. Gli scenari di consumo arrivano da `health_inputs.algorithm_inputs()` quando disponibili.
- Il vecchio parametro `strategy` di `/api/generate` è accettato per compatibilità, **ignorato** e registrato nei warning.

## 3. La catena

```text
S0 controllo ingresso
 → S1 ottimo di riferimento
 → S2 pool di candidati diversi (Optees MILP, più obiettivi, vincolo di diversità)
 → S3 valutazione multi-obiettivo + filtro Pareto
 → S4 robustezza sugli scenari di consumo (Min-Max / regret)
 → S5 assegnazione dei ruoli
 → S6 slot di esplorazione (bandit)
 → S7 spiegazioni, diff, salvataggio
```

### S0 — Controllo dell'ingresso

- **Coerenza energetica dei target.** Calcolare `E_macro = 4·P + 4·C + 9·G` sui bersagli. Se `|E_macro − kcal_target| / kcal_target > 0.10` aggiungere il warning `targets_inconsistent` con i due valori. Non blocca il calcolo, ma la UI lo mostra nel profilo e nel risultato. Gli attuali target demo (80/180/60 g → 1.580 kcal contro 1.800) falliscono questo controllo e vanno corretti (passo 0.2).
- Validazione già esistente di `formulate()`; nessun rilassamento.

### S1 — Ottimo di riferimento

Risolvere l'obiettivo **bilanciato** attuale (preferenze in priorità lessicografica, poi somma degli scarti relativi) → valore `z*` e soluzione `A0`. Se è impossibile: restituire `status: "infeasible"` con i vincoli coinvolti, come oggi, e fermarsi.

### S2 — Pool di candidati diversi

Generare fino a `pool_size` soluzioni ammissibili nella **regione quasi-ottima**:

```text
scarto_bilanciato(x) ≤ z* · (1 + epsilon) + 0.01
```

(il termine assoluto 0.01 evita una regione vuota quando `z* ≈ 0`).

Ogni nuovo candidato deve rispettare il **vincolo di diversità** (§4) rispetto a **tutti** i candidati già nel pool. Gli obiettivi dei solve successivi ruotano, così il pool esplora direzioni diverse invece di ripetere lo stesso criterio:

| Giro | Obiettivo del solve (sempre dentro la regione quasi-ottima) |
|---|---|
| 1 | bilanciato (= `A0`) |
| 2 | Min-Max dello scarto relativo |
| 3 | Max-Min della soddisfazione |
| 4 | massima preferenza / gradimento storico |
| 5 | massima varietà (penalità sugli alimenti già usati negli ultimi 7 giorni o già nel pool) |
| 6+ | somme pesate con priorità 4× su un nutriente, a rotazione |

Il pool si ferma quando raggiunge `pool_size`, quando un giro è impossibile per tutti gli obiettivi, oppure dopo un tempo massimo (default 20 s). Le funzioni di `multiobjective_day.py` restano utili come obiettivi dei singoli giri.

### S3 — Valutazione e filtro Pareto

Per ogni candidato calcolare il vettore degli obiettivi (frecce: ↓ minimizzare, ↑ massimizzare):

| Chiave | Significato | v1 |
|---|---|---|
| `nutrition_error` ↓ | somma degli scarti relativi dai bersagli | sì |
| `worst_error` ↓ | scarto relativo peggiore | sì |
| `preference` ↑ | quota di alimenti preferiti/gradimento storico | sì |
| `variety` ↑ | alimenti nuovi rispetto agli ultimi 7 giorni scelti | sì |
| `prep_minutes` ↓ | tempo di preparazione stimato | solo se noto per tutti |
| `training_fit` ↑ | copertura e tempo della palestra | v2 |

Gli obiettivi non disponibili per tutti i candidati sono esclusi dal confronto, non trattati come zero. Si eliminano i duplicati e le soluzioni dominate (`nondominated()` generalizzato a un vettore qualsiasi). Il risultato è il **fronte**: un campione non dominato, non la frontiera completa.

### S4 — Robustezza

Disponibile solo se `usable_consumption_baseline` è vero (scenari basso/centrale/alto di Salute). Per ogni candidato `c` e scenario `s`:

```text
loss(c, s)   = |(kcal_c − consumo_s) − bilancio_obiettivo|
regret(c, s) = loss(c, s) − min_c' loss(c', s)
```

`bilancio_obiettivo` è il deficit o surplus scelto dall'utente; se non è configurato, la robustezza resta `unavailable`. Si calcolano `max_loss` (Min-Max) e `max_regret`. In v1 è una **graduatoria dei candidati già fattibili**, non un'ottimizzazione robusta globale. Se Salute non è disponibile: `robustness: {"status": "unavailable", "reason": "..."}`, senza valori inventati.

### S5 — Ruoli

Selezione deterministica, in quest'ordine, sul fronte di S3:

| Ruolo | Regola | Condizione |
|---|---|---|
| `best` | `nutrition_error` minimo; a parità, `preference` maggiore | sempre |
| `varied` | `variety` massima fra i candidati a distanza ≥ `min_distance` da `best` | se esiste |
| `robust` | `max_regret` minimo, diverso dai piani già scelti | se S4 è disponibile |
| `preferred` | `preference` massima, diverso dai piani già scelti | se esiste storico di gradimento |
| `explore` | scelto da S6 | se il fronte ha candidati non ancora assegnati |

Un piano ha **un solo ruolo**. Se il migliore candidato per un ruolo è già stato scelto, si prende il successivo; se non ce n'è, il ruolo viene **omesso** (mai duplicato). Risultato: da 1 a `k` piani (default 4). Con un solo piano, `warnings` spiega perché (es. «una sola combinazione rispetta i vincoli del giorno»).

### S6 — Esplorazione (bandit)

- **I bracci sono caratteristiche del piano**, non metodi di ottimizzazione: famiglia proteica principale (legumi, pesce, carne bianca, carne rossa, uova, formaggi), amido principale (pasta, riso, pane, patate, nessuno), struttura (piatto unico / più componenti). Ogni candidato ha un insieme di bracci.
- **Contesto**: programma (`mode`), tipo di giornata (allenamento/riposo, da v2) e versione dei target. Un contesto nuovo riparte da zero.
- **Ricompensa**: solo piani dichiarati **provati**: `(voto − 1) / 4`; da v2 combinata con l'aderenza registrata nel diario. Generazione e scelta non sono ricompense. Peso e composizione corporea **non** sono ricompense giornaliere.
- **Politica**: UCB1 sui bracci; il punteggio di un candidato è la media dei punteggi UCB dei suoi bracci. Si sceglie fra i candidati del fronte non assegnati a un ruolo. Senza dati si sceglie il braccio meno provato.
- `choose_arm()` attuale (bracci = metodi) viene dismessa; le osservazioni esistenti restano nello storico ma non alimentano il nuovo bandit.

### S7 — Spiegazioni, diff e salvataggio

Vedi §5–§6. Si salva un `PlanSet` per esecuzione; i piani restano singolarmente selezionabili e valutabili come oggi.

## 4. Vincolo di diversità

Sia `S_j` l'insieme degli indici delle variabili binarie `y` (scelta di un alimento) uguali a 1 nel candidato `j`. Per ogni candidato precedente:

```text
Σ_{i ∈ S_j} y_i ≤ |S_j| − d          (d = min_distance, default 3)
```

Il nuovo piano deve quindi **lasciare almeno `d` alimenti** del piano `j`. Sostituisce l'attuale taglio `≤ |S_j| − 1`, che produce piani diversi per una sola verdura.

**Diversità strutturale** (`structural: true`). Se il piano `j` contiene, in pranzo o cena, l'alimento proteico principale `p_j` e l'amido principale `a_j`, il nuovo piano deve cambiarne almeno uno:

```text
y[p_j] + y[a_j] ≤ 1        (per ogni pasto in cui entrambi sono presenti in j)
```

Alimenti fissati da `locked` e prodotti di abitudine (colazione e spuntini personalizzati) sono **esclusi** dal conteggio: non possono variare e renderebbero il vincolo impossibile.

**Rilassamento dichiarato.** Se un giro è impossibile, si prova con `d − 1` fino a `d = 1`, poi senza la diversità strutturale. Ogni riduzione è registrata in `pool.diversity_relaxed` e mostrata all'utente («le alternative possibili oggi sono poche: cambiano al massimo 2 alimenti»). I vincoli nutrizionali non si rilassano mai.

## 5. Formato di uscita — `PlanSet`

```json
{
  "run_id": "2026-10-04T18:02:11Z-7f3a",
  "spec_version": "orchestration-v1",
  "versions": {"engine": "…", "catalog": "…", "rules": "…", "health_report": "…"},
  "request_hash": "sha256:…",
  "horizon": {"day_index": 0, "days": 1},
  "mode": "sedentary",
  "status": "ok",
  "warnings": [{"code": "targets_inconsistent", "message": "Le proteine, i carboidrati e i grassi bersaglio valgono 1.580 kcal, il bersaglio energetico è 1.800 kcal."}],
  "pool": {"candidates": 9, "front": 6, "epsilon": 0.05, "min_distance": 3, "diversity_relaxed": []},
  "plans": [ { "…": "Plan, vedi sotto" } ]
}
```

`status`: `ok` | `infeasible` | `partial` (es. timeout del pool con almeno un piano).

### `Plan`

Mantiene **tutti i campi attuali** (`selections`, `nutrients`, `nutrients_by_meal`, `slots`, `constraint_report`, `demo`, `scope`, `mode`, `day_index`) e aggiunge:

```json
{
  "role": "varied",
  "rank": 2,
  "explanation": {
    "headline": "Più vario: pesce al posto dei legumi a cena",
    "reasons": [
      "Cambia la fonte proteica di cena e l'amido di pranzo",
      "Resta entro il 3% dall'ottimo nutrizionale"
    ],
    "tradeoffs": ["Proteine 6 g sotto il bersaglio"]
  },
  "diff": {
    "reference_plan": "best",
    "distance": 4,
    "added":   [{"meal": "dinner", "food": "Merluzzo", "grams": 200}],
    "removed": [{"meal": "dinner", "food": "Lenticchie, secche, cotte, bollite", "grams": 179}],
    "changed": [{"meal": "lunch", "food": "Pane bianco", "from_g": 40, "to_g": 60}],
    "nutrients": {"kcal": -12, "protein_g": -6, "carbs_available_g": 4, "fat_g": 1}
  },
  "objectives": {"nutrition_error": 0.081, "worst_error": 0.079, "preference": 0.5, "variety": 0.67, "prep_minutes": null},
  "robustness": {"status": "available", "max_loss_kcal": 210, "max_regret_kcal": 35, "scenarios": {"low": 180, "central": 40, "high": 210}},
  "arms": ["protein:fish", "starch:bread"],
  "optimization": {"stage": "S2", "objective": "variety", "near_optimal_gap": 0.028}
}
```

Ruoli (`role`): `best` | `varied` | `robust` | `preferred` | `explore`.

## 6. Regole per `explanation` e `diff`

**`headline`** (≤ 80 caratteri, italiano), da modello per ruolo:

| Ruolo | Modello |
|---|---|
| `best` | «Il più vicino ai tuoi obiettivi» |
| `varied` | «Più vario: {cambio principale}» |
| `robust` | «Più sicuro se consumi meno/più del previsto» |
| `preferred` | «Con gli alimenti che apprezzi di più» |
| `explore` | «Da provare: {braccio poco esplorato}» |

- `reasons`: al massimo 3, solo fatti calcolati (distanza dall'ottimo in %, cambi di fonte proteica o amido, scenario coperto).
- `tradeoffs`: al massimo 2. Includere ogni nutriente con scarto peggiore di **5 punti percentuali** rispetto a `best`.

**`diff`**: sempre rispetto al piano `best` (per `best` stesso: `null`).

- `added` e `removed` per coppia (pasto, alimento); `changed` solo se `|Δ| ≥ 10 g` **oppure** `≥ 15%`.
- `nutrients`: differenza dei totali, arrotondata all'intero.
- `distance`: numero di alimenti di `best` che il piano non contiene, contati come nel §4, cioè senza quelli fissi.
- Proprietà verificata dai test: applicando `diff` al piano `best` si ottiene l'insieme di (pasto, alimento) del piano.

## 7. Interfaccia (contratto per il passo 1.3)

- La pagina Pianificazione **non ha più il menu Metodo**; rimangono Programma, Giornata e «Genera».
- Ogni card mostra il badge del ruolo e la `headline`. I chip del `diff` («+ Merluzzo», «− Lenticchie», «Pane 40→60 g») compaiono sopra il dettaglio dei pasti; `tradeoffs` è in tono neutro, non come errore.
- `warnings` compaiono in alto nella sezione delle alternative. `targets_inconsistent` rimanda al profilo.
- `objectives`, `robustness`, `optimization` e `pool` vanno nei «Dettagli tecnici».
- Scelta e valutazione funzionano come oggi; il voto alimenta S6 con i bracci del piano.

## 8. Estensione v2 (settimana, dieta + palestra)

- `horizon.days = 7`. Le variabili sono indicizzate per giorno. La diversità del §4 si applica sull'intera settimana, con in più «la stessa fonte proteica principale al massimo N volte» (N da regole della dieta o default 3).
- I candidati palestra arrivano da `plan_workout_week.py`. Ogni giorno ha il tipo allenamento/riposo, che sceglie i target nutrizionali del giorno quando la dieta li distingue.
- `training_fit` entra in S3; la robustezza usa anche i modelli energetici per attività di Salute, senza sommare due volte le calorie dei workout.
- Il diff aggiunge `sessions_added`, `sessions_removed`, `sessions_moved`.

## 9. Test richiesti

1. Ogni piano restituito ha `constraint_report.verified` e `all_respected`.
2. Ogni coppia di piani ha distanza ≥ `min_distance`, salvo riduzione registrata in `diversity_relaxed`.
3. Ogni piano rispetta la regione quasi-ottima di S2.
4. Nessun duplicato; ruoli unici; ruoli omessi quando non applicabili (nessun riempimento).
5. `diff` coerente con i piani (proprietà del §6); `best.diff` è `null`.
6. Stesso input e stesso `seed` → stesso `PlanSet` (a meno di `run_id` e timestamp).
7. S0 segnala i target demo attuali come incoerenti.
8. Senza Salute: `robustness.status = "unavailable"` e nessun ruolo `robust`.
9. Il bandit usa solo piani provati; generare e scegliere non cambiano i conteggi.
10. `strategy` legacy viene ignorato con warning; i piani storici restano leggibili dall'interfaccia.

## 10. Parametri di default

| Parametro | Default | Note |
|---|---|---|
| `k` | 4 | piani mostrati, massimo 5 |
| `pool_size` | 12 | candidati prima del filtro |
| `epsilon` | 0.05 | regione quasi-ottima relativa |
| `min_distance` | 3 | alimenti variabili per giornata; settimana: da tarare in v2 |
| `structural` | true | cambia proteina o amido principale |
| tempo massimo pool | 20 s | poi `status: partial` se c'è almeno un piano |
