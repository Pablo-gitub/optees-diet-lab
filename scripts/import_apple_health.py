"""Import the local ZIP into one explicitly named user's private health store."""
import argparse
import json
from pathlib import Path
import sqlite3
from apple_health import import_zip
ROOT=Path(__file__).resolve().parents[1]
if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--zip',type=Path,default=ROOT/'sanitary_data_export/dati esportati.zip')
    parser.add_argument('--web-db',type=Path,default=ROOT/'data/personal/web.sqlite')
    parser.add_argument('--owner',default='paolo');parser.add_argument('--force',action='store_true');args=parser.parse_args()
    with sqlite3.connect(args.web_db) as db:row=db.execute('SELECT id FROM users WHERE username=?',(args.owner,)).fetchone()
    if row is None:raise ValueError('Unknown owner')
    health=args.web_db.parent/'health';health.mkdir(exist_ok=True);health.chmod(0o700)
    ownership=health/'owner.json';ownership.write_text(json.dumps(dict(user_id=row[0],username=args.owner))+'\n');ownership.chmod(0o600)
    report=import_zip(args.zip,health/f'user_{row[0]}',dict(user_id=row[0],username=args.owner),progress=lambda s:print(json.dumps(s),flush=True),force=args.force)
    print(json.dumps(dict(records=report['import']['records_seen'],energy_days=len(report['daily']),workouts=report['import']['workouts_stored'],scenarios=report['scenarios']['status'])),flush=True)
