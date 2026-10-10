"""Crash the owned backend during real GPU inference, then verify task recovery."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import urllib.request
import psutil
import soundfile as sf
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
CACHE=ROOT/'cache/separation_chunks'
WORK=ROOT/'cache/separation_resume_check'

def request(route,payload=None):
    req=urllib.request.Request('http://127.0.0.1:8000'+route,
        data=None if payload is None else json.dumps(payload).encode(),headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(req,timeout=10) as response:return json.load(response)

def check():
    WORK.mkdir(parents=True,exist_ok=True)
    source=WORK/'input.wav'
    original,rate=sf.read(ROOT/'cache/atlas_confirmation/live_check/input.wav',always_2d=True)
    # Each run needs a fresh namespace to exercise a genuinely partial job.
    gain=float(np.random.default_rng().uniform(.987,.988))
    sf.write(source,original*gain,rate,subtype='FLOAT')
    before=set(CACHE.glob('*/*.pt')) if CACHE.exists() else set()
    task=request('/separate',{'audio_path':str(source),'model_type':'roformer','model_key':'BS-Roformer-Viperx-1297',
        'out_format':'wav','params':{'overlap':.5,'normalization_threshold':1,'amplification_threshold':0}})['task_id']
    deadline=time.monotonic()+180
    while time.monotonic()<deadline:
        new=set(CACHE.glob('*/*.pt'))-before
        if new:break
        status=request('/status/'+task)
        if status['status']=='failed':raise RuntimeError(status.get('error'))
        time.sleep(.05)
    else:raise RuntimeError('No real inference checkpoint was written')
    saved={str(p):{'mtime':p.stat().st_mtime_ns,'bytes':p.stat().st_size} for p in new}
    service=request('/api/service');pid=service['pid']
    if Path(service['root']).resolve()!=ROOT:raise RuntimeError('Refusing to interrupt another project')
    psutil.Process(pid).kill();psutil.Process(pid).wait(timeout=10)
    print('REAL BACKEND CRASH after',len(saved),'saved chunks; task',task,flush=True)
    subprocess.run([sys.executable,str(ROOT/'service_control.py'),'ensure'],cwd=ROOT,check=True)
    recovered=request('/status/'+task)
    print('RECOVERED SAME TASK',recovered['status'],flush=True)
    deadline=time.monotonic()+240
    while time.monotonic()<deadline:
        status=request('/status/'+task)
        if status['status']=='completed':break
        if status['status']=='failed':raise RuntimeError(status.get('error'))
        time.sleep(1)
    else:raise RuntimeError('Recovered inference did not finish')
    reused=all(Path(p).stat().st_mtime_ns==v['mtime'] for p,v in saved.items())
    if not reused:raise RuntimeError('Completed chunks were recomputed')
    completed=list(Path(next(iter(saved))).parent.glob('*.pt'))
    if len(completed)<=len(saved):raise RuntimeError('The fixture did not exercise remaining unfinished chunks')
    output_info=[sf.info(ROOT/'outputs'/name) for name in status['stems']]
    if len(output_info)!=2 or any(i.frames!=len(original) or i.samplerate!=rate or i.channels!=2 for i in output_info):
        raise RuntimeError('Recovered export duration/channel count changed')
    report={'passed':True,'task_id':task,'crashed_backend_pid':pid,'new_backend_pid':request('/api/service')['pid'],
            'preserved_chunks':len(saved),'total_completed_chunks':len(completed),
            'saved_chunks_reused_without_rewrite':reused,'stems':status['stems'],
            'frames':len(original),'rate':rate,'real_gpu_inference':True}
    (WORK/'results.json').write_text(json.dumps(report,indent=2),encoding='utf8')
    print(json.dumps(report),flush=True)

if __name__=='__main__':check()
