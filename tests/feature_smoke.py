"""Live functional matrix using generated test audio only."""
import json
import time
import urllib.request
import urllib.error
from pathlib import Path
import numpy as np
import soundfile as sf
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
BASE = 'http://127.0.0.1:8000'
results = []


def request(path, body=None):
    req = urllib.request.Request(BASE + path, data=json.dumps(body).encode() if body is not None else None,
                                 headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=120) as r: return json.load(r)


def record(name, passed, detail):
    results.append({'test': name, 'passed': bool(passed), 'detail': detail})
    print(json.dumps(results[-1]), flush=True)
    report = 'feature_smoke_48000.json' if '--48000' in sys.argv else 'feature_smoke.json'
    (ROOT/'tests/.artifacts'/report).write_text(json.dumps(results, indent=2), encoding='utf8')


rate = 48000 if '--48000' in sys.argv else 44100
for kind, frequency in [('Vocals', 220), ('Instrumental', 330)]:
    sf.write(ROOT/f'outputs/Karaoke_Feature_Test_{kind}.wav', .05*np.sin(2*np.pi*frequency*np.arange(rate*4)/rate), rate)
for pitch, tempo in [(0, 1), (12, 1), (-12, 1), (3, 1.25)]:
    result = request('/modify_audio', {'file_name': 'Karaoke_Feature_Test_Vocals.wav', 'pitch_semitones': pitch, 'tempo_factor': tempo})
    samples, actual_rate = sf.read(ROOT/'outputs'/result['filename'])
    duration = len(samples)/actual_rate
    spectrum = abs(np.fft.rfft(samples))
    peak = np.argmax(spectrum)*actual_rate/len(samples)
    record(f'pitch={pitch},tempo={tempo}', abs(duration-4/tempo)<=1/rate and abs(peak-220*2**(pitch/12))<3,
           {'seconds': duration, 'expected': 4/tempo, 'frequency': peak})
result = request('/remix', {'vocal_file': 'Karaoke_Feature_Test_Vocals.wav', 'inst_file': 'Karaoke_Feature_Test_Instrumental.wav', 'pitch_shift': 12, 'out_format': 'wav'})
duration = sf.info(ROOT/'outputs'/result['filename']).duration
record('remix_pitch_duration', abs(duration-4)<=1/rate, duration)
if '--audio-only' in sys.argv: sys.exit(0 if all(r['passed'] for r in results) else 1)

for endpoint in ['/models', '/whisper_status', '/api/favorites', '/leaderboard']:
    try: record('read '+endpoint, bool(request(endpoint)), 'responded')
    except Exception as exc: record('read '+endpoint, False, str(exc))

lyrics = request('/lyrics/Karaoke_Sync_Test_Vocals.wav')['segments']
for aspect in ['16:9', '9:16']:
    for theme in ['gold', 'neon', 'cyberpunk', 'emerald']:
        job = request('/generate_karaoke_video', {'inst_file':'Karaoke_Sync_Test_Instrumental.wav',
            'timing_file':'Karaoke_Sync_Test_Vocals.wav', 'segments':lyrics, 'aspect_ratio':aspect, 'theme':theme, 'show_header':False})
        for _ in range(240):
            status = request('/status/'+job['task_id'])
            if status['status'] in ('failed','completed'): break
            time.sleep(.5)
        if status['status'] != 'completed':
            record(f'video {aspect} {theme}',False,status); continue
        result = status.get('result', status)
        path = ROOT/'outputs'/result['video_file']
        import re
        probe = subprocess.run(['ffmpeg','-hide_banner','-i',str(path)],capture_output=True,text=True,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0)).stderr
        expected = (1920,1080) if aspect=='16:9' else (1080,1920)
        record(f'video {aspect} {theme}', f'{expected[0]}x{expected[1]}' in probe and '60 fps' in probe, {'file':str(path),'size':expected,'fps':60})

for aspect in ['16:9','9:16']:
    result = request('/generate_visualizer', {'file_name':'Karaoke_Feature_Test_Vocals.wav','aspect_ratio':aspect,'theme':'neon'})
    record('visualizer '+aspect,result.get('status')=='success',result)
sys.exit(0 if all(r['passed'] for r in results) else 1)
