"""Finish Ezo-only residual trials after the user's current GPU job completes."""
import hashlib
import json
from pathlib import Path
import shutil
import sys
import time
import urllib.request

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from local_runtime import configure_local_runtime
configure_local_runtime()
import numpy as np
import soundfile as sf
import core
from atlas_studio import PRESET,PRESET_V2,combine,run_model_estimate
from karaoke_residual import corrected_instrumental,correction_activity

WORK=ROOT/'cache/ezo_karaoke'
OUT=ROOT/'outputs/Ezo_Karaoke_Gelistirme'


def jobs():
    with urllib.request.urlopen('http://127.0.0.1:8000/api/audio/jobs',timeout=6) as response:return json.load(response)


def main():
    OUT.mkdir(exist_ok=True)
    while True:
        data=jobs();active=[j for j in data.get('jobs',[])+data.get('other_jobs',[]) if j.get('status') in ('queued','processing','cancelling')]
        if not active:break
        time.sleep(5)
    completed=[j for j in data.get('other_jobs',[]) if 'Ezo' in str(j.get('separation_request',{})) and j.get('status')=='completed']
    if not completed:raise RuntimeError('The original Ezo baseline did not finish; no baseline is being fabricated')
    job=max(completed,key=lambda j:j.get('created_at',0))
    old_inst=next(ROOT/'outputs'/name for name in job['stems'] if '_Instrumental_' in name)
    source=next((ROOT/'ytdl').glob('*Ezo.wav'))
    wave,rate=sf.read(source,dtype='float64',always_2d=True);frames=len(wave)
    headroom=.25/max(1.,float(np.abs(wave).max()));capture=WORK/'captured'
    patterns=['atlas_input_(Vocals)_model_bs*','atlas_input_(vocals)_mel_band_roformer_kim_ft2*','atlas_input_(Instrumental)_melband_roformer_inst_v2*']
    estimates=[]
    for pattern in patterns:
        matches=list(capture.glob(pattern))
        if len(matches)!=1:raise RuntimeError(f'Missing unmodified baseline model output: {pattern}')
        estimate,sr=sf.read(matches[0],dtype='float64',always_2d=True)
        if sr!=rate or estimate.shape!=wave.shape:raise RuntimeError('Baseline timebase changed')
        estimates.append(estimate/headroom)
    _,v1=combine(wave,estimates,PRESET)
    _,single=combine(wave,estimates,PRESET_V2)
    sf.write(OUT/'Ezo_V1_Instrumental.wav',v1,rate,subtype='FLOAT')
    sf.write(OUT/'Ezo_V2_SinglePass_Baseline.wav',single,rate,subtype='FLOAT')
    shutil.copy2(old_inst,OUT/'Ezo_V2_Before_Instrumental.wav')
    (WORK/'previous-preset.json').write_text(json.dumps(PRESET_V2,ensure_ascii=False,indent=2),encoding='utf8')
    cleanup_headroom=.25/max(1.,float(np.abs(single).max()))
    prepared=WORK/'full_residual_input.wav';sf.write(prepared,single*cleanup_headroom,rate,subtype='FLOAT')
    print('START FULL RESIDUAL CHECK',frames/rate,'seconds',flush=True)
    started=time.monotonic();model=PRESET_V2['models'][1];last=[-1]
    def progress(p,m):
        step=int(p*10)
        if step>last[0]:print('CLEANUP',round(100*p),m,flush=True);last[0]=step
    residual=run_model_estimate(core,prepared,model,WORK,rate,frames,frames,cleanup_headroom,progress)
    sf.write(OUT/'Ezo_Removed_Estimate.wav',residual,rate,subtype='FLOAT')
    activity=correction_activity(wave,estimates[0],rate)
    gate=activity[:,None]
    corrected=single-gate*residual
    for strength in (.5,.75,1.):
        sf.write(OUT/f'Ezo_Strict_{strength}_Instrumental.wav',single-strength*gate*residual,rate,subtype='FLOAT')
    sf.write(OUT/'Ezo_Strict_1.0_Vocals.wav',wave-corrected,rate,subtype='FLOAT')
    report={'source':str(source),'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
        'isolated_reference_stems_available':False,'true_instrumental_sdr_db':None,'zero_leakage_verified':False,
        'baseline_job_id':job['id'],'previous_preset':PRESET_V2,'frames':frames,'rate':rate,
        'cleanup_model_reused':model['model_key'],'cleanup_seconds':time.monotonic()-started,
        'identity_passes_captured_from_running_job':True,'distinct_separation_models':3,
        'candidate_runtime_full_passes':4,'correction_only_activity_gate':True,'clips':[]}
    for start,end in [(0,20),(40,56),(80,96),(140,156),(220,236)]:
        a=round(start*rate);b=round(end*rate);base=single[a:b];result=corrected[a:b]
        diff=result-base;ratio=float(np.sum(diff**2)/max(float(np.sum(base**2)),1e-20))
        report['clips'].append({'start':start,'end':end,'gate_mean':float(activity[a:b].mean()),
            'relative_changed_energy':ratio,'max_abs_correction':float(np.abs(diff).max()),
            'is_true_music_loss_measurement':False})
    old,_=sf.read(old_inst,dtype='float64',always_2d=True)
    reference=PRESET['models'][0]
    report['independent_model_probe']={}
    for label,audio in [('old_v2',old),('strict_v2',corrected)]:
        clip=audio[80*rate:96*rate];h=.25/max(1.,float(np.abs(clip).max()));input_path=WORK/f'probe_{label}.wav'
        sf.write(input_path,clip*h,rate,subtype='FLOAT')
        estimate=run_model_estimate(core,input_path,reference,WORK,rate,len(clip),len(clip),h,lambda p,m:None)
        rms=float(np.sqrt(np.mean(estimate**2)))
        report['independent_model_probe'][label]={'estimated_vocal_rms_dbfs':20*float(np.log10(max(rms,1e-12))),
                'estimated_vocal_energy_relative_to_input':float(np.sum(estimate**2)/max(float(np.sum(clip**2)),1e-20)),
                'is_ground_truth_leakage':False}
        sf.write(OUT/f'Ezo_80s_Probe_{label}.wav',estimate,rate,subtype='FLOAT')
        print('PROBE',label,report['independent_model_probe'][label],flush=True)
    report['independent_model_probe']['estimated_residual_drop_db']=(
        report['independent_model_probe']['old_v2']['estimated_vocal_rms_dbfs']-
        report['independent_model_probe']['strict_v2']['estimated_vocal_rms_dbfs'])
    (WORK/'ezo-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    shutil.copy2(WORK/'ezo-report.json',OUT/'comparison.json')
    print('EZO TRIAL DONE',OUT,flush=True)


if __name__=='__main__':main()
