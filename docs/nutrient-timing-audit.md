# Audit backend 8.13 — 2026-10-07

Suite completa finale: 354 test verdi in 293,243 s, comando previsto dal piano
con ambiente .env e PYTHONPATH=scripts:tests:.

Nove test dedicati con fixture sintetiche e DB temporanei: soglia stretta >60
minuti, orario necessario, richiesta esplicita/disattivazione, peso filtrato,
fine del pasto prima e inizio del primo pasto dopo, suggerimento durante solo
>90 minuti e mai pianificato, target morbidi impossibili, pasti bloccati,
fibre ignote non zero, fallback verificabile, kcal di ogni giorno invarianti,
Min-Max, candidati congiunti prima dell’applicazione, persistenza in DayView,
redistribuzione effettiva su un caso con margine, invalidazione dopo modifiche e PUT parziale che conserva la configurazione.

Prova col vero MCP Optees, profilo sintetico di 80 kg, sessione 75 minuti alle
17:00: due solve in 0,934 s, optimal; 1.303,1 kcal prima e dopo. Tutti i
vincoli nutrizionali rigidi rispettati. Questo è un caso di test, non un
obiettivo personale. Carboidrati prima 47,35 g contro quota provvisoria 80 g;
proteine dopo 36,39 g contro intervallo provvisorio 20–32 g: scostamenti
riportati e spiegati, senza sacrificare i target giornalieri o aumentare kcal.

Nel caso sintetico con totali fissi ma margine nella distribuzione, il solver
porta i carboidrati prima da 50 ad almeno 80 g, i grassi prima da 20 ad al
massimo 9 g e le proteine dopo da 50 nell’intervallo 20–32 g, mantenendo
1.300 kcal. Nel caso reale sopra il compromesso ottimo non lascia margine:
è corretto mantenere le porzioni e spiegare le quote non soddisfatte.

La redistribuzione è un secondo passaggio lessicografico: non peggiora
l’obiettivo iniziale e blocca l’energia effettiva di ciascun giorno. Per la
settimana blocca anche le giornate senza timing attivo. Mantiene i vincoli di
sovrapposizione già trovati e i pasti bloccati. Se non verifica una soluzione,
restituisce quella iniziale con spiegazione, senza applicazioni automatiche.

Parametri in config/nutrient-timing.json (nutrient-timing-v1, provvisorio).
Fonte primaria verificata: ISSN 2017,
https://link.springer.com/article/10.1186/s12970-017-0189-4.
Fattori rispetto alla media e pesi obiettivo sono euristiche dichiarate, non
soglie cliniche attribuite alla fonte. La matrice 8.2 deve fissare le dosi.

Orari pasti predefiniti dichiarati provvisori, sovrascrivibili nel profilo.
Se la sessione termina il giorno seguente, il risultato spiega che non è
collegato automaticamente un pasto di un altro giorno. Nessun orario,
peso, fibra mancante o bevanda viene inventato. Nessuna modifica a web/static/.
