"""Real GPU alignment on an isolated 18-second copy, never the user's project."""
import copy
import json
import time
import urllib.request
from pathlib import Path
import soundfile as sf

ROOT = Path(__file__).resolve().parents[1]
BASE = 'http://127.0.0.1:8000'


def request(path, body=None):
    req = urllib.request.Request(BASE + path, data=json.dumps(body).encode() if body is not None else None,
                                 headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=60) as response: return json.load(response)


original = request('/lyrics/Ensemble_Vocals_1788641882.flac')
segments = copy.deepcopy(original['segments'][:3])
name = 'Karaoke_Reference_E2E_Vocals.wav'
for kind in ('Vocals', 'Instrumental'):
    # Slice using the actual source rate as files can be 44.1/48kHz.
    info = sf.info(ROOT / f'outputs/Ensemble_{kind}_1788641882.flac')
    audio, rate = sf.read(ROOT / f'outputs/Ensemble_{kind}_1788641882.flac', stop=18 * info.samplerate)
    sf.write(ROOT / f'outputs/Karaoke_Reference_E2E_{kind}.wav', audio, rate)
before = request('/save_lyrics', {'file_name': name, 'language': 'tr', 'segments': segments})
job = request('/api/lyrics/reference/apply', {'file_name': name, 'language': 'tr', 'segments': before['segments'],
              'edits': {2: segments[2]['text'].replace('İNADINA', 'İNADINI')}, 'model_name': 'large-v3'})
print('Reference correction task:', job['task_id'], flush=True)
last = ''
for _ in range(900):
    status = request('/status/' + job['task_id'])
    if status.get('message') != last:
        last = status.get('message'); print(last, flush=True)
    if status['status'] == 'failed': raise RuntimeError(status.get('error'))
    if status['status'] == 'completed':
        result = status['result']
        assert result['segments'][:2] == before['segments'][:2], 'Unselected rows changed'
        assert request('/lyrics/' + name)['segments'] == result['segments']
        assert request('/lyrics/Ensemble_Vocals_1788641882.flac')['segments'] == original['segments']
        out = ROOT / 'tests/.artifacts/reference_e2e.json'
        out.write_text(json.dumps({'task_id': job['task_id'], 'result': result, 'original_unchanged': True}, ensure_ascii=False, indent=2), encoding='utf8')
        print('PASS: real alignment, isolated save/reopen, unchanged neighbours and original', flush=True)
        break
    time.sleep(1)
else: raise TimeoutError('Reference alignment timeout')
