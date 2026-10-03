"""Import public CREA food sheets, retaining original values and provenance."""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import time
from urllib.request import Request, urlopen

from bs4 import BeautifulSoup

BASE = 'https://www.alimentinutrizione.it'
ROOT = Path(__file__).resolve().parents[1] / 'dataset' / 'crea'
RAW = ROOT / 'raw'
MACROS = {
    'kcal_100g': 'Energia (kcal)',
    'protein_g_100g': 'Proteine (g)',
    'fat_g_100g': 'Lipidi (g)',
    'carbs_available_g_100g': 'Carboidrati disponibili (g)',
    'fiber_g_100g': 'Fibra totale (g)',
}


def number(value):
    value = value.strip().replace('\xa0', '').replace(',', '.')
    return float(value) if re.fullmatch(r'\d+(?:\.\d+)?', value) else None


def fetch(path, filename, offline):
    dest = RAW / filename
    if dest.exists():
        return dest.read_text(encoding='utf-8')
    if offline:
        raise FileNotFoundError(f'Cache missing: {filename}')
    for attempt in range(3):
        try:
            request = Request(BASE + path, headers={'User-Agent': 'OpteesDietPersonalStudy/0.1'})
            with urlopen(request, timeout=30) as response:
                html = response.read().decode('utf-8')
            tmp = dest.with_suffix('.tmp')
            tmp.write_text(html, encoding='utf-8')
            tmp.replace(dest)
            time.sleep(0.3)
            return html
        except Exception:
            if attempt == 2:
                raise
            time.sleep(2 ** attempt)


def parse_food(html, code):
    soup = BeautifulSoup(html, 'html.parser')
    top = soup.select_one('table.toptable')
    table = soup.select_one('table.tblmain')
    if top is None or table is None:
        raise ValueError('Food tables missing')
    title = top.select_one('h1')
    metadata = {}
    for row in top.select('tr'):
        cells = row.find_all('td', recursive=False)
        if len(cells) == 2:
            metadata[cells[0].get_text(' ', strip=True)] = cells[1].get_text(' ', strip=True)
    if metadata.get('Codice Alimento') != code:
        raise ValueError(f'Food ID mismatch: {metadata.get("Codice Alimento")} != {code}')
    nutrients = []
    group = None
    for row in table.select('tr'):
        cells = row.find_all('td', recursive=False)
        if not cells:
            headers = row.find_all('th', recursive=False)
            if len(headers) == 1:
                group = headers[0].get_text(' ', strip=True)
            continue
        if len(cells) != 9:
            raise ValueError(f'Unexpected nutrient row: {len(cells)} cells')
        values = [c.get_text(' ', strip=True) for c in cells]
        nutrients.append({
            'group': group, 'name': values[0], 'unit': values[1],
            'value_100g_raw': values[2], 'value_100g': number(values[2]),
            'min_raw': values[3], 'max_raw': values[4],
            'value_serving_raw': values[5], 'value_serving': number(values[5]),
            'origin': values[6], 'method': values[7],
            'references': [x['data-content'] for x in cells[8].select('[data-content]')],
        })
    if not nutrients or title is None:
        raise ValueError('Missing title or nutrients')
    food = {'source': 'CREA', 'source_id': code, 'name': title.get_text(' ', strip=True),
            'source_url': BASE + '/tabelle-nutrizionali/' + code,
            'metadata': metadata, 'nutrients': nutrients,
            'raw_sha256': hashlib.sha256(html.encode()).hexdigest()}
    by_name = {n['name']: n for n in nutrients}
    for field, label in MACROS.items():
        food[field] = by_name.get(label, {}).get('value_100g')
    return food


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--limit', type=int)
    parser.add_argument('--offline', action='store_true')
    args = parser.parse_args()
    if args.limit is not None and args.limit < 1:
        parser.error('--limit must be positive')
    RAW.mkdir(parents=True, exist_ok=True)
    index = fetch('/tabelle-nutrizionali/ricerca-per-ordine-alfabetico', 'index.html', args.offline)
    fetch('/tabelle-di-composizione-degli-alimenti', 'prefazione.html', args.offline)
    fetch('/simboli-abbreviazioni-sinonimi', 'legenda.html', args.offline)
    links = {}
    for a in BeautifulSoup(index, 'html.parser').select('a[href]'):
        match = re.fullmatch(r'/tabelle-nutrizionali/(\d+)', a['href'])
        if match:
            links[match[1]] = a['href']
    if not links:
        raise RuntimeError('No food links found')
    selected = list(links.items())[:args.limit]
    foods, errors = [], []

    def load(item):
        code, path = item
        return parse_food(fetch(path, code + '.html', args.offline), code)

    with ThreadPoolExecutor(max_workers=2) as executor:
        jobs = {executor.submit(load, item): item[0] for item in selected}
        for count, job in enumerate(as_completed(jobs), 1):
            try:
                foods.append(job.result())
            except Exception as exc:
                errors.append({'source_id': jobs[job], 'error': str(exc)})
            if count % 50 == 0 or count == len(selected):
                print(f'{count}/{len(selected)} sheets; errors={len(errors)}', flush=True)
    foods.sort(key=lambda f: f['source_id'])
    (ROOT / 'foods.json').write_text(json.dumps(foods, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    fields = ['source', 'source_id', 'name', 'category', 'serving_raw', 'edible_portion_raw', *MACROS, 'source_url']
    with (ROOT / 'foods.csv').open('w', newline='', encoding='utf-8') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for food in foods:
            row = {k: food[k] for k in fields if k in food}
            row.update(category=food['metadata'].get('Categoria'),
                       serving_raw=food['metadata'].get('Porzione'),
                       edible_portion_raw=food['metadata'].get('Parte Edibile'))
            writer.writerow(row)
    missing = {k: sum(f[k] is None for f in foods) for k in MACROS}
    essential = ('kcal_100g', 'protein_g_100g', 'fat_g_100g', 'carbs_available_g_100g')
    manifest = {
        'generated_at_utc': datetime.now(timezone.utc).isoformat(),
        'source': 'CREA Tabelle di composizione degli alimenti, aggiornamento 2019',
        'attribution': 'CREA Centro di ricerca Alimenti e Nutrizione; website L. Marletta e E. Camilli',
        'index_url': BASE + '/tabelle-nutrizionali/ricerca-per-ordine-alfabetico',
        'method': 'Derived from public HTML sheets; not an official CSV/JSON export',
        'foods_in_index': len(links), 'requested': len(selected), 'imported': len(foods),
        'complete': not errors and len(foods) == len(links), 'errors': errors,
        'missing_or_symbolic_macros': missing,
        'foods_with_numeric_essential_macros': sum(all(f[k] is not None for k in essential) for f in foods),
        'sha256': {n: hashlib.sha256((ROOT / n).read_bytes()).hexdigest() for n in ('foods.csv', 'foods.json')},
    }
    (ROOT / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({k: manifest[k] for k in ('foods_in_index', 'imported', 'complete', 'missing_or_symbolic_macros')}, ensure_ascii=False))
    if any(missing[k] for k in essential):
        print('Some macro values are symbolic or missing: inspect original values before optimization.')
    if errors:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
