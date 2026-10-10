# T-000 · Titolo breve

Autore della scheda: Claude | Codex · Data: AAAA-MM-GG · Tappa del piano: N
Esecutore: Gemini · Revisore: Claude (interfaccia) | Codex (backend)

## Obiettivo

Una frase: quale comportamento esiste alla fine che oggi non esiste.

## Contesto

Cosa c'è già (file, funzioni, endpoint esistenti con nome esatto) e perché serve.

## Contratto

Input, output, stati, messaggi. Per le API: metodo, percorso, corpo, risposta, errori.

## Criteri di accettazione

- [ ] Criterio verificabile 1
- [ ] Criterio verificabile 2

## Fuori perimetro

Cosa NON fare in questa scheda.

## Base

<!-- commit da cui partire: i test protetti sono confrontati con questa versione -->
```
abc1234
```

## File consentiti

```
web/static/esempio.js
```

## Test protetti

<!-- scritti da Claude/Codex; non modificabili da Gemini -->
```
tests/test_esempio.py
```

## Test aggiuntivi consentiti

```
tests/test_esempio_extra.py
```

## Comando di test

```
set -a; . ./.env; set +a; PYTHONPATH=scripts:tests:. ${DIET_PYTHON:-python} -m unittest test_esempio -q
```

## Riferimento visivo (solo interfaccia)

Schermata, prototipo o descrizione della disposizione.

## Resoconto Gemini

<!-- compilato da Gemini secondo GEMINI.md -->

## Revisione

<!-- compilata da Claude/Codex: esito, correzioni, commit -->
