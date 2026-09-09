"""Apply a tested draft via the API, refusing stale source snapshots."""
import json
import urllib.request
from pathlib import Path
root = Path(__file__).resolve().parents[1]
out = root / 'tests/.artifacts/ctc_project'
filename = 'Ensemble_Vocals_1788641882.flac'
url = 'http://127.0.0.1:8000'
before = json.loads((out / 'before.json').read_text(encoding='utf8'))
after = json.loads((out / 'after.json').read_text(encoding='utf8'))
with urllib.request.urlopen(url + '/lyrics/' + filename) as response:
    current = json.load(response)
if current['segments'] != before:
    raise RuntimeError('Project changed since analysis; refusing to overwrite newer edits.')
payload = json.dumps({'file_name':filename,'language':'tr','segments':after}).encode()
request = urllib.request.Request(url + '/save_lyrics', data=payload,headers={'Content-Type':'application/json'},method='POST')
with urllib.request.urlopen(request) as response:
    saved = json.load(response)
for alias in (filename, 'Ensemble_Instrumental_1788641882.flac'):
    with urllib.request.urlopen(url + '/lyrics/' + alias) as response:
        reopened = json.load(response)
    assert reopened['segments'] == saved['segments']
    for expected, actual in zip(after, reopened['segments']):
        for left, right in zip(expected['words'],actual['words']):
            assert left['start'] == right['start'] and left['end'] == right['end']
print(json.dumps({'saved':True,'lines':len(after),'issues':saved['timing_issues'],'example':after[1]},ensure_ascii=True))
