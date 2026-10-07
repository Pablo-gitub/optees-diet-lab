# Base senza Salute — audit 2026-10-07

Suite completa: 358 test verdi in 303,915 s, .env e comando unittest del piano.

Rimosso il fallback target di riposo meno bilancio: nessun target alimentare,
peso obiettivo o valore dimostrativo entra nella nuova base.

Mifflin–St Jeor semplificata, fonte primaria verificata:
https://pubmed.ncbi.nlm.nih.gov/2305711/. Peso filtrato da pesate recenti,
altezza/età/sesso/fattore dichiarati in goals.body, senza default.
Provenienza «stima da formula»; intervallo ±10% richiesto dall’utente,
dichiarato di sensibilità, non intervallo di confidenza. Il fattore non
accredita le sessioni aggiuntive che il planner somma separatamente.

Fixture sintetica: 80 kg filtrati, 180 cm, 40 anni, male, fattore 1,2:
riposo 1.730 kcal, base 2.076 kcal, intervallo 1.868,4–2.283,6 kcal.
Con female: base 1.876,8 kcal. Cambiare target demo e bilancio lascia la
base identica. Pesate successive con rumore usano il filtro, non il peso
grezzo dell’ultimo giorno. Dati assenti: unavailable con tutti e soli i
campi mancanti; nessuna proposta viene salvata.

Regressioni: Salute valida ha precedenza; vecchie basi circolari approvate
rifiutate anche dal congiunto/rientro e dal caricamento del profilo; formule
approvate riusabili solo con input invariati, contesto e approvazione recenti.
Restano approva/rifiuta, CSRF, 409, transazione atomica e limiti nutrizionali.
La stima manuale esplicita resta compatibile, distinta dalla formula.

Campi facoltativi validati: height_cm 100–250; age_years 18–120;
sex male/female (coefficiente della formula); activity_factor 1–2,5.
Nessun aggiornamento di dati personali o di web/static/.
