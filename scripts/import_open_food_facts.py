"""Stream official OFF TSV export, retaining products tagged sold in Italy."""
import argparse
import collections
import csv
import datetime
import gzip
import hashlib
import io
import json
import math
import re
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = 'https://static.openfoodfacts.org/data/en.openfoodfacts.org.products.csv.gz'
TARGET_BRANDS = {'Barilla':['barilla'], 'La Molisana':['la-molisana','molisana'],
                 'Kelloggs':['kellogg-s','kelloggs','kellogg'], 'Muller':['muller','mueller'],
                 'Misura':['misura'], 'Mulino Bianco':['mulino-bianco'],
                 'Granoro':['granoro'], 'De Cecco':['de-cecco'], 'Rummo':['rummo'],
                 'Garofalo':['garofalo'], 'Parmalat':['parmalat'], 'Granarolo':['granarolo'],
                 'Coop':['coop'], 'Conad':['conad'], 'Esselunga':['esselunga']}
NUMERIC = {'kcal_100g':'energy-kcal_100g', 'protein_g_100g':'proteins_100g',
           'fat_g_100g':'fat_100g','carbs_available_g_100g':'carbohydrates_100g',
           'saturated_fat_g_100g':'saturated-fat_100g','sugars_g_100g':'sugars_100g',
           'fiber_g_100g':'fiber_100g','salt_g_100g':'salt_100g'}


def number(value):
    if value is None or str(value).strip() == '':
        return None
    try: n = float(value)
    except (ValueError, TypeError): return None
    return n if math.isfinite(n) and n >= 0 else None


def normalize(row):
    flags=[]
    nutrients={key:number(row.get(source)) for key,source in NUMERIC.items()}
    if nutrients['kcal_100g'] is None:
        kj=number(row.get('energy-kj_100g'))
        if kj is not None:
            nutrients['kcal_100g']=kj/4.184
            flags.append('energy_converted_from_kJ')
    required=['kcal_100g','protein_g_100g','fat_g_100g','carbs_available_g_100g']
    missing=[key for key in required if nutrients[key] is None]
    if missing:flags.append('missing_core_nutrients')
    if nutrients['kcal_100g'] is not None and nutrients['kcal_100g']>950:flags.append('implausible_energy')
    mass=[nutrients[n] for n in ['protein_g_100g','fat_g_100g','carbs_available_g_100g']]
    if all(x is not None for x in mass) and sum(mass)>105:flags.append('implausible_macro_sum')
    for key,value in nutrients.items():
        if key!='kcal_100g' and value is not None and value>100:flags.append('implausible_'+key)
    for sub,total in [('sugars_g_100g','carbs_available_g_100g'),('saturated_fat_g_100g','fat_g_100g')]:
        if nutrients[sub] is not None and nutrients[total] is not None and nutrients[sub]>nutrients[total]+1:flags.append('inconsistent_'+sub)
    name=row.get('product_name') or row.get('generic_name') or ''
    if not name:flags.append('missing_name')
    errors=row.get('data_quality_errors_tags','')
    if errors:flags.append('source_quality_errors')
    unit=row.get('product_quantity_unit','')
    if not unit:
        # Explicit pack units only; do not infer liquid/solid from product category.
        quantity=row.get('quantity','').strip().lower()
        if re.search(r'\d\s*(ml|cl|l)\b',quantity):unit='ml'
        elif re.search(r'\d\s*(g|kg)\b',quantity):unit='g'
    basis='per_100_ml' if unit in ['ml','cl','l'] else 'per_100_g' if unit in ['g','kg'] else 'per_100_g_or_ml_unresolved'
    if basis=='per_100_g_or_ml_unresolved':flags.append('mass_volume_basis_unresolved')
    blocked=[f for f in flags if f!='energy_converted_from_kJ']
    return dict(source='Open Food Facts',source_id=row['code'],barcode=row['code'],name=name,
                brands=row.get('brands',''),brands_tags=row.get('brands_tags',''),
                category=row.get('categories',''),categories_tags=row.get('categories_tags',''),
                countries_tags=row.get('countries_tags',''),quantity=row.get('quantity',''),
                serving_raw=row.get('serving_size',''),nutrition_data_per=row.get('nutrition_data_per',''),
                nutrient_basis=basis,**nutrients,allergens_tags=row.get('allergens',''),
                ingredients_text=row.get('ingredients_text',''),last_modified_t=row.get('last_modified_t',''),
                source_quality_errors=errors,source_quality_warnings=row.get('data_quality_warnings_tags',''),
                quality_flags=flags,missing_core_nutrients=missing,
                numeric_candidate=not blocked, diet_mapping_status='unreviewed',
                solver_eligible=False, source_url='https://world.openfoodfacts.org/product/'+row['code'])


class HashedReader:
    def __init__(self,stream):self.stream=stream;self.sha=hashlib.sha256();self.bytes=0
    def read(self,size=-1):
        data=self.stream.read(size);self.sha.update(data);self.bytes+=len(data);return data


def run(output, local=None):
    output.mkdir(parents=True,exist_ok=True)
    csv.field_size_limit(50_000_000)
    if local:
        stream=local.open('rb');headers={};url=str(local)
    else:
        stream=urllib.request.urlopen(urllib.request.Request(SOURCE,headers={'User-Agent':'OpteesDietCaseStudy/0.1 (local dataset import)'}),timeout=120)
        headers={k:stream.headers.get(k) for k in ['Last-Modified','ETag','Content-Length']};url=SOURCE
    hashed=HashedReader(stream)
    reader=csv.DictReader(io.TextIOWrapper(gzip.GzipFile(fileobj=hashed),encoding='utf-8',newline=''),delimiter='\t')
    if not {'code','countries_tags'}.issubset(reader.fieldnames):raise ValueError('Unsupported OFF export schema')
    print('Export schema:',len(reader.fieldnames),'fields',flush=True)
    codes=set();brands=collections.Counter();flags=collections.Counter();requested=collections.Counter()
    count=0;scanned=0;eligible=0;start=time.monotonic()
    temporary=output/'products.jsonl.tmp';rawtmp=output/'raw_italy.jsonl.gz.tmp'
    with temporary.open('w') as target,gzip.open(rawtmp,'wt',encoding='utf-8') as raw:
        for row in reader:
            scanned+=1
            if scanned%100000==0:print(f'Scanned {scanned:,}; Italy {count:,}; compressed read {hashed.bytes//1_000_000} MB; elapsed {time.monotonic()-start:.0f}s',flush=True)
            if 'en:italy' not in row.get('countries_tags','').split(','):continue
            code=row.get('code','')
            if not code or code in codes:continue
            codes.add(code);product=normalize(row);count+=1;eligible+=product['numeric_candidate']
            target.write(json.dumps(product,ensure_ascii=False)+'\n');raw.write(json.dumps(row,ensure_ascii=False)+'\n')
            tags=row.get('brands_tags','').split(',')
            brands.update([t for t in tags if t]);flags.update(product['quality_flags'])
            for label,aliases in TARGET_BRANDS.items():
                if any(t in aliases or t.removeprefix('xx:') in aliases for t in tags):requested[label]+=1
    stream.close()
    # Replace completed outputs only; an interrupted import leaves old catalog usable.
    temporary.replace(output/'products.jsonl');rawtmp.replace(output/'raw_italy.jsonl.gz')
    manifest=dict(source='Open Food Facts contributors',source_url=url,license='ODbL 1.0 (database); DbCL 1.0 (contents)',
                  downloaded_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),source_headers=headers,
                  source_compressed_sha256=hashed.sha.hexdigest(),source_compressed_bytes=hashed.bytes,
                  selection='countries_tags contains exact en:italy; deduplication by barcode; all brands',
                  scanned_rows=scanned,products=count,numeric_candidates=eligible,solver_eligible=0,
                  requested_brands=dict(requested),top_brand_tags=brands.most_common(30),quality_flags=dict(flags),
                  normalized_sha256=hashlib.sha256((output/'products.jsonl').read_bytes()).hexdigest())
    (output/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:manifest[k] for k in ['products','numeric_candidates','requested_brands']},ensure_ascii=False,indent=2),flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'dataset/open_food_facts')
    parser.add_argument('--input',type=Path,help='Optional local official TSV gzip')
    args=parser.parse_args();run(args.output,args.input)
