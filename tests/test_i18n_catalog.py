"""Interface localisation (Italian / English): catalogues and no hard-coded texts.

The catalogues are `web/static/locales/it.js` and `en.js`; each assigns one flat
object to `I18N_MESSAGES.<lang>` (keys like "today.pending.title"). Texts use
`{name}` placeholders. Code reads them with `t(key, params)`; static HTML uses
`data-i18n="key"` for the text and `data-i18n-attr="attr:key;attr:key"` for
attributes.

MIGRATED lists the files already converted; later task cards extend it.
"""

import json
import re
import unittest
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / 'web' / 'static'
LOCALES = STATIC / 'locales'

MIGRATED = [
    'index.html',
    'app.js',
    'today.js',
    'pending.js',
    'checkin-review.js',
]

ITALIAN_WORDS = re.compile(
    r'\b(il|lo|gli|di|del|della|dei|delle|per|con|non|che|una|sono|nessun|nessuna|'
    r'giorno|giorni|pasto|pasti|conferma|confermati?|salva|annulla|oggi|ieri|domani|'
    r'settimana|errore|riprova|caricamento|allenamento|peso|colazione|pranzo|cena|'
    r'proteine|grassi|carboidrati|energia|esci|impostazioni|chiudi|apri|modifica|salta|'
    r'calcola|rivedi|progressi|piano|ricette|profilo|obiettivo|alimenti?|grammi|porzion[ei]|alternativ[aei]|schema|conf|porz|insufficiente|obsoleto|'
    r'nuov[aeio]|cosa|tua|tuo|tuoi|stima|rimpianto|serie|ripetizioni|recupero|scegli|cerca|aggiungi)\b',
    re.IGNORECASE,
)
ACCENTED = re.compile(r'[àèéìòùÀÈÉÌÒÙ]')
PLACEHOLDER = re.compile(r'\{(\w+)\}')
TEXT_ATTRS = ('placeholder', 'aria-label', 'title', 'alt')


def load_catalog(lang):
    source = (LOCALES / f'{lang}.js').read_text(encoding='utf-8')
    match = re.search(r'I18N_MESSAGES\.' + lang + r'\s*=\s*(\{.*\})\s*;?\s*$', source, re.S)
    if not match:
        raise AssertionError(f'{lang}.js must assign one object literal to I18N_MESSAGES.{lang}')
    return json.loads(match.group(1))


def js_literals(source):
    """Yield (line, text) for string literals and template text in JS source."""
    i, line, n = 0, 1, len(source)
    while i < n:
        c = source[i]
        if c == '\n':
            line += 1
            i += 1
        elif source.startswith('//', i):
            i = source.find('\n', i)
            i = n if i < 0 else i
        elif source.startswith('/*', i):
            end = source.find('*/', i + 2)
            end = n if end < 0 else end + 2
            line += source.count('\n', i, end)
            i = end
        elif c in '\'"`':
            start_line, i, buf, depth = line, i + 1, [], 0
            while i < n:
                ch = source[i]
                if ch == '\\':
                    buf.append(source[i:i + 2])
                    i += 2
                    continue
                if ch == '\n':
                    line += 1
                if c == '`' and source.startswith('${', i):
                    yield start_line, ''.join(buf)
                    buf, depth, i = [], 1, i + 2
                    while i < n and depth:
                        depth += {'{': 1, '}': -1}.get(source[i], 0)
                        line += source[i] == '\n'
                        i += 1
                    continue
                if ch == c:
                    i += 1
                    break
                buf.append(ch)
                i += 1
            yield start_line, ''.join(buf)
        else:
            i += 1


CSS_CLASSES = set(re.findall(r'\.([a-zA-Z][\w-]*)', (STATIC / 'style.css').read_text(encoding='utf-8')))
CSS_PREFIXES = {name[:name.index('-') + 1] for name in CSS_CLASSES if '-' in name}
CSS_PREFIXES |= {name[:name.rindex('-') + 1] for name in CSS_CLASSES if '-' in name}
UNITS = {'kcal', 'g', 'kg', 'min', 's', 'cm', 'ml', 'mg', 'µg', '%'}
CODE_WORDS = {'noopener', 'noreferrer', 'DOMContentLoaded', 'Enter', 'Escape', 'Tab', 'GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'Content-Type', 'X-CSRF-Token'}


def looks_italian(text):
    """True when a literal reads as interface text rather than code."""
    text = text.strip()
    if ACCENTED.search(text) or '…' in text:
        return True
    if not re.search(r'[A-Za-z]{2}', text) or text in CODE_WORDS:
        return False
    tokens = text.split()
    if len(tokens) > 1:
        # A list of CSS classes (or class prefixes like 'tone-') is code; anything else is prose.
        return not all(token in CSS_CLASSES or (token.endswith('-') and token in CSS_PREFIXES) or token in CODE_WORDS
                       for token in tokens)
    if text in UNITS:
        return False
    if ITALIAN_WORDS.fullmatch(text.strip('.,:;!?')) or any(ITALIAN_WORDS.fullmatch(p) for p in re.split(r'[/.]', text) if p):
        return True
    return bool(re.fullmatch(r'[A-Z][a-z]{2,}[.:!?]?', text))


class HtmlScan(HTMLParser):
    VOID = {'meta', 'link', 'input', 'img', 'br', 'hr', 'source'}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack, self.problems, self.keys = [], [], []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if attrs.get('data-i18n'):
            self.keys.append(attrs['data-i18n'])
        covered = set()
        for part in filter(None, (attrs.get('data-i18n-attr') or '').split(';')):
            name, _, key = part.partition(':')
            covered.add(name.strip())
            self.keys.append(key.strip())
        for name in TEXT_ATTRS:
            value = attrs.get(name)
            if value and name not in covered and looks_italian(value):
                self.problems.append(f'line {self.getpos()[0]}: <{tag} {name}="{value}">')
        if tag not in self.VOID:
            self.stack.append((tag, bool(attrs.get('data-i18n'))))

    def handle_endtag(self, tag):
        while self.stack:
            if self.stack.pop()[0] == tag:
                break

    def handle_data(self, data):
        text = data.strip()
        if not text or not self.stack or self.stack[-1][0] in ('script', 'style', 'title'):
            return
        if not self.stack[-1][1] and looks_italian(text):
            self.problems.append(f'line {self.getpos()[0]}: text "{text[:60]}"')


class CatalogTest(unittest.TestCase):
    def test_both_catalogues_have_the_same_keys(self):
        it, en = load_catalog('it'), load_catalog('en')
        self.assertEqual(sorted(set(it) - set(en)), [], 'missing in en.js')
        self.assertEqual(sorted(set(en) - set(it)), [], 'missing in it.js')

    def test_values_are_non_empty_strings_with_matching_placeholders(self):
        it, en = load_catalog('it'), load_catalog('en')
        for key in it:
            with self.subTest(key=key):
                self.assertIsInstance(it[key], str)
                self.assertIsInstance(en[key], str)
                self.assertTrue(it[key].strip() and en[key].strip())
                self.assertEqual(set(PLACEHOLDER.findall(it[key])), set(PLACEHOLDER.findall(en[key])))

    def test_english_catalogue_is_not_a_copy_of_the_italian_one(self):
        it, en = load_catalog('it'), load_catalog('en')
        italian_in_en = [k for k, v in en.items() if ACCENTED.search(v)]
        self.assertEqual(italian_in_en, [])
        same = [k for k in it if it[k] == en[k] and looks_italian(it[k])]
        self.assertEqual(same, [])

    def test_i18n_runtime_is_loaded_before_the_modules(self):
        html = (STATIC / 'index.html').read_text(encoding='utf-8')
        scripts = re.findall(r'<script src="/static/([^"]+)"', html)
        self.assertIn('i18n.js', scripts)
        self.assertIn('locales/it.js', scripts)
        self.assertIn('locales/en.js', scripts)
        first_module = scripts.index('app.js')
        for name in ('locales/it.js', 'locales/en.js', 'i18n.js'):
            self.assertLess(scripts.index(name), first_module, name)


class NoHardCodedTextTest(unittest.TestCase):
    def test_static_html_texts_use_data_i18n(self):
        scan = HtmlScan()
        scan.feed((STATIC / 'index.html').read_text(encoding='utf-8'))
        self.assertEqual(scan.problems, [])

    def test_migrated_scripts_have_no_italian_literals(self):
        for name in MIGRATED:
            if not name.endswith('.js'):
                continue
            with self.subTest(file=name):
                source = (STATIC / name).read_text(encoding='utf-8')
                found = [f'{name}:{line}: {text[:70]!r}' for line, text in js_literals(source) if looks_italian(text)]
                self.assertEqual(found, [])

    def test_migrated_scripts_do_not_hard_code_the_italian_locale(self):
        for name in MIGRATED:
            if name.endswith('.js'):
                with self.subTest(file=name):
                    self.assertNotIn("'it-IT'", (STATIC / name).read_text(encoding='utf-8'))

    def test_every_used_key_exists(self):
        catalog = load_catalog('it')
        scan = HtmlScan()
        scan.feed((STATIC / 'index.html').read_text(encoding='utf-8'))
        used = set(scan.keys)
        for path in STATIC.glob('*.js'):
            used |= set(re.findall(r"\bt\(\s*'([\w.\-]+)'", path.read_text(encoding='utf-8')))
        self.assertEqual(sorted(used - set(catalog)), [])


class ScannerSelfTest(unittest.TestCase):
    def test_scanner_finds_italian_and_ignores_code(self):
        source = "x('Hai 3 pasti da confermare'); y('lunch'); z(`Pranzo ${n}`); // Conferma\nw('day-head')"
        found = [text for _, text in js_literals(source) if looks_italian(text)]
        self.assertEqual(found, ['Hai 3 pasti da confermare', 'Pranzo '])

    def test_html_scan_accepts_marked_elements(self):
        scan = HtmlScan()
        scan.feed('<p data-i18n="a.b">Ciao a tutti di</p><button aria-label="Chiudi">x</button><span>Esci</span>')
        self.assertEqual(len(scan.problems), 2)
        self.assertEqual(scan.keys, ['a.b'])


if __name__ == '__main__':
    unittest.main()
