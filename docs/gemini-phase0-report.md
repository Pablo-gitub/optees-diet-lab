# Rapporto Fase 0 (Passi 0.3 · 0.4 · 0.5) — Media, Ricette e Titoli Italiani

Data di completamento: 2026-10-04  
Operatore: Gemini  
Ambiente Python: `/home/paolo/anaconda3/envs/optees/bin/python`  
Repository: `optees_diet_case_of_studi`  
Stato Git: Modifiche non committate nel working directory (pronte per la revisione di Claude nel Turno T3).

---

## 1. Sintesi dei Risultati e Conteggi Effettivi

| Ambito | Obiettivo da Piano | Risultato Conseguito | Stato | File Interessati |
|---|---|---|---|---|
| **0.3 Media Esercizi** | 10 esercizi da `config/workout-protocols.json` mappati su Free Exercise DB, 2 foto ciascuno in locale, max 2 video didattici YouTube, correzione Commons | 10 esercizi mappati su 10 ID Free Exercise DB; 20 foto locali (2 per esercizio) in `web/static/media/exercises/<id>/`; 2 video didattici verificati per esercizio | **COMPLETATO** | `config/exercise-media.json`<br>`web/static/media/exercises/` |
| **0.4 Foto Ricette** | Copertura ≥ 100 ricette, priorità alle 81 italiane e 25 del solver; sostituzione foto errate (risotto alla milanese puro, senza ossobuco); licenze aperte e attribuzioni complete | **142 ricette** con immagini illustrative convalidate e controllate a vista da Wikimedia Commons; risotto alla milanese sostituito con foto di puro risotto allo zafferano (Number55, CC BY-SA 3.0) | **COMPLETATO** | `config/recipe-images.json` |
| **0.5 Titoli in Italiano** | Overlay JSON versionato con tutti gli 834 ID del catalogo (`dataset/recipes/catalog.sqlite`), traduzione fedele, conservazione nomi propri e identità culinaria | **834 / 834 ricette coperte** (corrispondenza 1-a-1 esatta con il database SQLite) | **COMPLETATO** | `config/recipe-titles-it.json` |

---

## 2. Dettaglio Passo 0.3 — Media Esercizi

### 2.1 Mappatura degli Esercizi
I 10 esercizi definiti nelle sessioni di `config/workout-protocols.json` sono stati associati agli identificativi di `dataset/free_exercise_db/exercises.json`:

1. `push-up` → `Pushups`
2. `bodyweight-squat` → `Bodyweight_Squat`
3. `dumbbell-floor-press` → `Dumbbell_Floor_Press`
4. `dumbbell-deadlift` → `Stiff-Legged_Dumbbell_Deadlift` *(variante a gambe tese/rumena con manubri, vedi anomalie)*
5. `plank` → `Plank`
6. `inverted-row` → `Inverted_Row`
7. `stationary-bike` → `Bicycling_Stationary`
8. `rowing-machine` → `Rowing_Stationary`
9. `incline-treadmill-walk` → `Walking_Treadmill` *(camminata su tapis roulant, vedi anomalie)*
10. `elliptical-trainer` → `Elliptical_Trainer`

### 2.2 Immagini Locali e Controllo Visivo
- Le 20 immagini sorgente (formato `.jpg`, risoluzione originale, pubblico dominio / The Unlicense) sono state scaricate e collocate nelle rispettive directory `web/static/media/exercises/<id>/0.jpg` e `1.jpg`.
- **Verifica visiva**: Tutte le 20 immagini sono state ispezionate visivamente tramite tool di rendering immagini. Le precedenti associazioni errate di Wikimedia Commons (es. "Handstand pushup" per i piegamenti e "squat thrust / burpee" per lo squat a corpo libero) sono state completamente eliminate e sostituite con le foto corrette delle due fasi del movimento (partenza ed estensione/esecuzione).
- In `config/exercise-media.json` i percorsi puntano ora a `/static/media/exercises/<id>/0.jpg` e `/static/media/exercises/<id>/1.jpg`.

### 2.3 Curatela dei Video YouTube
Sono stati selezionati rigorosamente 2 video per esercizio da canali didattici certificati e riconosciuti (Calisthenicmovement, Concept2, BarBend, Sunny Health & Fitness, Scott Herman Fitness, Live Lean TV, Criticalbench, Bowflex). Sono stati esclusi categoricamente shorts, reel verticali e titoli clickbait o sensazionalistici.

### 2.4 Anomalie e Lacune Documentate (0.3)
- `dumbbell-deadlift`: Free Exercise DB non dispone di uno stacco da terra convenzionale da pavimento con manubri ("conventional dumbbell deadlift"), ma dello stacco a gambe tese / rumeno (`Stiff-Legged_Dumbbell_Deadlift`). Il pattern di cerniera d'anca è coerente ma l'escursione sul ginocchio è ridotta rispetto a uno stacco convenzionale.
- `incline-treadmill-walk`: Nel dataset le immagini mostrano il nastro del tapis roulant in piano (`Walking_Treadmill`), anche se il testo descrittivo menziona la possibilità di regolare l'inclinazione. Documentata la discrepanza visiva rispetto alla variante "incline".

---

## 3. Dettaglio Passo 0.4 — Foto Ricette

### 3.1 Estensione della Copertura (142 ricette)
- `config/recipe-images.json` è stato espanso da 4 a **142 ricette**.
- Include tutte le ricette italiane di rilievo (carbonara, amatriciana, lasagne alla bolognese, parmigiana di melanzane, ossobuco, trofie al pesto, pizza margherita, tiramisù, ecc.), le ricette del solver (pasta al pomodoro demo, panino caprese, parmigiana, caponata, cotoletta, frittelle di baccalà, gnocchi al pomodoro, minestrone, mujadara, falafel, ecc.) e le ricette tradizionali internazionali più note di `unitools` (ratatouille, soupe à l'oignon, paella valenciana, moussaka, gazpacho, quiche lorraine, boeuf bourguignon, borscht, goulash, pierogi, hummus, sushi/ramen, pad thai, ecc.).

### 3.2 Sostituzione Risotto alla Milanese
- La foto precedentemente associata (`File:Ossobuco con risotto alla milanese.jpg`), che conteneva in primo piano un ossobuco con carne, è stata **rimossa**.
- È stata sostituita con l'immagine autentica di puro risotto alla milanese allo zafferano:
  - **File**: `File:Risotto alla Milanese.JPG`
  - **Autore**: Number55 (`https://commons.wikimedia.org/wiki/User:Number55`)
  - **Licenza**: CC BY-SA 3.0 (`https://creativecommons.org/licenses/by-sa/3.0/`)
  - **Controllo visivo**: confermata la presenza esclusiva del risotto giallo allo zafferano mantecato sul piatto, senza tagli di carne o ossobuco.

### 3.3 Sostituzione Panino Caprese e Bonifica Anomalie
- L'URL di `foodose:R315` è stato aggiornato all'immagine attiva e convalidata `File:Caprese Sandwich at Mobtown Ballroom.jpg` (autore Sdkb, licenza CC BY-SA 4.0).
- Le immagini generate dalla ricerca che includevano dipinti o ritratti (es. ritratto storico per Margherita o attrezzi per waffle) sono state rimosse e sostituite con autentiche fotografie di cibo su piatto.

---

## 4. Dettaglio Passo 0.5 — Titoli Italiani

### 4.1 Overlay Versionato (`config/recipe-titles-it.json`)
È stato creato il file di overlay `config/recipe-titles-it.json` con la struttura richiesta:
```json
{
  "version": "1.0",
  "source": "dataset/recipes/catalog.sqlite",
  "count": 834,
  "titles": {
    "demo:pasta-pomodoro": "...",
    ...
  }
}
```

### 4.2 Criteri di Traduzione e Copertura
- **Copertura totale**: 834 chiavi su 834 ID presenti in `dataset/recipes/catalog.sqlite` (333 ricette `foodose`, 501 ricette `unitools`).
- **Conservazione dei nomi propri**: Piatti tradizionali ed etnici hanno mantenuto il loro nome originale e intoccato (es. *Ackee and saltfish*, *Tom yum goong*, *Borscht*, *Khachapuri*, *Mantu*, *Pad thai*, *Shakshuka*, *Bacalhau à brás*, *Feijoada*).
- **Traduzione fedele**: Le 333 ricette descrittive di `foodose` e le ricette `unitools` con titoli composti in inglese sono state tradotte con precisione culinaria in italiano (es. *"Lemon-ricotta pancakes with warm blueberries"* → *"Pancake alla ricotta e limone con mirtilli caldi"*; *"Turkey meatballs with roasted pepper sauce"* → *"Polpette di tacchino con salsa di peperoni arrostiti"*).
- Nessun dato nutrizionale, ingrediente o peso nel catalogo originale è stato modificato o toccato.

---

## 5. Elenco dei File Modificati e Aggiunti

1. `config/exercise-media.json` (modificato): aggiornati URL locali, licenze Unlicense, 2 video YouTube curati per ciascuno dei 10 esercizi.
2. `config/recipe-images.json` (modificato): espanso a 142 ricette, corretto il risotto alla milanese (Number55) e il panino caprese.
3. `config/recipe-titles-it.json` (nuovo): overlay di traduzione italiana per tutte le 834 ricette.
4. `web/static/media/exercises/` (nuova directory con 10 sottocartelle e 20 immagini `.jpg`).
5. `docs/gemini-phase0-report.md` (questo documento).

---

## 6. Verifica dei Test Automatizzati

Comando eseguito:
```bash
/home/paolo/anaconda3/envs/optees/bin/python -m unittest discover tests
```

Esito:
```text
Ran 126 tests in 3.182s

OK
```
Tutti i 126 test del repository risultano verdi, inclusi:
- `tests/test_exercise_media.py` (7 test specifici per i media esercizi: schema, percorsi locali, licenze, disclaimer, fallback).
- `tests/test_recipe_images.py` (pulizia titoli, parsing MediaWiki, attribuzioni e integrazione FastAPI).
- `tests/test_recipe_solver.py` e suite completa dell'engine.
