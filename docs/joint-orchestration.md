# Contratto backend — settimana congiunta (4.1–4.2)

Estensione di `orchestration.md` §8. `web/static/` è riservato al prossimo turno frontend.

## Generazione e applicazione

`POST /api/plans/joint-week` usa cookie e CSRF, restituisce 202 `{job_id}`. Lettura tramite job e PlanSet esistenti. Corpo:

- `week_start`, `mode?`, `day_index?`, `locked?`: come la settimana dieta.
- `workout`: disponibilità e vincoli come `POST /api/workouts/week`; `week_start` viene preso dall'orizzonte comune. Le sessioni già registrate o saltate vengono bloccate dal server.
- `day_targets`: `rest` e `training`, ciascuno con i quattro nutrienti e `min/target/max` del contratto. Sono target espliciti per tutta la giornata, non suggeriti automaticamente da Salute. Il profilo deve includere colazione e spuntini (`daily_meals.enabled:true`).
- `diet?`: `pool_size`, `k`, `epsilon`, `time_limit`, `solve_time_limit`, `max_protein_repetitions`, `protein_frequencies`, `portion_bounds_g`.
- `k?`: 1–5 piani finali; default 4.
- `energy_balance_target_kcal?`: deficit (negativo) o surplus (positivo) esplicitamente scelto; `null` lascia indisponibile la robustezza.
- `workout_activity_map?`: corrispondenze esplicite id sessione → tipo Apple. Le sessioni cardio hanno corrispondenze locali dichiarate; nessuna conversione automatica del punteggio muscolare in calorie.

S1–S2: candidati palestra fattibili dal modello settimanale esistente; per ciascuno, MILP dieta di sette giorni con target del tipo di giornata. Limiti nutrizionali, porzioni da 5 g, frequenze, disponibilità, attrezzatura e pasti già registrati restano vincoli duri. Ogni candidato combinato ha entrambi i rapporti di verifica. Si tratta di una ricerca su un pool limitato, non dell'ottimo globale su tutte le schede possibili.

S3: fronte campionato su scarto nutrizionale, errore peggiore, preferenze, varietà e `training_fit`. Quest'ultimo espone copertura muscolare euristica e costo di tempo separatamente; nessuna efficacia clinica o calorie dedotte da questi punteggi. S5–S7: ruoli unici, bracci alimentari e protocollo, diff alimenti e `sessions_added/removed/moved`.

Il PlanSet ha `kind:"joint"`. Ogni piano contiene `days` con `date`, `day_type`, `mode`, `targets`, `energy_scenarios`, `workout_sessions`, oltre ai pasti, e una lista settimanale `workout_sessions`. `apply {plan_id,scope:"week"}` applica dieta e palestra in una transazione; restituisce DayView e slot protetti. Configurazione o registri cambiati dopo la generazione richiedono una rigenerazione (409). Nessuna applicazione automatica o riscrittura dei dati eseguiti.

## Dispendio: niente doppio conteggio

La somma Salute `resting + active` include già le sessioni. La nuova base è il totale dei giorni completi meno l'energia degli allenamenti osservati negli stessi giorni. Un giorno con energia workout mancante, sessioni sovrapposte o sottrazione maggiore delle calorie attive viene escluso. Richiesti almeno sette giorni utilizzabili in 28 e dati recenti (14 giorni). I giorni senza workout conservano il proprio totale, senza sottrazioni inventate.

Gli scenari giornalieri sono base senza workout + energia delle sessioni pianificate **una sola volta**. Il modello per tipo Apple richiede almeno tre osservazioni recenti (90 giorni) e porta provenienza, quantili e ipotesi di scalatura alla durata completa della sessione, compresi recuperi. Un modello mancante non equivale a zero: scenario non disponibile. La base contiene già riposo e attività ordinaria; non si aggiungono MET o altre formule per sostituire dati mancanti. Nessun target viene alterato automaticamente dal dispendio.

## Robustezza (4.2)

Disponibile solo con scenari completi e bilancio esplicito. Per ogni scenario correlato basso/centrale/alto, perdita = media dei sette errori assoluti giornalieri `|apporto − consumo − bilancio|`. La media degli errori evita che surplus e deficit di giorni diversi si cancellino.

Min-Max minimizza la perdita peggiore; regret sottrae, scenario per scenario, il miglior valore nel pool comparabile. Entrambi sono verificati indipendentemente e dichiarano lo scope del pool campionato. Il selettore lineare di Optees `scenario.linear.min_max_loss` usa variabili binarie one-hot sui candidati, per la perdita e separatamente per il regret; non mescola frazioni di settimane. Il ruolo robusto viene omesso con un solo candidato distinto o scenari insufficienti, con motivo esplicito. Nessuna robustezza globale è dichiarata.

## Verifica 4.1

188 test verdi; audit reale Optees su sette giorni con target distinti, quantità a passi di 5 g e vincoli dieta/palestra verificati. Il pool è campionato: non certifica un ottimo globale congiunto. Il passo 4.2 completa la robustezza. Nessuna modifica a `web/static/`.
