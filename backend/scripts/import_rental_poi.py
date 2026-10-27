"""Import named POIs. A rental POI is not proof of a return depot."""
import csv
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
source = ROOT / 'data/drive/rental_poi.csv'
rows, seen = [], set()
with source.open(encoding='utf-8-sig', newline='') as f:
    for r in csv.DictReader(f):
        lat, lng = float(r['center_y']), float(r['center_x'])
        if not (33 <= lat <= 34 and 126 <= lng <= 127):
            continue
        key = (r['dest_name'].strip(), r['dest_address'].strip(), lat, lng)
        if key in seen:
            continue
        seen.add(key)
        ident = hashlib.sha256('|'.join(map(str, key)).encode()).hexdigest()[:12]
        rows.append(dict(id='rental-' + ident, name=key[0], address=key[1], lat=lat, lng=lng,
                         source='팀 제공 TMAP 렌트카 POI', return_verified=False))
rows.sort(key=lambda r: (r['name'], r['address']))
out = ROOT / 'backend/app/data/rental_hubs.json'
out.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print('rental POIs:', len(rows), 'first:', rows[0]['id'])
