# Consegna a Gemini: passi 0.3–0.5

Lavora nel repository `optees_diet_case_of_studi`. Leggi `docs/development-plan.md`, in particolare 0.3, 0.4 e 0.5. Codex chiude 0.1 e 0.2 e proseguirà sull'engine; mantieni disgiunte le modifiche.

Puoi modificare `config/exercise-media.json`, `config/recipe-images.json`, aggiungere un overlay `config/recipe-titles-it.json`, salvare immagini in `web/static/media/exercises/` e scrivere il rapporto in `docs/gemini-phase0-report.md`. Non modificare engine, API, test esistenti, JavaScript/CSS/HTML, cataloghi originali o dati personali. Segnala eventuali altri file necessari prima di modificarli.

## 0.3 — Esercizi

Trova gli esercizi usati in `config/workout-protocols.json`, incluse le sessioni e i riferimenti al catalogo. Associali agli identificativi di `dataset/free_exercise_db/exercises.json`. Scarica soltanto le due immagini pertinenti per ciascun esercizio in `web/static/media/exercises/<id>/`. Verifica licenza e provenienza, mantieni il formato consumato dall'applicazione e usa URL locali `/static/media/exercises/...`.

Controlla visivamente ogni immagine: attrezzo, movimento e variante devono corrispondere. Correggi gli abbinamenti Commons errati. Se manca una variante corretta, dichiarala senza sostituirla con un altro movimento. Conserva al massimo due video YouTube per esercizio, da canali didattici riconoscibili; escludi shorts e titoli clickbait.

## 0.4 — Ricette

Estendi le immagini ad almeno 100 ricette, dando precedenza alle 81 italiane e alle 25 composizioni del solver. Identifica gli ID reali nei cataloghi e mantieni lo schema attuale di `config/recipe-images.json`.

Usa foto Wikimedia Commons con licenza libera e attribuzione completa: autore, pagina sorgente, URL immagine, licenza e relativo collegamento. Guarda ogni foto per verificare che rappresenti il piatto indicato; non approvare sulla sola base del nome. Se non trovi una foto corretta, documenta la lacuna. Non inventare attribuzioni o raggiungimento della copertura.

## 0.5 — Titoli italiani

Crea un overlay JSON versionato con `version`, `source` e `titles` (oggetto: ID ricetta → titolo italiano). Copri tutti gli 834 ID realmente presenti; segnala variazioni del conteggio. Traduci fedelmente, conserva i nomi propri e non riscrivere ingredienti, quantità o dati nutrizionali. L'integrazione del fallback nell'interfaccia spetta a Claude.

## Verifica e consegna

Valida JSON, riferimenti agli ID e percorsi delle immagini. Produci un rapporto con conteggi effettivi, elenco dei file cambiati, anomalie e lacune, fonti/licenze e prova dei controlli visivi. Esegui i test previsti dal piano e riporta comando e risultato. Non includere dati personali in esempi o fixture.

Lascia le modifiche disponibili per la revisione di Claude prima del commit, come stabilito dal piano. Non segnare un passo completato se mancano verifiche o copertura richiesta.
