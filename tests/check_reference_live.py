"""Read-only smoke test of real search/comparison; never applies lyric edits."""
import json
import sqlite3
from pathlib import Path
from urllib.request import Request, urlopen


def post(path, data):
    request = Request('http://127.0.0.1:8000/api/lyrics/reference/' + path,
                      data=json.dumps(data).encode(), headers={'Content-Type': 'application/json'})
    with urlopen(request, timeout=60) as response:
        return json.load(response)


root = Path(__file__).resolve().parents[1]
with sqlite3.connect((root / 'assets/favorites.db').as_uri() + '?mode=ro', uri=True) as conn:
    row = conn.execute('SELECT segments_json FROM lyrics WHERE file_name LIKE ? ORDER BY updated_at DESC LIMIT 1', ('%1788641882%',)).fetchone()
segments = json.loads(row[0])
found = post('search', {'youtube_url': 'https://www.youtube.com/watch?v=jWh-7JGuxTo'})
assert found['artist'] == 'Hadise' and found['title'] == 'Ara Beni'
assert found['candidates']
compared = post('compare', {'segments': segments, 'reference': found['candidates'][0]['text']})
assert len(compared['rows']) == len(segments)
with sqlite3.connect((root / 'assets/favorites.db').as_uri() + '?mode=ro', uri=True) as conn:
    after = conn.execute('SELECT segments_json FROM lyrics WHERE file_name LIKE ? ORDER BY updated_at DESC LIMIT 1', ('%1788641882%',)).fetchone()
assert after == row, 'Search/comparison must never save lyrics.'
print(json.dumps({'candidates': len(found['candidates']), 'rows_preserved': len(segments),
                  'proposed_rows': [r['index'] + 1 for r in compared['rows'] if r['changed']],
                  'database_unchanged': True}))
