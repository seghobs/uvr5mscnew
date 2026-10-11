"""Exercise the actual local API and configured production export, not mocks."""
import json
from pathlib import Path
import time
import urllib.request
import numpy as np
import soundfile as sf

ROOT=Path(__file__).resolve().parents[1]
WORK=ROOT/'cache/atlas_confirmation/live_check'


def request(path,payload=None):
    data=None if payload is None else json.dumps(payload).encode()
    req=urllib.request.Request('http://127.0.0.1:8000'+path,data=data,
        headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(req,timeout=30) as response:return json.load(response)


def check():
    preset=json.loads((ROOT/'frontend/src/lib/atlas-studio-v2-preset.json').read_text(encoding='utf8'))
    if not preset.get('calibration',{}).get('accepted'):raise RuntimeError('New calibrated preset has not been accepted/applied')
    WORK.mkdir(parents=True,exist_ok=True)
    with np.load(ROOT/'cache/atlas_extended/turkish/e471d064a086/reference.npz') as ref:
        wave=ref['source'][40*44100:43*44100]
    source=WORK/'input.wav';sf.write(source,wave,44100,subtype='FLOAT')
    expected,rate=sf.read(source,always_2d=True,dtype='float64')
    models=[{k:m[k] for k in ('model_type','model_key')} for m in preset['models']]
    available=request('/models')
    if any(m['model_key'] not in available[m['model_type']] for m in models):raise RuntimeError('Running API model registry is stale')
    created=request('/ensemble',{'audio_path':str(source),'models':models,'out_format':'wav','params':{'ensemble_profile':'atlas_studio_v2'}})
    task=created['task_id'];deadline=time.monotonic()+300;events=[]
    while time.monotonic()<deadline:
        result=request('/status/'+task)
        event={'status':result['status'],'progress':result.get('progress'),'message':result.get('message')}
        if not events or event!=events[-1]:events.append(event);print('LIVE',event,flush=True)
        if result['status']=='failed':raise RuntimeError(result.get('error',result))
        if result['status']=='completed':break
        time.sleep(3)
    else:raise RuntimeError('Live production task timed out')
    files=[ROOT/'outputs'/name for name in result['stems']]
    if len(files)!=2:raise RuntimeError('Live API did not export two stems')
    waves=[]
    for path in files:
        output,sr=sf.read(path,always_2d=True,dtype='float64')
        if sr!=rate or output.shape!=expected.shape or not np.isfinite(output).all():raise RuntimeError('Live export changed duration/channel count or produced nonfinite samples')
        waves.append(output)
    error=float(np.abs(sum(waves)-expected).max())
    if error>1e-6:raise RuntimeError('Live API source sum was not preserved')
    report={'passed':True,'task_id':task,'models':models,'frames':len(expected),'rate':rate,'sum_max_abs_error':error,
        'output_files':[str(p) for p in files],'events':events,'quality_benchmark':False}
    (WORK/'results.json').write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf8')
    print('LIVE EXPORT VERIFIED',error,flush=True)


if __name__=='__main__':check()
