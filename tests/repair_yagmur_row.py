"""Apply the inspected first-row alignment, backing up and checking the live revision."""
import copy
import json
import urllib.request
from pathlib import Path

out = Path(__file__).resolve().parent / '.artifacts'
file = 'Ensemble_Vocals_1788631857.flac'
base = 'http://127.0.0.1:8000'
def get():
    with urllib.request.urlopen(base + '/lyrics/' + file) as response:
        return json.load(response)

original = get()
row = original['segments'][0]
assert row['text'] == 'SÖYLE YAĞMUR ÇAMUR DEĞMEDİ YÜREĞİME'
assert row['start'] == 4.777 and row['words'][1]['start'] == 44.61, 'Project changed; inspect before applying'
backup = out / 'yagmur_before_repair.json'
with backup.open('x', encoding='utf8') as stream:
    json.dump(original, stream, ensure_ascii=False, indent=2)
corrected = copy.deepcopy(original['segments'])
corrected[0] = json.loads((out / 'yagmur_ctc_inspection.json').read_text(encoding='utf8'))[0]
assert corrected[0]['text'] == row['text']
assert get()['segments'] == original['segments'], 'Concurrent edit detected'
request = urllib.request.Request(base + '/save_lyrics', data=json.dumps({
    'file_name':file,'language':original.get('language','tr'),'segments':corrected
}).encode(),headers={'Content-Type':'application/json'})
with urllib.request.urlopen(request) as response:
    json.load(response)
saved = get()['segments']
assert saved[0]['words'] == corrected[0]['words']
assert saved[1:] == original['segments'][1:]
print('PASS: backed up, repaired first row, reopened saved timing, all other rows unchanged')
