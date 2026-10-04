"""Build/query an offline SQLite index of the normalized branded catalog."""
import argparse
import json
import sqlite3
import unicodedata
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
DIRECTORY=ROOT/'dataset/open_food_facts'

def fold(text):
    return ''.join(c for c in unicodedata.normalize('NFKD',text.casefold()) if not unicodedata.combining(c))

def build(directory):
    temporary=directory/'catalog.sqlite.tmp'
    if temporary.exists():temporary.unlink()
    with sqlite3.connect(temporary) as db:
        db.execute('CREATE TABLE products(barcode TEXT PRIMARY KEY,name TEXT,brands TEXT,search_text TEXT,numeric_candidate INTEGER,payload TEXT)')
        with (directory/'products.jsonl').open() as stream:
            for line in stream:
                p=json.loads(line)
                db.execute('INSERT INTO products VALUES(?,?,?,?,?,?)',(p['barcode'],p['name'],p['brands'],fold(p['name']+' '+p['brands']+' '+p['barcode']),p['numeric_candidate'],line))
        db.execute('CREATE INDEX brands_index ON products(brands)')
        count=db.execute('SELECT COUNT(*) FROM products').fetchone()[0]
    temporary.replace(directory/'catalog.sqlite')
    print(f'Indexed {count:,} products')

def search(directory,text):
    with sqlite3.connect(directory/'catalog.sqlite') as db:
        escaped=fold(text).replace('\\','\\\\').replace('%','\\%').replace('_','\\_')
        for code,name,brands,candidate in db.execute("SELECT barcode,name,brands,numeric_candidate FROM products WHERE search_text LIKE ? ESCAPE '\\' LIMIT 20",('%'+escaped+'%',)):
            print(f'{code} | {brands} | {name} | numeric_candidate={bool(candidate)}')

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--directory',type=Path,default=DIRECTORY);p.add_argument('--search');a=p.parse_args()
    search(a.directory,a.search) if a.search else build(a.directory)
