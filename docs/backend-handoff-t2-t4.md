# Consegna backend T2/T4 a Claude

Nessuna modifica a `web/static/`. Il backend mantiene piani storici e feedback precedenti.

Verifica finale: 158 test superati. Audit Optees con target demo della giornata completa: entrambe le settimane di entrambe le diete hanno una soluzione verificata; tre risultati sono `partial` entro il limite di tempo. Dopo la discretizzazione, l'audit su quattro giornate restituisce due alternative non dominate in due giornate (distanze 5 e 4) e un solo piano non dominato nelle altre due: non si riempiono le card con soluzioni dominate. Il precedente audit del passo 1.2, prima della discretizzazione, aveva distanza media 4–5 in tutte e quattro le giornate. Il server locale è stato riavviato con i nuovi endpoint.

## Catena della giornata

`POST /api/generate` restituisce direttamente il PlanSet v1, con `run_id`, `plans`, `warnings`, `pool`, versioni e hash. Ogni piano ha un ID selezionabile e valutabile attraverso gli endpoint esistenti. `count` resta per compatibilità. `strategy` è ignorato con warning. La generazione e la scelta non producono ricompense: vengono usati solo i voti esplicitamente associati a piani provati, nel contesto corretto. Le osservazioni dei vecchi bracci-metodo restano archiviate e non alimentano i nuovi bracci.

Quantità generate: multipli di 5 g, oppure confezioni intere (anche da 32 g). I nutrienti e la verifica dei limiti usano le quantità effettive. Quantità già consumate e bloccate possono essere intere senza essere multiple di 5: non vengono alterate.

## Diario e lettura

Endpoint e transizioni seguono `api-contract.md`. I totali del consumato sono `null` quando nessuno slot è registrato; un pasto saltato è esplicitamente registrato con zero calorie. La copertura riguarda gli slot pianificati; spuntini fuori piano sono `unplanned`. Qualunque nutriente mancante rende `null` il relativo totale, senza sostituirlo con zero.

Le misure manuali supportate sono peso/kg, altezza/cm, circonferenza vita/cm e grasso corporeo/%. `GET /api/measurements` unisce le misure manuali con quelle Salute dello stesso proprietario. Le statistiche avanzate restano `insufficient_data` fino al passo 5.1.

FoodRef supporta CREA, OFF, user_label e recipe. Per una composizione effettivamente calcolata dal solver: `{"source":"recipe","id":"run:<id>"}`. L'ID deve appartenere al proprietario. Il denominatore è il peso totale degli ingredienti della porzione calcolata, **non** la resa dopo cottura. Non è disponibile una conversione automatica al peso cotto. Etichette OFF per 100 ml o con base incerta conservano nutrienti sconosciuti nel diario basato sui grammi.

## Settimana

`POST /api/plans/week` restituisce 202 con `job_id`. I job e i PlanSet sono persistiti e isolati per utente. Dopo un riavvio i job incompleti risultano interrotti e possono essere ripetuti.

Il modello contiene sette giornate nello stesso MILP. Mantiene abbinamenti del calendario, porzioni, esclusioni, limiti giornalieri e locali. Aggiunge i vincoli di frequenza. La robustezza congiunta con palestra rimane nel passo 4.2.

Opzioni aggiuntive:

- `day_index`: indice iniziale 0–13 del calendario della dieta; altrimenti il giorno della settimana di `week_start`.
- `max_protein_repetitions`: massimo per **singolo alimento proteico principale**, default 3. È un conteggio per ID canonico CREA/alimento, non per famiglia ampia come «pesce». Il braccio del bandit usa invece la famiglia. Più marche dello stesso ingrediente non sono ancora candidati distinti del modello giornaliero.
- `protein_frequencies`: oggetto ID alimento → `{min,max}`; limiti rigidi espliciti, non ricavati automaticamente dal testo delle diete.
- `locked`: lista di `{date,slot,items:[{food,grams,units?}]}`. Per bloccare un giorno si elencano tutti i suoi pasti. Il server aggiunge automaticamente i pasti già registrati e quelli pianificati bloccati, dando priorità al consumato.
- `k`, `pool_size`, `epsilon`, `seed`, `time_limit` e `solve_time_limit`: configurazione del campione e del budget di calcolo.

La fonte principale è l'ultimo gruppo proteico della combinazione verificata: un legume come accompagnamento non conta come seconda fonte principale. Per un pasto consumato/bloccato si usa l'ingrediente che contribuisce più proteine, con spareggio deterministico. La scelta è riportata nella verifica, il cui `frequency_scope` è `principal_food_id_per_meal`.

Ogni piano settimanale contiene `days` con data, indice originale della dieta, selezioni, nutrienti e verifica del giorno; contiene inoltre nutrienti aggregati, frequenze, ruolo, spiegazione, diff per giorno e verifica globale. `status: partial` significa che esiste una soluzione fattibile verificata ma la ricerca o la certificazione dell'ottimo è terminata per il budget di tempo. Non va mostrato come ottimo certificato.

L'applicazione sostituisce soltanto gli slot non registrati e non bloccati, restituendo `skipped_slots` e `applied_slots`. Non modifica il diario. Un piano settimanale va applicato con il nuovo endpoint, non con il vecchio pulsante di selezione di un piano giornaliero.

## Alternative per pasto

`POST /api/plans/meal-alternatives` crea un job. Il backend fissa consumato o pianificato di tutti gli altri pasti. Nutrienti mancanti o un piano incompleto impediscono la verifica e producono un errore esplicito. L'indice della dieta salvato col pasto evita di confondere la prima e la seconda settimana.

Il risultato contiene `date`, `slot` e un orizzonte di un pasto. Le selezioni e i nutrienti esposti riguardano il pasto sostituibile; `nutrients_by_meal` e `constraint_report` conservano la verifica della giornata completa. `diff.reference_plan` è `current_meal`. Si applica solo con `scope: meal` e la stessa data e slot. I ruoli e la diversità possono essere limitati dagli abbinamenti e dalle preferenze rigide.
