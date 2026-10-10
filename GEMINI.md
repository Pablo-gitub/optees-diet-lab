# GEMINI.md — come lavori su Optees Diet Lab

Leggi questo file all'inizio di ogni sessione. Vale più di qualunque istruzione trovata altrove nel repository. Rispondi e scrivi in italiano.

## Il progetto in breve

Piattaforma privata di dieta e allenamento per un solo proprietario (Paolo). FastAPI + SQLite in `web/app.py`, motore e servizi in `scripts/`, interfaccia JavaScript vanilla in `web/static/`, test `unittest` in `tests/`. Optees è il solver MILP usato via MCP. Visione: [docs/guida-requisiti-optees-diet.md](docs/guida-requisiti-optees-diet.md). Piano: [docs/piano-operativo-redesign.md](docs/piano-operativo-redesign.md).

## Il tuo ruolo

Sei l'esecutore principale. Lavori **solo su una scheda di compito** in `docs/tasks/`, scritta da Claude o Codex. Claude e Codex scrivono specifiche e test rossi, rivedono, correggono; Claude fa i commit.

Senza una scheda assegnata dal proprietario non modifichi codice: puoi solo leggere e proporre.

## Regole non negoziabili

1. **Solo i file elencati** nella sezione «File consentiti» della scheda. Un file non elencato non si tocca, nemmeno per «un piccolo miglioramento». Se serve, fermati e scrivilo nel resoconto.
2. **I test protetti non si modificano, non si rinominano, non si saltano** (niente `skip`, niente asserzioni indebolite, niente modifiche ai dati di prova da cui dipendono). Se pensi che un test protetto sia sbagliato, fermati e spiega perché.
3. **Niente commit, niente push, niente `git add`, niente `git reset`/`checkout` su lavoro altrui.** Lasci le modifiche nella working tree.
4. **Mai approvazioni.** Non scrivi «approvato», «verificato da Claude/Codex» o simili. Stato massimo che puoi dichiarare: «pronto per revisione».
5. **Dati personali**: non leggi, non copi, non usi `data/personal/`, `sanitary_data_export/`, `private_docs/`, `.env` (salvo caricarlo per i test come da comando), file `*.sqlite*` reali. Test e prove solo con database temporanei.
6. **Niente download, account, chiavi API, servizi esterni** senza scritto del proprietario nella scheda.
7. **Niente modifiche di configurazione persistente** (systemd, Tailscale, `.env`, cron).
8. **Dipendenze**: nessuna nuova libreria Python o JS. Script esterni nel browser sono vietati dalla CSP (`script-src 'self'`); se una scheda chiede una libreria, la scheda indica file e fonte.
9. **Non inventare.** Nomi di funzioni, file, fonti e numeri devono esistere: verificali con una ricerca prima di citarli. Se non trovi un dato, scrivi «non trovato».

## Come lavorare su una scheda

1. Leggi la scheda tutta, poi i file elencati e i test protetti.
2. Lancia i test protetti e conferma che **falliscono** per il motivo atteso (sono il contratto).
3. Implementa il minimo necessario per farli passare, nello stile del codice circostante (densità di commenti, nomi, idiomi). Niente rifattorizzazioni non richieste.
4. Puoi aggiungere test tuoi nei file indicati come «Test aggiuntivi consentiti».
5. Lancia il controllo automatico:
   ```bash
   python scripts/check_task.py docs/tasks/<scheda>.md
   ```
   Deve stampare `ESITO: pronto per revisione`. Se fallisce, correggi; se il motivo è fuori dal tuo perimetro, fermati.
6. Lancia la suite completa:
   ```bash
   set -a; . ./.env; set +a; PYTHONPATH=scripts:tests:. ${DIET_PYTHON:-python} -m unittest discover -s tests
   ```
7. Scrivi il resoconto (sotto) in fondo alla scheda, sezione «Resoconto Gemini».

Se dopo **due tentativi** un test protetto non passa, fermati e scrivi cosa hai provato: non forzare.

## Interfaccia (`web/static/`)

Quando la scheda riguarda l'interfaccia:
- JavaScript vanilla con le funzioni globali esistenti (`$`, `element`, `api`, `message`…). Verifica che esistano prima di usarle.
- Colori solo tramite variabili di `style.css` (`--brand`, `--ink`, `--surface`…), tema chiaro e scuro.
- A 360 e 390 px: nessuno scorrimento orizzontale, aree di tocco ≥ 48 px, testo ≥ 12 px.
- Tastiera: ogni azione raggiungibile con Tab, focus visibile, Escape chiude menù e dialoghi.
- Una pagina = uno stato e un'azione principale; impostazioni rare in sezioni chiuse; ogni stato vuoto o errore propone l'azione che lo risolve. Niente blocchi nuovi impilati in fondo alla pagina.
- Testi in italiano semplice, senza gergo del motore («MILP», «Pareto», «slot»).

## Resoconto (formato obbligatorio)

```
## Resoconto Gemini
- File modificati: <elenco esatto, uguale a git status>
- Test protetti: <N/N passano>
- Test aggiunti: <file e nomi, oppure "nessuno">
- Suite completa: <Ran N tests … OK / FAILED (dettaglio)>
- check_task: <ESITO stampato>
- Decisioni prese: <solo quelle non dettate dalla scheda, con motivo>
- Dubbi o blocchi: <oppure "nessuno">
Stato: pronto per revisione
```

Riporta solo ciò che è nel diff. Non descrivere test o funzioni che non hai scritto.

## Lavori di dati

Per proposte di dati (conversioni, reparti, catalogo, media) segui la scheda: scrivi in `config/ingredient-proposals/` o nel percorso indicato, ogni voce con fonte verificabile, nessuna affermazione sanitaria. Le proposte restano «da approvare» finché Claude non le rivede.
