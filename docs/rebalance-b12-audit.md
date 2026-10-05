# Audit B12 — pizza media a cena

La segnalazione UI in frontend-handoff-t3-t5.md documenta **71 modifiche per 61 kcal** su un piano reale con scenari Salute sintetici. Quel piano temporaneo non è presente nel database disponibile: questi numeri sono l'osservazione di Claude, non una nuova misurazione sul medesimo snapshot.

Prova riproducibile: `tests/test_meal_rebalance.py`, sette giornate, lunedì 5 ottobre 2026, sei giorni futuri; pasta, pollo/pesce, spinaci e olio nei pasti principali, banana a colazione/spuntini. Anteprima senza scritture; stessa fixture prima e dopo.

| Caso | Prima della correzione | Dopo B12 |
|---|---|---|
| Scostamento esatto +61 kcal | Il vecchio solver non trova una soluzione per questa fixture: indisponibile, 0 correzione | 51,15 kcal recuperate; 3 pasti cambiati, solo grammi, 0 sostituzioni, colazione e spuntini identici |
| Preset pizzeria medio a cena | Segnalazione UI: 71 modifiche / 61 kcal, su altro piano | Fixture: cena prevista 662,3 kcal, preset 842–1020, scostamento 179,7–357,7; recupero 170,5 kcal, 6 pasti cambiati, solo grammi, 0 sostituzioni, nessuna pizza futura |

Il preset corrente v1.2 è un intervallo: il solver non può recuperare 357,7 kcal se il surplus garantito è 179,7. Il residuo resta 9,2–187,2 kcal (`partial`). Il diff esclude gli alimenti e i pasti invariati. È verificata anche l'esclusione delle pizze nel livello che permette sostituzioni, non soltanto nella soluzione con grammi.

Questi conteggi sono misurati con il solver MILP di test (SciPy); la suite include inoltre un'anteprima HTTP con Optees reale, controllo del database invariato e applicazione esplicita.
