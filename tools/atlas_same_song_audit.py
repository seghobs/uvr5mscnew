"""Run frozen production V1/V2 from scratch on one reference multitrack."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time
import urllib.request

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from local_runtime import configure_local_runtime
configure_local_runtime()
import numpy as np
import soundfile as sf
import torch
import core
import separation_checkpoint
from atlas_studio import PRESET,PRESET_V2,run_atlas_studio
from tools.atlas_benchmark import metrics


def leakage(instrumental,vocal,estimate):
    """Conditional least-squares proxy; not a literal perceptual leakage score."""
    basis=np.stack([instrumental.ravel(),vocal.ravel()])
    coefficients=np.linalg.lstsq(basis.T,estimate.ravel(),rcond=None)[0]
    energy=max(float(np.sum(instrumental**2)),1e-12)
    residual=estimate.ravel()-coefficients@basis
    return {'instrumental_gain':float(coefficients[0]),
        'vocal_projection_gain':float(coefficients[1]),
        'vocal_projection_energy_relative_to_reference_instrumental':float(coefficients[1]**2*np.sum(vocal**2)/energy),
        'unexplained_artifact_energy_relative_to_reference_instrumental':float(residual@residual/energy)}


def windowed_leakage(instrumental,vocal,estimate,rate=44100):
    """One-second conditional projections avoid cancellation across the song."""
    projected=0.;windows=[]
    denominator=max(float(np.sum(instrumental**2)),1e-12)
    for start in range(0,len(estimate),rate):
        stop=min(start+rate,len(estimate))
        inst=instrumental[start:stop];voice=vocal[start:stop];output=estimate[start:stop]
        basis=np.stack([inst.ravel(),voice.ravel()])
        gains=np.linalg.lstsq(basis.T,output.ravel(),rcond=None)[0]
        power=float(gains[1]**2*np.sum(voice**2));projected+=power
        windows.append({'start_seconds':start/rate,'stop_seconds':stop/rate,
                        'vocal_projection_gain':float(gains[1]),'projected_vocal_energy':power})
    return {'vocal_leakage_windowed_power_ratio':projected/denominator,'windows':windows}


def main():
    if not torch.cuda.is_available():raise RuntimeError('CUDA required for this real-model comparison')
    with urllib.request.urlopen('http://127.0.0.1:8000/api/audio/jobs',timeout=5) as response:
        jobs=json.load(response)
    if any(j.get('status') in ('queued','processing','cancelling') for j in jobs.get('jobs',[])+jobs.get('other_jobs',[])):
        raise RuntimeError('User jobs active; refusing concurrent GPU comparison')
    source=ROOT/'cache/atlas_benchmark/dataset/test/Al James - Schoolboy Facination.stem.mp4'
    destination=ROOT/'outputs/atlas-v1-v2-schoolboy-comparison'
    destination.mkdir(exist_ok=False)
    preset_paths=[ROOT/'frontend/src/lib'/name for name in ('atlas-studio-preset.json','atlas-studio-v2-preset.json')]
    hashes={path.name:hashlib.sha256(path.read_bytes()).hexdigest() for path in preset_paths}
    stems=[]
    for stream in (1,2,3,4):
        result=subprocess.run(['ffmpeg','-v','error','-i',str(source),'-map',f'0:a:{stream}',
            '-ac','2','-ar','44100','-f','f32le','-'],check=True,capture_output=True)
        stems.append(np.frombuffer(result.stdout,dtype='<f4').reshape(-1,2).astype('float64'))
    instrumental=sum(stems[:3]);vocal=stems[3];mixture=instrumental+vocal
    sf.write(destination/'00_Mixture.wav',mixture,44100,subtype='FLOAT')
    sf.write(destination/'01_Reference_Instrumental.wav',instrumental,44100,subtype='FLOAT')
    sf.write(destination/'02_Reference_Vocals.wav',vocal,44100,subtype='FLOAT')
    decoded_mix,_=sf.read(destination/'00_Mixture.wav',dtype='float64',always_2d=True)
    report={'song':source.stem.removesuffix('.stem'),'source':str(source),
        'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
        'seconds':len(mixture)/44100,'frames':len(mixture),'sample_rate':44100,
        'gpu':torch.cuda.get_device_name(0),'preset_sha256':hashes,
        'presets':{'v1':PRESET,'v2':PRESET_V2},'checkpoint_replay_disabled':True,
        'scope':'One seven-second reference excerpt; no preset fitting or changes. Spectral deficit is an energy proxy, not percent of missing notes. Projection leakage is not a perceptual score.',
        'systems':{}}
    # This standalone process must actually execute neural inference rather
    # than replaying chunk tensors left by earlier development experiments.
    separation_checkpoint.attach_checkpoint=lambda *args,**kwargs:None
    for label,preset in [('v1',PRESET),('v2',PRESET_V2)]:
        print('RUN',label,preset['revision'] if 'revision' in preset else 'original',flush=True)
        last=[-1]
        def progress(fraction,message):
            step=int(fraction*10)
            if step>last[0]:print(label,round(fraction*100),message,flush=True);last[0]=step
        started=time.monotonic()
        files=run_atlas_studio(core,destination/'00_Mixture.wav',preset['models'],'wav',destination,progress,preset=preset)
        predicted_vocal,rate=sf.read(files[0],dtype='float64',always_2d=True)
        predicted_inst,_=sf.read(files[1],dtype='float64',always_2d=True)
        if rate!=44100 or predicted_inst.shape!=instrumental.shape:raise RuntimeError('Timebase changed')
        short=destination/f'{label.upper()}_Instrumental.wav'
        Path(files[1]).replace(short)
        vocal_file=destination/f'{label.upper()}_Vocals.wav';Path(files[0]).replace(vocal_file)
        report['systems'][label]={'seconds_to_process':time.monotonic()-started,
            'instrumental_file':str(short),'vocal_file':str(vocal_file),
            'instrumental_metrics':{**metrics(instrumental,predicted_inst),**leakage(instrumental,vocal,predicted_inst)},
            'windowed_leakage':windowed_leakage(instrumental,vocal,predicted_inst),
            'mixture_sum_max_abs_error':float(np.max(np.abs(predicted_inst+predicted_vocal-decoded_mix))),
            'output_sha256':hashlib.sha256(short.read_bytes()).hexdigest()}
        (destination/'comparison.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
        print('RESULT',label,json.dumps(report['systems'][label]['instrumental_metrics']),flush=True)
    assert hashes=={path.name:hashlib.sha256(path.read_bytes()).hexdigest() for path in preset_paths}
    print('COMPLETE',destination,flush=True)


if __name__=='__main__':main()
