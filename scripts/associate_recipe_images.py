"""Associate illustrative images from Wikimedia Commons to recipes.

Extracts recipe titles, queries Wikimedia Commons via MediaWiki API,
preserves author, source, and open license (CC BY / CC BY-SA / PD),
and attaches a disclaimer that the image is illustrative and may differ
in actual ingredients, weights, or yield. Operates offline by default,
requiring --online to query external APIs.
"""

import argparse
import html
import json
import re
import sqlite3
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RECIPES = ROOT / 'dataset/recipes/catalog.sqlite'
DEFAULT_IMAGES = ROOT / 'config/recipe-images.json'
COMMONS_API = 'https://commons.wikimedia.org/w/api.php'
USER_AGENT = 'OpteesDietRecipeImageBot/1.0 (educational case study; mailto:info@example.com)'

DISCLAIMER = 'Immagine a scopo illustrativo: ingredienti, quantità e porzioni possono differire dalla ricetta specifica.'


def clean_title_for_search(title: str) -> str:
    """Prepare a clean search query from a recipe title."""
    if not title:
        return ''
    # Remove leading/trailing symbols, quotes, parentheses content
    t = re.sub(r'\(.*?\)', '', title)
    t = re.sub(r'\[.*?\]', '', t)
    t = t.replace('·', ' ').replace('-', ' ').replace('_', ' ')
    t = re.sub(r'\s+', ' ', t).strip()
    return t


def strip_html(text: str) -> tuple:
    """Extract plain text and first href URL from an HTML fragment."""
    if not text:
        return '', None
    url_match = re.search(r'href=[\'"]([^\'"]+)[\'"]', text)
    first_url = html.unescape(url_match.group(1)) if url_match else None
    if first_url and first_url.startswith('//'):
        first_url = 'https:' + first_url
    clean = re.sub(r'<[^>]+>', '', text)
    clean = html.unescape(clean).strip()
    return clean, first_url


def parse_imageinfo(page: dict, search_term: str, recipe_id: str, recipe_title: str) -> dict:
    """Parse MediaWiki imageinfo structure into a standardized image metadata record."""
    imageinfo = page.get('imageinfo', [])
    if not imageinfo:
        return None

    info = imageinfo[0]
    mime = info.get('mime', '').lower()
    if mime not in ['image/jpeg', 'image/png', 'image/webp']:
        return None

    title = page.get('title', '')
    lower_title = title.lower()
    # Skip icons, maps, flags, logos, diagrams
    for skip in ['icon', 'logo', 'flag', 'map', 'diagram', 'coat of arms', 'symbol']:
        if skip in lower_title:
            return None

    extmeta = info.get('extmetadata', {})
    artist_raw = extmeta.get('Artist', {}).get('value', '')
    author, author_url = strip_html(artist_raw)
    if not author:
        author = extmeta.get('Credit', {}).get('value', 'Wikimedia Commons contributor')
        author, _ = strip_html(author)

    license_short = extmeta.get('LicenseShortName', {}).get('value') or extmeta.get('UsageTerms', {}).get('value') or 'CC-BY-SA'
    license_url = extmeta.get('LicenseUrl', {}).get('value')
    if not license_url and 'cc' in license_short.lower():
        license_url = 'https://creativecommons.org/licenses/'

    source_page = info.get('descriptionurl', f"https://commons.wikimedia.org/wiki/{urllib.parse.quote(title.replace(' ', '_'))}")
    image_url = info.get('url')
    thumb_url = info.get('thumburl') or image_url

    return {
        'recipe_id': recipe_id,
        'recipe_title': recipe_title,
        'search_term': search_term,
        'image_url': image_url,
        'thumbnail_url': thumb_url,
        'title': title,
        'author': author,
        'author_url': author_url,
        'license': license_short,
        'license_url': license_url,
        'source': 'Wikimedia Commons',
        'source_page': source_page,
        'illustrative': True,
        'disclaimer': DISCLAIMER
    }


def query_commons_api(search_term: str, timeout: int = 10) -> list:
    """Execute MediaWiki search query on Wikimedia Commons."""
    params = {
        'action': 'query',
        'generator': 'search',
        'gsrnamespace': '6',  # File: namespace
        'gsrsearch': search_term,
        'gsrlimit': '8',
        'prop': 'imageinfo',
        'iiprop': 'url|size|extmetadata|mime',
        'iiurlwidth': '640',
        'format': 'json'
    }
    url = f"{COMMONS_API}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={'User-Agent': USER_AGENT})

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            pages = data.get('query', {}).get('pages', {})
            return list(pages.values())
    except Exception as e:
        print(f"Errore nella ricerca Wikimedia Commons per '{search_term}': {e}")
        return []


def load_images_index(images_path: Path) -> dict:
    """Load existing images index JSON."""
    if not images_path.exists():
        return {'version': '1.0', 'images': {}}
    return json.loads(images_path.read_text(encoding='utf-8'))


def save_images_index(data: dict, images_path: Path):
    """Save updated images index JSON."""
    images_path.parent.mkdir(parents=True, exist_ok=True)
    images_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def associate_images(recipes_db_path: Path, images_path: Path, online: bool = False,
                     sample: int = None, cuisine: str = None, recipe_id: str = None,
                     force: bool = False, dry_run: bool = False) -> dict:
    """Associate illustrative images to recipes."""
    index = load_images_index(images_path)
    images_map = index.setdefault('images', {})

    with sqlite3.connect(recipes_db_path) as db:
        query = "SELECT id, title, cuisine, payload FROM recipes"
        args = []
        conditions = []
        if recipe_id:
            conditions.append("id = ?")
            args.append(recipe_id)
        if cuisine:
            conditions.append("cuisine_id = ?")
            args.append(cuisine.lower().replace(' ', '-'))
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += " ORDER BY title, id"
        if sample:
            query += f" LIMIT {int(sample)}"

        rows = db.execute(query, args).fetchall()

    print(f"Trovate {len(rows)} ricette da processare...")
    updated = 0
    skipped = 0

    for r_id, r_title, r_cuisine, r_payload in rows:
        if r_id in images_map and not force:
            skipped += 1
            continue

        search_term = clean_title_for_search(r_title)
        if not online:
            print(f"[OFFLINE] {r_id}: '{search_term}' saltato (usa --online per interrogare Wikimedia Commons)")
            continue

        pages = query_commons_api(search_term)
        chosen = None
        for page in pages:
            cand = parse_imageinfo(page, search_term, r_id, r_title)
            if cand:
                chosen = cand
                break

        if chosen:
            print(f" [OK] {r_id} -> {chosen['title']} ({chosen['license']}, {chosen['author']})")
            if not dry_run:
                images_map[r_id] = chosen
                updated += 1
        else:
            print(f" [MISSING] Nessuna immagine adatta trovata per '{search_term}' ({r_id})")

    if not dry_run and updated > 0:
        save_images_index(index, images_path)
        print(f"Salvate {updated} nuove associazioni in: {images_path}")

    return {
        'total_examined': len(rows),
        'updated': updated,
        'skipped_existing': skipped,
        'total_in_index': len(images_map)
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--recipes-db', type=Path, default=DEFAULT_RECIPES)
    parser.add_argument('--output', type=Path, default=DEFAULT_IMAGES)
    parser.add_argument('--online', action='store_true', help='Consenti chiamate esterne a Wikimedia Commons API')
    parser.add_argument('--sample', type=int, help='Numero massimo di ricette da processare')
    parser.add_argument('--cuisine', type=str, help='Filtra per cucina (es. Italian)')
    parser.add_argument('--recipe-id', type=str, help='Elabora una singola ricetta specifica per ID')
    parser.add_argument('--force', action='store_true', help='Sovrascrivi le associazioni già presenti nell\'indice')
    parser.add_argument('--dry-run', action='store_true', help='Esegui la ricerca senza salvare l\'indice')

    args = parser.parse_args()

    res = associate_images(
        recipes_db_path=args.recipes_db,
        images_path=args.output,
        online=args.online,
        sample=args.sample,
        cuisine=args.cuisine,
        recipe_id=args.recipe_id,
        force=args.force,
        dry_run=args.dry_run
    )

    print("Riepilogo:")
    print(f"  Ricette esaminate:        {res['total_examined']}")
    print(f"  Nuove associazioni:       {res['updated']}")
    print(f"  Già presenti (saltate):   {res['skipped_existing']}")
    print(f"  Totale immagini a catalogo: {res['total_in_index']}")


if __name__ == '__main__':
    main()
