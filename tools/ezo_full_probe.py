"""Whole-record independent-model diagnostic, not a ground-truth quality score."""
import json
from pathlib import Path
import sys
import urllib.request

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from local_runtime import configure_local_runtime
configure_local_runtime()
import numpy as np
import soundfile as sf
import core
from atlas_studio import PRESET,run_model_estimate


def main():
    with urllib.request.urlopen('http://127.0.0.1:8000/api/audio/jobs',timeout=5) as r:data=json.load(r)
    if any(j.get('status') in ('queued','processing','cancelling') for j in data.get('jobs',[])+data.get('other_jobs',[])):
        raise RuntimeError('User jobs are active')
    work=ROOT/'cache/ezo_karaoke';out=ROOT/'outputs/Ezo_Karaoke_Gelistirme'
    wave,rate=sf.read(out/'Ezo_Strict_1.0_Instrumental.wav',dtype='float64',always_2d=True)
    h=.25/max(1.,float(np.abs(wave).max()));prepared=work/'full_probe_input.wav';sf.write(prepared,wave*h,rate,subtype='FLOAT')
    last=[-1]
    def progress(p,m):
        step=int(p*10)
        if step>last[0]:print('FULL PROBE',round(p*100),m,flush=True);last[0]=step
    estimate=run_model_estimate(core,prepared,PRESET['models'][0],work,rate,len(wave),len(wave),h,progress)
    sf.write(out/'Ezo_Full_Independent_Vocal_Estimate.wav',estimate,rate,subtype='FLOAT')
    windows=[]
    for start in range(0,len(wave),rate):
        segment=estimate[start:start+rate];rms=float(np.sqrt(np.mean(segment**2)))
        windows.append({'start':start/rate,'estimated_vocal_rms_dbfs':float(20*np.log10(max(rms,1e-12)))})
    report={'diagnostic_only':True,'zero_leakage_verified':False,'true_sdr_db':None,
        'seconds':len(wave)/rate,'model':PRESET['models'][0]['model_key'],
        'overall_estimated_vocal_rms_dbfs':float(20*np.log10(max(float(np.sqrt(np.mean(estimate**2))),1e-12))),
        'loudest_estimated_windows':sorted(windows,key=lambda w:w['estimated_vocal_rms_dbfs'],reverse=True)[:12],
        'windows':windows,'warning':'This model can classify instruments as voice. Its output is not isolated ground truth.'}
    (work/'full-probe.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print('FULL PROBE DONE',report['overall_estimated_vocal_rms_dbfs'],report['loudest_estimated_windows'][:3],flush=True)


if __name__=='__main__':main()
