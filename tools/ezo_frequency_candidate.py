"""Export frozen three-model candidate and compare against prior Ezo audit."""
import json
from pathlib import Path
import sys
import time
import urllib.request
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from local_runtime import configure_local_runtime
configure_local_runtime()
import numpy as np
import soundfile as sf
import core
import separation_checkpoint
from atlas_studio import PRESET,run_model_estimate
from atlas_band_ensemble import combine_frequency,spectrum


def main():
    fit=json.loads((ROOT/'cache/atlas_music_fit/report.json').read_text(encoding='utf8'))
    previous=json.loads((ROOT/'outputs/Ezo_V1_V2_Music_Comparison/comparison.json').read_text(encoding='utf8'))
    old=json.loads((ROOT/'docs/atlas-studio-v2-ezo-check.json').read_text(encoding='utf8'))
    wave,rate=sf.read(old['source'],dtype='float64',always_2d=True)
    h=.25/max(1.,float(np.abs(wave).max()));capture=ROOT/'cache/ezo_karaoke/captured'
    patterns=['atlas_input_(Vocals)_model_bs*','atlas_input_(vocals)_mel_band_roformer_kim_ft2*','atlas_input_(Instrumental)_melband_roformer_inst_v2*']
    estimates=[]
    for i,pattern in enumerate(patterns):
        estimate,sr=sf.read(next(capture.glob(pattern)),dtype='float64',always_2d=True)
        assert sr==rate and estimate.shape==wave.shape
        estimate/=h
        estimates.append(wave-estimate if i==2 else estimate)
    vocal,inst=combine_frequency(wave,estimates,fit['frequency_weights']);del estimates
    out=ROOT/'outputs/Ezo_Music_Refined';out.mkdir(exist_ok=True)
    sf.write(out/'Ezo_V2_Refined_Instrumental.wav',inst,rate,subtype='FLOAT')
    sf.write(out/'Ezo_V2_Refined_Vocals.wav',vocal,rate,subtype='FLOAT')
    report={'frequency_weights':fit['frequency_weights'],'seconds':len(wave)/rate,
        'distinct_models':3,'inference_passes':3,'secondary_subtraction':False,
        'peak':float(np.max(np.abs(inst))),'source_sum_max_error':float(np.max(np.abs(wave-vocal-inst))),
        'true_music_fidelity_verified':False,'true_sdr_db':None,'zero_leakage_verified':False,
        'low_voice_windows':{},'interpretation':'Same 39 low-voice windows as frozen preceding audit. Source-mixture closeness and Viper residuals are biased proxies, not true isolated instruments or vocals.'}
    frequencies=np.fft.rfftfreq(2048,1/rate)
    for label,path in [('v1',Path(previous['systems']['v1']['file'])),('previous_v2',Path(previous['systems']['v2']['file'])),('refined',out/'Ezo_V2_Refined_Instrumental.wav')]:
        values={band:np.zeros(4) for band in [(20,250),(250,1000),(1000,10000)]}
        with sf.SoundFile(path) as audio:
            for window in previous['windows']:
                if not window['low_voice_model_window']:continue
                start=round(window['start']*rate);audio.seek(start)
                x=audio.read(rate,always_2d=True);src=wave[start:start+len(x)]
                a=spectrum(src);b=spectrum(x)
                for band,sums in values.items():
                    mask=(frequencies>=band[0])&(frequencies<band[1]);aa=np.abs(a[:,mask]);bb=np.abs(b[:,mask])
                    ar=np.maximum(np.diff(np.sqrt(np.sum(aa**2,axis=(0,1)))),0)
                    br=np.maximum(np.diff(np.sqrt(np.sum(bb**2,axis=(0,1)))),0)
                    sums+=np.array([np.sum(np.maximum(aa-bb,0)**2),np.sum(aa**2),np.sum((ar-br)**2),np.sum(ar**2)])
        report['low_voice_windows'][label]={str(band):{'spectral_deficit':float(s[0]/s[1]),'flux_error':float(s[2]/s[3])} for band,s in values.items()}
    for start,end in [(80,96),(140,156),(84,96)]:
        sf.write(out/f'Ezo_V2_Refined_{start}_{end}.wav',inst[start*rate:end*rate],rate,subtype='FLOAT')
    save=lambda:(out/'candidate-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    save();print('EZO CANDIDATE',report['low_voice_windows'],flush=True)
    with urllib.request.urlopen('http://127.0.0.1:8000/api/audio/jobs',timeout=5) as r:jobs=json.load(r)
    if any(j.get('status') in ('queued','processing','cancelling') for j in jobs.get('jobs',[])+jobs.get('other_jobs',[])):
        raise RuntimeError('User jobs active, stopping diagnostic before GPU')
    work=ROOT/'cache/atlas_music_fit';prepared=work/'ezo_refined_probe_input.wav'
    ph=.25/max(1.,float(np.abs(inst).max()));sf.write(prepared,inst*ph,rate,subtype='FLOAT')
    separation_checkpoint.attach_checkpoint=lambda *args,**kwargs:None
    last=[-1]
    def progress(p,m):
        step=int(p*10)
        if step>last[0]:print('REFINED PROBE',round(p*100),m,flush=True);last[0]=step
    started=time.monotonic();estimate=run_model_estimate(core,prepared,PRESET['models'][0],work,rate,len(inst),len(inst),ph,progress)
    sf.write(out/'Ezo_Refined_Estimated_Residual_Voice.wav',estimate,rate,subtype='FLOAT')
    report['vocal_probe']={'estimated_voice_dbfs':float(20*np.log10(max(float(np.sqrt(np.mean(estimate**2))),1e-12))),
        'model':PRESET['models'][0]['model_key'],'independent':False,'seconds_to_process':time.monotonic()-started,
        'v1_dbfs':previous['systems']['v1']['vocal_probe']['estimated_vocal_rms_dbfs'],
        'previous_v2_dbfs':previous['systems']['v2']['vocal_probe']['estimated_vocal_rms_dbfs']}
    save();print('EZO REFINED DONE',json.dumps(report['vocal_probe']),flush=True)


if __name__=='__main__':main()
