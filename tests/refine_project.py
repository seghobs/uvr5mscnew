"""Run the production character aligner against a saved project, output a draft."""
import json
import sqlite3
import sys
from pathlib import Path
root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))
from karaoke_ctc import refine_turkish
from karaoke_timing import timing_issues
file = sys.argv[1]
out = root / 'tests/.artifacts/ctc_project'
out.mkdir(parents=True, exist_ok=True)
with sqlite3.connect((root / 'assets/favorites.db').as_uri() + '?mode=ro', uri=True) as conn:
    raw = conn.execute('select segments_json from lyrics where file_name=? order by updated_at desc limit 1', (file,)).fetchone()[0]
segments = json.loads(raw)
(out / 'before.json').write_text(raw, encoding='utf8')
result = refine_turkish(root / 'outputs' / file, segments, 'tr', lambda f,m: print(m,flush=True))
assert [w['word'] for s in result for w in s['words']] == [w['word'] for s in segments for w in s['words']]
(out / 'after.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps({'lines':len(result),'words':sum(len(s['words']) for s in result),'issues':timing_issues(result),'example':result[1]},ensure_ascii=True))
