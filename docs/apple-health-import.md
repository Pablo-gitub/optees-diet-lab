# Importazione Apple Salute

La pagina **Salute** mostra misure corporee con data e fonte, consumi stimati su 7/14/28 giorni, scenari empirici e storico degli allenamenti. I dati appartengono al singolo profilo e restano nei file privati esclusi da Git.

Il proprietario dell'importazione può sostituire lo ZIP nella cartella `sanitary_data_export` e premere **Esamina nuova estrazione**. Deve esserci un solo ZIP. Il parsing è in streaming: non occorre estrarre tutto l'archivio. Un archivio già elaborato viene riutilizzato; un errore di parsing conserva il precedente riepilogo.

Per l'importazione iniziale da terminale: `python scripts/import_apple_health.py --owner paolo`. Il profilo deve già esistere nel database web. Database e riepilogo sono salvati in `data/personal/health/user_<id>`.

## Regole dell'analisi

- Energia attiva e a riposo sono separate. Le calorie degli allenamenti non vengono sommate nuovamente al totale giornaliero.
- Le sovrapposizioni privilegiano Watch, poi iPhone e altre fonti; a parità, l'intervallo più breve e la registrazione più recente. Le calorie sono distribuite uniformemente nell'intervallo e aggregate nel fuso Europe/Rome.
- Giorni mancanti e giorno corrente non valgono zero. Una copertura del riposo di almeno 20/24 della giornata, insieme alla presenza di energia attiva, rende il giorno utilizzabile: è un indicatore di copertura, non prova di uso continuo del dispositivo.
- Gli scenari basso/centrale/alto sono percentili 20/50/80 del consumo osservato sui 28 giorni disponibili, non intervalli di confidenza. Servono almeno sette giorni utilizzabili e una base non più vecchia di 14 giorni.
- I modelli per attività usano fino a venti osservazioni recenti. Meno di tre osservazioni o dati più vecchi di 90 giorni impediscono di considerarli aggiornati. Non descrivono ancora protocolli, carichi e risposta individuale all'allenamento.
- La percentuale di grasso HealthKit è memorizzata come frazione e visualizzata in punti percentuali, secondo la [documentazione Apple](https://developer.apple.com/documentation/healthkit/hkunit/percent()).
- Frequenza cardiaca campione per campione, sonno e itinerari sono esclusi dalla prima importazione; eventuali statistiche cardiache delle sessioni sono conservate.

## Collegamento agli algoritmi

`scripts/health_inputs.py` e l'endpoint autenticato `/api/health` forniscono misure, provenienza, anzianità, disponibilità della base calorica e scenari. La freschezza viene ricalcolata anche senza una nuova importazione. Gli obiettivi nutrizionali restano configurati separatamente.

Questa è la base del primo passaggio. Restano da collegare i candidati fattibili di dieta e palestra, confrontarli insieme con Pareto, bilanciarli con Min-Max/Max-Min, valutare separatamente la robustezza calorica e apprendere dal feedback delle combinazioni effettivamente provate.
