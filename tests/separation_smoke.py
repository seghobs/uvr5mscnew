"""Run a locally installed separation model on generated test audio."""
import json
import time
import urllib.request
from pathlib import Path

root = Path(__file__).resolve().parents[1]
def request(path, body=None):
    req = urllib.request.Request('http://127.0.0.1:8000'+path, data=json.dumps(body).encode() if body is not None else None, headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(req, timeout=60) as response: return json.load(response)
model = 'BS-Roformer-Viperx-1297'
assert request('/model_status/'+model)['cached'], 'This test must never download a model.'
job = request('/separate', {'model_type':'roformer','model_key':model,'audio_path':str(root/'outputs/Karaoke_Feature_Test_Vocals.wav'), 'out_format':'wav','params':{}})
last = ''
for _ in range(600):
    status = request('/status/'+job['task_id'])
    if status.get('message') != last:
        last = status.get('message'); print(last, flush=True)
    if status['status'] in ('failed','completed'):
        (root/'tests/.artifacts/separation_smoke.json').write_text(json.dumps(status,indent=2),encoding='utf8')
        assert status['status']=='completed',status.get('error',last)
        print('PASS: installed separation model completed', flush=True)
        break
    time.sleep(1)
else: raise TimeoutError('Separation timeout')
