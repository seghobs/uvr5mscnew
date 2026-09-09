"""Verify invalid requests fail without touching recordings."""
import json
import urllib.request
import urllib.error
from pathlib import Path

base = 'http://127.0.0.1:8000'
cases = [
    ('/output/Karaoke_Sync_Test_Vocals_missing.wav', None, 404),
    ('/api/lyrics/reference/search', {'youtube_url':'http://localhost/private'}, 422),
    ('/api/lyrics/reference/compare', {'segments':[], 'reference':''}, 422),
    ('/api/lyrics/reference/apply', {'file_name':'Karaoke_Sync_Test_Vocals.wav','segments':[], 'edits':{}}, 422),
    ('/modify_audio', {'file_name':'Karaoke_Feature_Test_Vocals.wav','tempo_factor':0}, 422),
    ('/generate_karaoke_video', {'inst_file':'Karaoke_Sync_Test_Instrumental.wav','segments':[], 'theme':'invalid'}, 422),
    ('/status/not-a-task', None, 400),
]
results = []
for path, body, expected in cases:
    req = urllib.request.Request(base+path, data=json.dumps(body).encode() if body is not None else None, headers={'Content-Type':'application/json','Range':'bytes=0-0'})
    try:
        with urllib.request.urlopen(req,timeout=30) as response: actual=response.status
    except urllib.error.HTTPError as exc: actual=exc.code
    results.append({'path':path,'expected':expected,'actual':actual})
    assert actual==expected,results[-1]
print(json.dumps(results))
Path('tests/.artifacts/negative_api.json').write_text(json.dumps(results,indent=2))
