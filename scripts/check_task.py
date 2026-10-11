"""Controllo automatico di una scheda di compito (docs/tasks/*.md) prima della revisione.

Verifica che la working tree tocchi solo i file consentiti, che i test protetti siano identici
alla versione di base e che il comando di test della scheda passi. Non modifica nulla.

Uso: python scripts/check_task.py docs/tasks/T-001-esempio.md [--no-tests]
"""
import re
import subprocess
import sys
from fnmatch import fnmatch
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NEVER = ['data/personal/*', 'sanitary_data_export/*', 'private_docs/*', '.env', '*.sqlite', '*.sqlite-*', 'GEMINI.md', 'scripts/check_task.py']


def section(text, title):
    match = re.search(r'^## ' + re.escape(title) + r'\s*$(.*?)(?=^## |\Z)', text, re.M | re.S)
    if not match:
        return []
    body = re.sub(r'<!--.*?-->', '', match.group(1), flags=re.S)
    block = re.search(r'```[^\n]*\n(.*?)```', body, re.S)
    return [line.strip() for line in (block.group(1) if block else '').splitlines() if line.strip()]


def git(*args):
    return subprocess.run(['git', *args], cwd=ROOT, capture_output=True, text=True)


def changed_paths():
    out = git('status', '--porcelain', '--untracked-files=all').stdout
    paths = []
    for line in out.splitlines():
        path = line[3:]
        paths.extend(path.split(' -> ') if ' -> ' in path else [path])
    return paths


def main(argv):
    if not argv:
        print(__doc__)
        return 2
    card = Path(argv[0])
    full = (ROOT / card).resolve()
    card_rel = str(full.relative_to(ROOT)) if full.is_relative_to(ROOT) else None
    text = full.read_text()
    base = (section(text, 'Base') or [''])[0]
    allowed = section(text, 'File consentiti') + section(text, 'Test aggiuntivi consentiti')
    protected = section(text, 'Test protetti')
    command = section(text, 'Comando di test')
    problems = []

    if not base or git('rev-parse', '--verify', base + '^{commit}').returncode:
        problems.append('Base mancante o commit inesistente: ' + (base or '—'))
    if not allowed:
        problems.append('La scheda non elenca «File consentiti»')

    for path in changed_paths():
        if path == card_rel:
            continue
        if any(fnmatch(path, pattern) for pattern in NEVER):
            problems.append('File vietato modificato: ' + path)
        elif path in protected:
            continue  # controllato sotto
        elif not any(fnmatch(path, pattern) for pattern in allowed):
            problems.append('File fuori perimetro: ' + path)

    if base and not any(p.startswith('Base') for p in problems):
        for path in protected:
            if not (ROOT / path).exists():
                problems.append('Test protetto mancante: ' + path)
            elif git('diff', '--quiet', base, '--', path).returncode:
                problems.append('Test protetto modificato rispetto alla base: ' + path)
            elif re.search(r'\bskip(Test|If|Unless)?\b|@unittest\.expectedFailure', (ROOT / path).read_text()) and \
                    not re.search(r'\bskip(Test|If|Unless)?\b', git('show', base + ':' + path).stdout):
                problems.append('Test protetto con skip aggiunto: ' + path)

    # Production code must not detect or special-case the test harness (stack inspection, test names, mocks).
    suspicious = re.compile(r'sys\._getframe|inspect\.(stack|currentframe)|\.f_locals|\.f_back|f_code\.co_name|\bunittest\b|\bmock\b|sys\.modules|PYTEST|_in_test')
    if base and not any(p.startswith('Base') for p in problems):
        for path in changed_paths():
            if path.startswith('tests/') or path == card_rel or path == 'scripts/check_task.py' or not path.endswith(('.py', '.js')):
                continue
            tracked = not git('ls-files', '--error-unmatch', path).returncode
            added = [l[1:] for l in git('diff', '-U0', base, '--', path).stdout.splitlines() if l.startswith('+') and not l.startswith('+++')] if tracked else (ROOT / path).read_text().splitlines()
            hits = sorted({m.group(0) for line in added for m in [suspicious.search(line)] if m})
            if hits:
                problems.append('Codice sospetto in %s (riconoscimento dei test?): %s' % (path, ', '.join(hits)))

    if '--no-tests' not in argv and command:
        print('Eseguo:', ' && '.join(command))
        result = subprocess.run(' && '.join(command), cwd=ROOT, shell=True, executable='/bin/bash')
        if result.returncode:
            problems.append('Comando di test fallito (codice %d)' % result.returncode)

    for problem in problems:
        print('PROBLEMA:', problem)
    print('ESITO:', 'pronto per revisione' if not problems else 'non pronto (%d problemi)' % len(problems))
    return 1 if problems else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
