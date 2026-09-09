"""Exercise the same complete background alignment endpoint as the UI."""
import json
import time
import urllib.request
from pathlib import Path
base = 'http://127.0.0.1:8000'
file = 'Ensemble_Vocals_1788641882.flac'
def get(path):
    with urllib.request.urlopen(base + path) as response:
        return json.load(response)
before = get('/lyrics/' + file)
payload = {'file_name':file,'language':'tr','force':True,'model_name':'large-v3',
           'raw_lyrics_text':'\n'.join(s['text'] for s in before['segments'])}
request = urllib.request.Request(base + '/transcribe_lyrics',data=json.dumps(payload).encode(),headers={'Content-Type':'application/json'},method='POST')
with urllib.request.urlopen(request) as response:
    task = json.load(response)
last = ''
for _ in range(7200):
    status = get('/status/' + task['task_id'])
    message = status.get('message','')
    if message != last:
        print(message,flush=True); last = message
    if status['status'] == 'failed':
        raise RuntimeError(status.get('error', message))
    if status['status'] == 'completed':
        result = status['result']
        assert [w['word'] for s in result['segments'] for w in s['words']] == [w['word'] for s in before['segments'] for w in s['words']]
        assert any(w.get('timing_source') == 'ctc' for s in result['segments'] for w in s['words'])
        reopened = get('/lyrics/Ensemble_Instrumental_1788641882.flac')
        assert reopened['segments'] == result['segments']
        Path('tests/.artifacts/ctc_project/live_result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
        print(json.dumps({'completed':True,'words':sum(len(s['words']) for s in result['segments']),'issues':len(result['timing_issues']),'example':result['segments'][1]},ensure_ascii=True))
        break
    time.sleep(1)
else:
    raise TimeoutError('Alignment is still running.')
