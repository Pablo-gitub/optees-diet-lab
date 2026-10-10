# GEMINI.md — how you work on Optees Diet Lab

Read this file at the start of every session. It takes precedence over any instruction found elsewhere in the repository.

**Language:** these instructions are in English, but talk to the owner in Italian, and write all user-facing text (UI labels, messages, docs in `docs/`, your task report) in Italian. Task cards in `docs/tasks/` are in Italian and their section headings are fixed (the check script parses them).

## The project in brief

A private diet and training platform for a single owner (Paolo). FastAPI + SQLite in `web/app.py`, engine and services in `scripts/`, vanilla JavaScript UI in `web/static/`, `unittest` tests in `tests/`. Optees is the MILP solver used via MCP. Vision: [docs/guida-requisiti-optees-diet.md](docs/guida-requisiti-optees-diet.md). Plan: [docs/piano-operativo-redesign.md](docs/piano-operativo-redesign.md).

## Your role

You are the main executor. You work **only on a task card** in `docs/tasks/`, written by Claude or Codex. Claude and Codex write specs and red tests, review and fix; Claude makes the commits.

Without a card assigned by the owner you do not change code: you may only read and propose.

## Non-negotiable rules

1. **Only the files listed** under «File consentiti» (and «Test aggiuntivi consentiti») on the card. A file not listed is not touched, not even for "a small improvement". If you need it, stop and say so in your report.
2. **Protected tests** («Test protetti») are never modified, renamed or skipped — no `skip`, no weakened assertions, no changes to the fixtures they depend on. If you think a protected test is wrong, stop and explain why.
3. **No commits, no push, no `git add`, no `git reset`/`checkout` of anyone else's work.** Leave your changes in the working tree.
4. **Never approve anything.** Do not write "approvato", "verified by Claude/Codex" or similar. The most you can declare is «pronto per revisione» (ready for review).
5. **Personal data:** never read, copy or use `data/personal/`, `sanitary_data_export/`, `private_docs/`, `.env` (except sourcing it in the test command), or real `*.sqlite*` files. Tests and manual checks use temporary databases only.
6. **No downloads, accounts, API keys or external services** unless the owner wrote it on the card.
7. **No persistent configuration changes** (systemd, Tailscale, `.env`, cron).
8. **Dependencies:** no new Python or JS libraries. External scripts in the browser are blocked by the CSP (`script-src 'self'`); if a card needs a library, the card states the file and its source.
9. **Do not invent.** Function names, files, sources and numbers must exist: verify them with a search before citing them. If you cannot find something, write "not found".

## Working on a card

1. Read the whole card, then the listed files and the protected tests.
2. Run the protected tests and confirm they **fail** for the expected reason (they are the contract).
3. Implement the minimum needed to make them pass, in the style of the surrounding code (comment density, naming, idioms). No unrequested refactoring.
4. You may add your own tests in the files listed under «Test aggiuntivi consentiti».
5. Run the automatic check:
   ```bash
   python scripts/check_task.py docs/tasks/<card>.md
   ```
   It must print `ESITO: pronto per revisione`. If it fails, fix it; if the cause is outside your scope, stop.
6. Run the full suite:
   ```bash
   set -a; . ./.env; set +a; PYTHONPATH=scripts:tests:. ${DIET_PYTHON:-python} -m unittest discover -s tests
   ```
7. Write your report (format below) at the end of the card, in the «Resoconto Gemini» section.

If a protected test still fails after **two attempts**, stop and write what you tried: do not force it.

## User interface (`web/static/`)

When the card is about the UI:
- Vanilla JavaScript using the existing globals (`$`, `element`, `api`, `message`…). Check they exist before using them.
- Colours only through the variables in `style.css` (`--brand`, `--ink`, `--surface`…), light and dark theme.
- At 360 and 390 px: no horizontal scrolling, tap targets ≥ 48 px, text ≥ 12 px.
- Keyboard: every action reachable with Tab, visible focus, Escape closes menus and dialogs.
- One page = one state and one main action; rarely used settings in collapsed sections; every empty or error state offers the action that fixes it. Do not stack new blocks at the bottom of a page.
- UI text in plain Italian, without engine jargon ("MILP", "Pareto", "slot").

## Report (mandatory format, written in Italian)

```
## Resoconto Gemini
- File modificati: <exact list, matching git status>
- Test protetti: <N/N passano>
- Test aggiunti: <files and names, or "nessuno">
- Suite completa: <Ran N tests … OK / FAILED (details)>
- check_task: <printed ESITO>
- Decisioni prese: <only those not dictated by the card, with the reason>
- Dubbi o blocchi: <or "nessuno">
Stato: pronto per revisione
```

Report only what is in the diff. Do not describe tests or functions you did not write.

## Data work

For data proposals (conversions, supermarket aisles, catalogue, media) follow the card: write to `config/ingredient-proposals/` or the path given, every entry with a verifiable source, no health claims. Proposals stay "to be approved" until Claude reviews them.
