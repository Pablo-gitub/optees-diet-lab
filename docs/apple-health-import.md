# Importazione e aggiornamento dei dati Apple Salute e Withings

Questa guida descrive la procedura operativa per esportare periodicamente i dati sanitari da iPhone (Apple Salute) e dalla bilancia intelligente (Withings), importarli nella piattaforma e verificare la copertura richiesta dagli algoritmi di ottimizzazione congiunta dieta/allenamento.

I dati sanitari appartengono al profilo privato dell'utente e risiedono esclusivamente in cartelle locali non tracciate da Git (`data/personal/health/user_<id>/`). Le stime del dispositivo non alterano automaticamente gli obiettivi calorici e nutrizionali configurati nel profilo.

---

## 1. Esportazione dall'iPhone e Collegamento Withings

### 1.1 Esportazione completa da Apple Salute (iOS)
1. Aprire l'applicazione **Salute** su iPhone.
2. Toccare l'icona del proprio profilo / avatar in alto a destra («da verificare sul telefono»).
3. Scorrere in fondo alla schermata e selezionare **Esporta tutti i dati sanitari** («da verificare sul telefono»).
4. Confermare l'operazione quando richiesto dal sistema. iOS avvierà l'estrazione e la compressione dei dati in background. Il processo può richiedere alcuni minuti a seconda del volume dello storico.
5. Al termine, tramite il menu di condivisione di iOS («da verificare sul telefono»), trasferire il file compresso generato (`export.zip` o `dati esportati.zip`) sul computer (es. via AirDrop, cavo USB o servizio di condivisione file sicuro).

> [!NOTE]
> Il file ZIP prodotto da Apple contiene `export.xml` (e facoltativamente `export_cda.xml`, ignorato dal sistema). L'archivio non deve essere decompresso manualmente sul computer: il motore di importazione legge il flusso XML in streaming direttamente dall'archivio ZIP.

### 1.2 Collegamento Withings → Apple Salute (Peso e Composizione Corporea)
Per assicurare che le misurazioni di peso e massa grassa confluiscano automaticamente nell'esportazione sanitaria di iOS:
1. Aprire l'applicazione **Withings** (Withings App / Health Mate) sul proprio iPhone.
2. Accedere alla scheda **Profilo** → **App e partner** (o **Impostazioni**) e selezionare **Apple Salute** («da verificare sul telefono»).
3. Verificare e abilitare i permessi di scrittura verso Apple Salute per le seguenti metriche:
   - **Peso corporeo** (`HKQuantityTypeIdentifierBodyMass`)
   - **Percentuale di grasso corporeo** (`HKQuantityTypeIdentifierBodyFatPercentage`)
   - **Altezza** (`HKQuantityTypeIdentifierHeight`)
   - **Indice di massa corporea** (`HKQuantityTypeIdentifierBodyMassIndex`)
4. Nell'app **Salute** di iOS, andare su **Condivisione** → **App** → **Withings** («da verificare sul telefono») e verificare che la scrittura delle suddette metriche risulti regolarmente concessa.
5. In questo modo ogni pesata effettuata sulla bilancia Withings viene sincronizzata con HealthKit e inclusa nell'export cumulativo.

---

## 2. Dove Mettere lo ZIP e Come Eseguire l'Importazione

### 2.1 Collocazione dell'archivio
- Posizionare il file ZIP nella cartella:
  ```text
  sanitary_data_export/
  ```
- **Regola fondamentale**: nella cartella deve essere presente **un solo file con estensione `.zip`** (es. `sanitary_data_export/dati esportati.zip`).
- Quando si dispone di una nuova estrazione, questa deve **sostituire** la precedente (cancellare o sovrascrivere il vecchio ZIP prima di avviare l'import).

### 2.2 Avvio dell'importazione
L'importazione può essere eseguita indifferentemente in due modi:

#### Modalità A — Da interfaccia web (Consigliata)
1. Accedere all'applicazione web e aprire la sezione **Progressi** (o la scheda **Salute**).
2. Nel riquadro **Dati da Apple Salute**, cliccare sul pulsante **Esamina nuova estrazione** (`button#health-import`).
3. L'interfaccia mostrerà l'avanzamento in tempo reale (`Importazione in corso · N record esaminati`), aggiornandosi ogni 3 secondi.
4. Al termine, il pulsante si riabilita e viene visualizzato il messaggio *«Importazione completata»* (oppure *«Esportazione già esaminata»* se l'archivio era identico per CRC32/dimensione a quello già presente).

#### Modalità B — Da riga di comando (CLI)
Dal terminale, posizionandosi nella root del progetto:
```bash
python scripts/import_apple_health.py --owner paolo
```
Per forzare la reindicizzazione anche se l'impronta (fingerprint) dell'archivio non è cambiata:
```bash
python scripts/import_apple_health.py --owner paolo --force
```

### 2.3 Resilienza ai guasti: cosa succede se l'import fallisce
Il processo di importazione è progettato per essere **completamente atomico e sicuro**:
- Durante l'estrazione, il codice non modifica né sovrascrive mai direttamente il database attivo (`health.sqlite`) né il file di sintesi (`summary.json`).
- L'importazione crea e popola un database temporaneo isolato:
  `data/personal/health/user_<id>/health.importing.sqlite` (`scripts/apple_health.py:170`).
- Se durante il parsing dell'XML, la normalizzazione o la generazione degli scenari si verifica un qualsiasi errore (archivio corrotto, interruzione di rete o del processo, crash):
  1. Il blocco di gestione eccezioni intercetta l'evento (`scripts/apple_health.py:229-232`).
  2. La connessione al DB temporaneo viene chiusa e il file `health.importing.sqlite` viene **eliminato dal disco** (`temporary.unlink()`).
  3. Il database `health.sqlite` precedente e il report `summary.json` **rimangono perfettamente intatti, validi e operativi**. Nessun dato pregresso va perso.
  4. L'endpoint web registra l'errore e imposta lo stato di fallimento: *«Importazione non riuscita; il riepilogo precedente resta disponibile.»* (`web/app.py:449`).
- Solo al termine positivo di tutti i passaggi, i file temporanei vengono promossi a definitivi tramite sostituzione atomica del filesystem (`os.replace`) per il database SQLite (`scripts/apple_health.py:227`) e per il riepilogo JSON (`scripts/apple_health.py:227`).

---

## 3. Frequenza consigliata di aggiornamento

### Il lunedì mattina, dopo la pesata e prima del check-in
1. **Pesata** a digiuno del lunedì (bilancia Withings → Apple Salute, oppure inserimento manuale in Progressi).
2. **Esportazione e importazione** dei dati Salute come descritto sopra.
3. **Check-in** del lunedì in Progressi.

Il motivo è nel codice. Un giorno è utilizzabile solo se precede la data dell'importazione (`date < today` in `summarize()`, [`scripts/apple_health.py`](../scripts/apple_health.py)). La proposta di ricalibrazione richiede il consumo Salute di **tutte** le quattordici giornate che terminano la domenica prima del check-in (`progress_recalibration.py`, «Consumo Salute recente e completo richiesto sugli stessi quattordici giorni»). Un'importazione fatta la domenica sera esclude la domenica: il check-in del lunedì non produrrebbe alcuna proposta.

Durante la settimana basta un'importazione ogni 7–10 giorni: la base di consumo resta valida se l'ultimo giorno utilizzabile ha al massimo 14 giorni.

---

## 4. Verifica di Copertura dei Dati per gli Algoritmi

La tabella seguente riassume i requisiti e le soglie minime di copertura necessarie affinché gli algoritmi di pianificazione congiunta dieta + palestra possano operare con gli scenari empirici e la modalità robusta.

| Dato / Parametro | Soglia richiesta per la validità | Verifica nel codice (File, Funzione, Righe) | Conseguenza e Fallback se mancante o non rispettato |
|---|---|---|---|
| **Giorno usabile per baseline (`usable_for_baseline`)** | • Data precedente a oggi: `date < today`<br>• Copertura energia a riposo: $\ge \frac{20}{24}$ della giornata (`expected * 20 / 24`, gestendo giorni da 23h o 25h per ora legale/solare)<br>• Copertura energia attiva: $> 0$ secondi | [`scripts/apple_health.py`](../scripts/apple_health.py)<br>`summarize()`<br>Righe 102–106 | Il singolo giorno non viene considerato utilizzabile per la statistica (`usable_for_baseline = False`) e non entra nel pool di calcolo della baseline. Non viene considerato come zero né altera la media. |
| **Baseline spesa non di allenamento (`non_workout_baseline` / `scenarios`)** | • Finestra di analisi: 28 giorni precedenti l'ultimo giorno usabile (`anchor`)<br>• Almeno **7 giorni usabili** nella finestra (`valid_days >= 7`)<br>• Anzianità dell'ancora: **$\le 14$ giorni** (`0 <= staleness_days <= 14`) | [`scripts/apple_health.py`](../scripts/apple_health.py)<br>`summarize()`: 110–116<br>[`scripts/joint_energy.py`](../scripts/joint_energy.py)<br>`non_workout_baseline()`: 34–41<br>[`scripts/health_inputs.py`](../scripts/health_inputs.py)<br>`refresh_report()`: 17–19, 30–33<br>[`scripts/joint_energy.py`](../scripts/joint_energy.py)<br>`day_scenarios()`: 45–46 | `status` diventa `'insufficient_or_stale'`. In `day_scenarios()` lo stato passa a `status='unavailable'` (*«Base Salute senza allenamenti insufficiente o non recente.»*). La settimana congiunta viene comunque generata con gli obiettivi indicati, ma senza valutazione di robustezza (Min-Max e rimpianto); nessun dispendio viene inventato. Anche la proposta di ricalibrazione del lunedì non viene generata. |
| **Sottrazione allenamenti osservati dalla baseline** | • Allenamento con calorie attive finite (`finite(active_kcal)`)<br>• Nessuna sovrapposizione temporale con altri allenamenti<br>• Calorie di allenamento rimosse $\le$ calorie attive totali del giorno $+ 0.01$ | [`scripts/joint_energy.py`](../scripts/joint_energy.py)<br>`non_workout_baseline()`<br>Righe 23–38 | Se un giorno contiene allenamenti privi di calorie o sovrapposti, l'intera giornata viene esclusa (`excluded_days`). Se a seguito delle esclusioni i giorni validi scendono sotto 7, la baseline diventa `'insufficient_or_stale'`. |
| **Modelli energetici attività (`workout_forecasts` / `workout_energy_models`)** | • Almeno **3 osservazioni** per la specifica attività Apple (`observations >= 3`)<br>• Considerate fino alle ultime 20 osservazioni per il calcolo dei quantili P20, P50, P80 di `kcal/min`<br>• Età dell'ultima osservazione: **$\le 90$ giorni** (`0 <= age_days <= 90`)<br>• Coerenza quantili: `P20 <= P50 <= P80` | [`scripts/apple_health.py`](../scripts/apple_health.py)<br>`summarize()`: 139–145<br>[`scripts/health_inputs.py`](../scripts/health_inputs.py)<br>`refresh_report()`: 20–23<br>[`scripts/joint_energy.py`](../scripts/joint_energy.py)<br>`day_scenarios()`: 49–52 | Se un'attività non ha almeno 3 osservazioni negli ultimi 90 giorni, lo stato è `'insufficient_or_stale'`. Se una sessione programmata della giornata richiede tale attività, `day_scenarios()` restituisce `status='unavailable'` con motivazione *«Modello energetico recente mancante per <session_id>»*. Gli scenari congiunti per quel giorno non vengono calcolati. |
| **Mappatura sessioni catalogo $\to$ attività Apple** | La sessione deve essere presente nel dizionario `ACTIVITIES` di `joint_energy.py`:<br>• `continuous_stationary-bike` $\to$ `Cycling`<br>• `interval_bike` $\to$ `Cycling`<br>• `continuous_rowing-machine` $\to$ `Rowing`<br>• `continuous_incline-treadmill-walk` $\to$ `Walking`<br>• `continuous_elliptical-trainer` $\to$ `Elliptical` | [`scripts/joint_energy.py`](../scripts/joint_energy.py)<br>`ACTIVITIES`: 7–13<br>`day_scenarios()`: 47–51 | Se una sessione non è mappata in `ACTIVITIES` (es. sessioni di forza come `strength_dumbbells`, `hypertrophy_basic`, `isometric_core`), `activity` risulta `None` e il modello associato non esiste. `day_scenarios()` restituisce `status='unavailable'` e blocca la stima energetica della sessione, impedendo calcoli calorici arbitrari per esercizi con sovraccarichi. |
| **Peso corporeo (`measures['weight']`)** | • Misura presente nel database<br>• Età dell'ultima pesata: **$\le 90$ giorni** (`measures['weight']['age_days'] <= 90`) | [`scripts/apple_health.py`](../scripts/apple_health.py)<br>`summarize()`: 119–121, 148<br>[`scripts/health_inputs.py`](../scripts/health_inputs.py)<br>`refresh_report()`: 16, 34 | Se la misura manca o è più vecchia di 90 giorni, il flag `body_profile_needs_review` diventa `True`. L'applicazione segnala all'utente l'esigenza di aggiornare la misura antropometrica di base, mantenendo comunque l'accesso alle funzionalità della piattaforma. |

---

## 5. Cosa Fare se Qualcosa Non Va: Risoluzione dei Problemi

Di seguito vengono analizzate le casistiche di errore più frequenti riscontrabili durante l'aggiornamento dei dati:

### 5.1 Più di uno ZIP nella cartella (`sanitary_data_export/`)
- **Comportamento nel codice**: in [`web/app.py`](../web/app.py), l'endpoint `/api/health/import` conta tutti i file `.zip` in `sanitary_data_export/`:
  ```python
  archives = list((ROOT / 'sanitary_data_export').glob('*.zip'))
  if len(archives) != 1:
      raise HTTPException(400, 'Lascia un solo ZIP nella cartella delle esportazioni sanitarie')
  ```
- **Sintomo in UI**: la richiesta fallisce con HTTP 400 e compare l'errore: *«Lascia un solo ZIP nella cartella delle esportazioni sanitarie»*.
- **Risoluzione**: aprire la cartella `sanitary_data_export/`, eliminare i file ZIP precedenti, le copie duplicate (es. `export (1).zip`, `export_vecchio.zip`) e conservare unicamente il file ZIP più recente, quindi premere nuovamente **Esamina nuova estrazione**.

### 5.2 Importazione già in corso o blocco residuo
- **Comportamento nel codice**: in [`web/app.py`](../web/app.py):
  ```python
  if (health_directory(user['id']) / 'health.importing.sqlite').exists():
      raise HTTPException(409, 'Importazione esterna già in corso')
  if health_lock.locked() or (health_task and not health_task.done()):
      raise HTTPException(409, 'Importazione già in corso')
  ```
- **Sintomo in UI**: pulsante disabilitato o risposta HTTP 409 con messaggio *«Importazione già in corso»* o *«Importazione esterna già in corso»*.
- **Risoluzione**:
  - Se un'importazione è effettivamente in corso (visibile dallo stato che conta i record analizzati), attendere qualche istante fino al completamento.
  - Se il processo precedente è stato terminato in modo anomalo (es. riavvio improvviso del server durante l'elaborazione) e rimane presente il file `health.importing.sqlite`, verificare che nessun processo Python sia in esecuzione e rimuovere manualmente il file `health.importing.sqlite` dalla cartella `data/personal/health/user_<id>/`, quindi ripetere l'operazione.

### 5.3 Dati troppo vecchi (Staleness / Obsolescenza)
- **Comportamento nel codice**: la funzione `refresh_report` in [`scripts/health_inputs.py`](../scripts/health_inputs.py) ricalcola l'anzianità dei dati rispetto alla data odierna a ogni consultazione:
  - Se `staleness_days > 14` giorni dall'ultimo giorno valido della baseline, `scenarios['status']` passa a `'insufficient_or_stale'`.
  - Se `age_days > 90` giorni dall'ultima sessione di un'attività, `workout_forecasts['status']` passa a `'insufficient_or_stale'`.
  - Se `age_days > 90` giorni dall'ultima pesata, `body_profile_needs_review` diventa `True`.
- **Sintomo in UI**: nella scheda Salute, gli scenari o i modelli mostrano lo stato *«Insufficiente/obsoleto»*, e la pianificazione congiunta non rende disponibile il ruolo robusto.
- **Risoluzione**: eseguire una nuova estrazione dall'app Salute su iPhone (avendo cura di sincronizzare preventivamente Apple Watch e l'app Withings), posizionare il nuovo ZIP e avviare l'importazione.

### 5.4 Allenamenti senza calorie attive
- **Comportamento nel codice**:
  - Se un `Workout` esportato non include il riepilogo `active_kcal` (es. sessione registrata da app terze o frequenza cardiaca non acquisita), il parser tenta di ricostruire le calorie integrando i campioni `active_energy` registrati nell'intervallo temporale della sessione ([`scripts/apple_health.py`](../scripts/apple_health.py)).
  - Se i campioni coprono almeno il 50% della durata (`fraction >= 0.5`), le calorie vengono ricostruite con etichetta `energy_samples_in_workout_window`.
  - Se la copertura è inferiore al 50%, `active_kcal` rimane nullo. Di conseguenza, in [`scripts/joint_energy.py`](../scripts/joint_energy.py), la giornata contenente questo allenamento viene marcata come non affidabile (`bad`) ed esclusa dalla baseline del dispendio.
- **Risoluzione**: verificare che durante l'allenamento l'Apple Watch sia allacciato correttamente per registrare battito ed energia attiva, e che l'app di tracciamento abbia i permessi di scrittura per `HKQuantityTypeIdentifierActiveEnergyBurned`.

### 5.5 Sessioni sovrapposte (Overlapping workouts)
- **Comportamento nel codice**: in [`scripts/joint_energy.py`](../scripts/joint_energy.py), durante l'elaborazione dei workout per la baseline, viene verificata l'intersezione temporale tra sessioni nella stessa giornata:
  ```python
  if any(a < other_b and other_a < b for other_a, other_b in intervals.get(date, [])):
      bad.add(date)
  ```
- **Sintomo**: se due sessioni registrate (es. una da Apple Watch e una importata da Strava o altra app) hanno orari sovrapposti, l'intera giornata viene contrassegnata in `bad` ed esclusa dal calcolo della spesa non di allenamento (`excluded_days`).
- **Risoluzione**: aprire l'app **Salute** su iPhone, andare su **Attività** → **Allenamenti** → **Mostra tutti i dati** («da verificare sul telefono») e individuare la sessione duplicata o sovrapposta; eliminare l'allenamento duplicato, quindi generare una nuova esportazione.

---

## 6. Regole dell'analisi

- Energia attiva e a riposo sono separate. Le calorie degli allenamenti non vengono sommate di nuovo al totale giornaliero.
- Le sovrapposizioni privilegiano Watch, poi iPhone e altre fonti; a parità, l'intervallo più breve e la registrazione più recente. Le calorie sono distribuite uniformemente nell'intervallo e aggregate nel fuso Europe/Rome.
- Giorni mancanti e giorno corrente non valgono zero. La copertura del riposo è un indicatore di completezza, non la prova di un uso continuo del dispositivo.
- Gli scenari basso/centrale/alto sono i percentili 20/50/80 del consumo osservato nei 28 giorni disponibili, non intervalli di confidenza.
- La percentuale di grasso HealthKit è memorizzata come frazione e visualizzata in punti percentuali, secondo la [documentazione Apple](https://developer.apple.com/documentation/healthkit/hkunit/percent()).
- Frequenza cardiaca campione per campione, sonno e itinerari non vengono importati; le statistiche cardiache delle sessioni sono conservate.

## 7. Collegamento agli algoritmi

`scripts/health_inputs.py` e l'endpoint autenticato `/api/health` forniscono misure, provenienza, anzianità e scenari; la freschezza viene ricalcolata anche senza una nuova importazione. I dati Salute servono a:

- **settimana congiunta** (4.1–4.2): scenari di consumo per giorno, robustezza Min-Max e rimpianto ([joint-orchestration.md](joint-orchestration.md));
- **check-in del lunedì e ricalibrazione** (5.1–5.2): consumo medio delle due settimane e pesate ([backend-handoff-progress.md](backend-handoff-progress.md)).

Gli obiettivi nutrizionali non cambiano mai automaticamente: ogni variazione è una proposta da approvare.
