"""Associate illustrative images (Wikimedia Commons) and YouTube video proposals to gym exercises.

Extracts exercise names, queries Wikimedia Commons for open licensed photos,
extracts YouTube video suggestions for exercise form, preserves author,
license and source page, and attaches an illustrative disclaimer.
Operates offline by default, requiring --online for external network calls.
"""

import argparse
import html
import json
import re
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REPDB = ROOT / 'dataset/repdb/raw/exercises.json'
DEFAULT_FEDB = ROOT / 'dataset/free_exercise_db/exercises.json'
DEFAULT_MEDIA = ROOT / 'config/exercise-media.json'
COMMONS_API = 'https://commons.wikimedia.org/w/api.php'
USER_AGENT = 'OpteesExerciseMediaBot/1.0 (educational case study; mailto:info@example.com)'
BROWSER_USER_AGENT = (
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
    '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
)

DISCLAIMER = (
    "Immagine e video a solo scopo illustrativo: l'esecuzione corretta, "
    "l'attrezzatura e i carichi devono essere adattati alle proprie capacità "
    "e condizioni individuali."
)
EXERCISE_DISCLAIMER = DISCLAIMER

# Core reviewed exercises for workout draft templates
REVIEWED_EXERCISE_IDS = {
    'dumbbell-floor-press',
    'dumbbell-deadlift',
    'bodyweight-squat',
    'push-up',
    'plank',
    'inverted-row',
    'stationary-bike',
    'rowing-machine',
    'incline-treadmill-walk',
    'elliptical-trainer',
}


def clean_exercise_name_for_search(name: str) -> str:
    """Prepare a clean search query from an exercise identifier or name."""
    if not name:
        return ''
    t = name.replace('-', ' ').replace('_', ' ')
    t = re.sub(r'\(.*?\)', '', t)
    t = re.sub(r'\[.*?\]', '', t)
    t = re.sub(r'\s+', ' ', t).strip()
    return t


def strip_html(text: str) -> tuple:
    """Extract plain text and first href URL from an HTML fragment."""
    if not text:
        return '', None
    url_match = re.search(r'''href=['"]([^'"]+)['"]''', text)
    first_url = html.unescape(url_match.group(1)) if url_match else None
    if first_url and first_url.startswith('//'):
        first_url = 'https:' + first_url
    clean = re.sub(r'<[^>]+>', '', text)
    clean = html.unescape(clean).strip()
    return clean, first_url


def parse_imageinfo(page: dict, search_term: str, exercise_id: str, exercise_name: str) -> dict:
    """Parse MediaWiki imageinfo into a standardized image metadata record."""
    imageinfo = page.get('imageinfo', [])
    if not imageinfo:
        return None

    info = imageinfo[0]
    mime = info.get('mime', '').lower()
    if mime not in ['image/jpeg', 'image/png', 'image/webp']:
        return None

    title = page.get('title', '')
    lower_title = title.lower()
    for skip in ['icon', 'logo', 'flag', 'map', 'diagram', 'symbol', 'coat of arms']:
        if skip in lower_title:
            return None

    extmeta = info.get('extmetadata', {})
    artist_raw = extmeta.get('Artist', {}).get('value', '')
    author, author_url = strip_html(artist_raw)
    if not author:
        author = extmeta.get('Credit', {}).get('value', 'Wikimedia Commons contributor')
        author, _ = strip_html(author)

    license_short = (
        extmeta.get('LicenseShortName', {}).get('value')
        or extmeta.get('UsageTerms', {}).get('value')
        or 'CC-BY-SA'
    )
    license_url = extmeta.get('LicenseUrl', {}).get('value')
    if not license_url and 'cc' in license_short.lower():
        license_url = 'https://creativecommons.org/licenses/'

    source_page = info.get(
        'descriptionurl',
        f"https://commons.wikimedia.org/wiki/{urllib.parse.quote(title.replace(' ', '_'))}"
    )
    image_url = info.get('url')
    thumb_url = info.get('thumburl') or image_url

    return {
        'exercise_id': exercise_id,
        'exercise_name': exercise_name,
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
        'disclaimer': DISCLAIMER,
    }


def query_commons_api(search_term: str, timeout: int = 10) -> list:
    """Execute MediaWiki search query on Wikimedia Commons."""
    params = {
        'action': 'query',
        'generator': 'search',
        'gsrnamespace': '6',
        'gsrsearch': f"{search_term} exercise",
        'gsrlimit': '8',
        'prop': 'imageinfo',
        'iiprop': 'url|size|extmetadata|mime',
        'iiurlwidth': '640',
        'format': 'json',
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


def parse_youtube_search_results(html_text: str, limit: int = 3, max_results: int = None) -> list:
    """Extract video candidates from YouTube search HTML payload."""
    if max_results is not None:
        limit = max_results
    match = re.search(r'var ytInitialData = ({.*?});</script>', html_text)
    if not match:
        match = re.search(r'window\["ytInitialData"\] = ({.*?});</script>', html_text)
    if not match:
        return []

    try:
        data = json.loads(match.group(1))
    except Exception:
        return []

    videos = []

    def extract(obj):
        if isinstance(obj, dict):
            if 'videoRenderer' in obj:
                vr = obj['videoRenderer']
                vid_id = vr.get('videoId')
                title_run = vr.get('title', {}).get('runs', [{}])[0].get('text') or vr.get('title', {}).get('simpleText')
                owner_run = vr.get('ownerText', {}).get('runs', [{}])[0].get('text')
                dur = vr.get('lengthText', {}).get('simpleText')
                if vid_id and title_run:
                    videos.append({
                        'video_id': vid_id,
                        'title': title_run,
                        'channel': owner_run or 'YouTube Creator',
                        'duration': dur or 'N/A',
                        'url': f'https://www.youtube.com/watch?v={vid_id}',
                        'thumbnail_url': f'https://i.ytimg.com/vi/{vid_id}/hqdefault.jpg',
                    })
            for v in obj.values():
                extract(v)
        elif isinstance(obj, list):
            for item in obj:
                extract(item)

    extract(data)

    # Deduplicate by video_id
    seen = set()
    deduped = []
    for v in videos:
        if v['video_id'] not in seen:
            seen.add(v['video_id'])
            deduped.append(v)
        if len(deduped) >= limit:
            break

    return deduped


def query_youtube_search(exercise_name: str, limit: int = 3, timeout: int = 10) -> list:
    """Query YouTube public search for exercise form tutorial videos."""
    query = f"{exercise_name} exercise form tutorial"
    url = f"https://www.youtube.com/results?search_query={urllib.parse.quote(query)}"
    req = urllib.request.Request(url, headers={'User-Agent': BROWSER_USER_AGENT})

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            content = resp.read().decode('utf-8', errors='replace')
            return parse_youtube_search_results(content, limit=limit)
    except Exception as e:
        print(f"Errore nella ricerca YouTube per '{exercise_name}': {e}")
        return []


def load_media_index(media_path: Path) -> dict:
    """Load existing exercise media index JSON."""
    if not media_path.exists():
        return {'version': '1.0', 'exercises': {}}
    try:
        return json.loads(media_path.read_text(encoding='utf-8'))
    except Exception:
        return {'version': '1.0', 'exercises': {}}


def save_media_index(data: dict, media_path: Path):
    """Save updated exercise media index JSON."""
    media_path.parent.mkdir(parents=True, exist_ok=True)
    media_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def load_exercises(source_path: Path) -> list:
    """Load exercises from RepDB or FreeExerciseDB JSON file."""
    if not source_path.exists():
        return []
    data = json.loads(source_path.read_text(encoding='utf-8'))
    if isinstance(data, dict) and 'exercises' in data:
        # RepDB format
        return [
            {
                'id': ex.get('id'),
                'name': ex.get('name_en') or ex.get('name', ''),
                'source': 'repdb',
            }
            for ex in data['exercises']
        ]
    elif isinstance(data, list):
        # FreeExerciseDB format
        return [
            {
                'id': ex.get('id'),
                'name': ex.get('name', ''),
                'source': 'free_exercise_db',
            }
            for ex in data
        ]
    return []


def associate_exercise_media(
    source_path: Path,
    media_path: Path,
    online: bool = False,
    exercise_id: str = None,
    reviewed_only: bool = False,
    sample: int = None,
    skip_images: bool = False,
    skip_youtube: bool = False,
    force: bool = False,
    dry_run: bool = False,
) -> dict:
    """Associate illustrative images and YouTube tutorial videos to exercises."""
    index = load_media_index(media_path)
    exercises_map = index.setdefault('exercises', {})

    all_exercises = load_exercises(source_path)
    if not all_exercises:
        print(f"Nessun esercizio trovato in {source_path}")
        return {'total_examined': 0, 'updated': 0, 'skipped': 0, 'total_in_index': len(exercises_map)}

    filtered = []
    for ex in all_exercises:
        ex_id = ex['id']
        if exercise_id and ex_id != exercise_id:
            continue
        if reviewed_only and ex_id not in REVIEWED_EXERCISE_IDS:
            continue
        filtered.append(ex)

    if sample:
        filtered = filtered[:int(sample)]

    print(f"Trovati {len(filtered)} esercizi da processare...")
    updated = 0
    skipped = 0

    for ex in filtered:
        ex_id = ex['id']
        ex_name = ex['name']
        search_term = clean_exercise_name_for_search(ex_name or ex_id)

        existing = exercises_map.get(ex_id, {})
        has_image = bool(existing.get('illustrative_image'))
        has_videos = bool(existing.get('youtube_videos'))

        if has_image and has_videos and not force:
            skipped += 1
            continue

        if not online:
            print(f"[OFFLINE] {ex_id}: '{search_term}' saltato (usa --online per interrogare Wikimedia Commons e YouTube)")
            continue

        entry = dict(existing)
        entry['exercise_id'] = ex_id
        entry['exercise_name'] = ex_name
        entry['disclaimer'] = DISCLAIMER
        is_changed = False

        # 1. Search Wikimedia Commons Image
        if not skip_images and (not has_image or force):
            pages = query_commons_api(search_term)
            chosen_img = None
            for page in pages:
                cand = parse_imageinfo(page, search_term, ex_id, ex_name)
                if cand:
                    chosen_img = cand
                    break
            if chosen_img:
                entry['illustrative_image'] = chosen_img
                is_changed = True
                print(f" [IMG OK] {ex_id} -> {chosen_img['title']} ({chosen_img['license']}, {chosen_img['author']})")
            else:
                print(f" [IMG MISSING] Nessuna immagine adatta trovata per '{search_term}' ({ex_id})")

        # 2. Search YouTube Video proposals
        if not skip_youtube and (not has_videos or force):
            yt_videos = query_youtube_search(search_term, limit=3)
            if yt_videos:
                entry['youtube_videos'] = yt_videos
                is_changed = True
                print(f" [YT OK] {ex_id} -> {len(yt_videos)} video proposti (es. '{yt_videos[0]['title']}')")
            else:
                print(f" [YT MISSING] Nessun video trovato per '{search_term}' ({ex_id})")

        if is_changed:
            exercises_map[ex_id] = entry
            updated += 1

    if not dry_run and updated > 0:
        save_media_index(index, media_path)
        print(f"Salvate {updated} nuove schede multimediali in: {media_path}")

    return {
        'total_examined': len(filtered),
        'updated': updated,
        'skipped_existing': skipped,
        'total_in_index': len(exercises_map),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=DEFAULT_REPDB, help='Dataset esercizi JSON sorgente')
    parser.add_argument('--output', type=Path, default=DEFAULT_MEDIA, help='File JSON indice multimediale')
    parser.add_argument('--online', action='store_true', help='Consenti chiamate di rete esterne a Wikimedia Commons e YouTube')
    parser.add_argument('--exercise-id', type=str, help='Elabora solo un esercizio specifico per ID')
    parser.add_argument('--reviewed-only', action='store_true', help='Elabora solo gli esercizi revisionati nei template palestra')
    parser.add_argument('--sample', type=int, help='Numero massimo di esercizi da processare')
    parser.add_argument('--skip-images', action='store_true', help='Salta la ricerca di immagini su Wikimedia Commons')
    parser.add_argument('--skip-youtube', action='store_true', help='Salta la ricerca di video su YouTube')
    parser.add_argument('--force', action='store_true', help='Riesegui anche per esercizi già presenti')
    parser.add_argument('--dry-run', action='store_true', help='Non salvare su disco')

    args = parser.parse_args()

    res = associate_exercise_media(
        source_path=args.source,
        media_path=args.output,
        online=args.online,
        exercise_id=args.exercise_id,
        reviewed_only=args.reviewed_only,
        sample=args.sample,
        skip_images=args.skip_images,
        skip_youtube=args.skip_youtube,
        force=args.force,
        dry_run=args.dry_run,
    )

    print('Riepilogo Esercizi:')
    print(f"  Esaminati:                {res['total_examined']}")
    print(f"  Aggiornati:               {res['updated']}")
    print(f"  Saltati (già completi):   {res['skipped_existing']}")
    print(f"  Totale esercizi a catalogo: {res['total_in_index']}")


if __name__ == '__main__':
    main()
