"""Full Ezo paired audit. Mixture comparisons and model probes are not true stems."""
import hashlib
import json
from pathlib import Path
import sys
import time
import urllib.request

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from local_runtime import configure_local_runtime
configure_local_runtime()
import numpy as np
import soundfile as sf
from scipy.signal import stft
import core
import separation_checkpoint
from atlas_studio import PRESET,PRESET_V2,run_model_estimate

OUT=ROOT/'outputs/Ezo_V1_V2_Music_Comparison'
WORK=ROOT/'cache/ezo_music_audit'
BANDS={'sub_20_60':(20,60),'bass_60_250':(60,250),'low_mid_250_1000':(250,1000),
       'mid_1000_4000':(1000,4000),'presence_4000_10000':(4000,10000),'air_10000_20000':(10000,20000)}


def digest(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
    return h.hexdigest()


def idle():
    with urllib.request.urlopen('http://127.0.0.1:8000/api/audio/jobs',timeout=5) as r:jobs=json.load(r)
    if any(j.get('status') in ('queued','processing','cancelling') for j in jobs.get('jobs',[])+jobs.get('other_jobs',[])):
        raise RuntimeError('User GPU jobs active; refusing diagnostic competition')


def spectrum(wave,rate):
    return np.abs(stft(wave.T,fs=rate,nperseg=2048,noverlap=1536,boundary=None)[2])


def main():
    OUT.mkdir(exist_ok=True);WORK.mkdir(exist_ok=True)
    assert 'residual_cleanup' not in PRESET_V2
    old=json.loads((ROOT/'docs/atlas-studio-v2-ezo-check.json').read_text(encoding='utf8'))
    source=Path(old['source']);folder=ROOT/'outputs/Ezo_Karaoke_Gelistirme'
    paths={'v1':folder/'Ezo_V1_Instrumental.wav','v2':folder/'Ezo_V2_Music_Instrumental.wav'}
    info=sf.info(source);rate=info.samplerate
    assert digest(source)==old['source_sha256']
    report={'song':source.name,'seconds':info.duration,'source_sha256':digest(source),
        'presets':{'v1':PRESET,'v2':PRESET_V2},'isolated_reference_stems_available':False,
        'perceptual_listening_performed':False,'true_drum_bass_fidelity_winner':None,
        'true_vocal_leakage_winner':None,'true_sdr_db':None,'zero_leakage_verified':False,
        'systems':{},'windows':[],'band_summary':{}}
    original,_=sf.read(source,dtype='float32',always_2d=True)
    peak=float(np.max(np.abs(original)));headroom=.25/max(1.,peak)
    captures=ROOT/'cache/ezo_karaoke/captured'
    patterns=['atlas_input_(Vocals)_model_bs*','atlas_input_(vocals)_mel_band_roformer_kim_ft2*','atlas_input_(Instrumental)_melband_roformer_inst_v2*']
    handles=[sf.SoundFile(next(captures.glob(pattern))) for pattern in patterns]
    files={key:sf.SoundFile(path) for key,path in paths.items()}
    sums={key:{band:np.zeros(4) for band in BANDS} for key in paths}
    lowvoice={key:{band:np.zeros(4) for band in BANDS} for key in paths}
    max_errors={key:0. for key in paths};lowvoice_count=0
    try:
        for start in range(0,len(original),rate):
            mixture=original[start:start+rate].astype('float64')
            estimates=[h.read(len(mixture),dtype='float64',always_2d=True)/headroom for h in handles]
            candidates=[estimates[0],estimates[1],mixture-estimates[2]]
            voice_ratio=10*np.log10((np.sum(estimates[0]**2)+1e-20)/(np.sum(mixture**2)+1e-20))
            is_low=bool(voice_ratio<-32);lowvoice_count+=int(is_low)
            row={'start':start/rate,'voice_activity_model_relative_db':float(voice_ratio),'low_voice_model_window':is_low,'systems':{}}
            src_s=spectrum(mixture,rate);freq=np.fft.rfftfreq(2048,1/rate)
            for key,preset in [('v1',PRESET),('v2',PRESET_V2)]:
                wave=files[key].read(len(mixture),dtype='float64',always_2d=True)
                assert wave.shape==mixture.shape and np.isfinite(wave).all()
                expected=mixture-sum(m['weight']*candidate for m,candidate in zip(preset['models'],candidates))
                max_errors[key]=max(max_errors[key],float(np.max(np.abs(expected-wave))))
                power=spectrum(wave,rate);bands={}
                for band,(lo,hi) in BANDS.items():
                    mask=(freq>=lo)&(freq<hi);a=src_s[:,mask];b=power[:,mask];difference=b-a
                    values=np.array([np.sum(a*a),np.sum(b*b),np.sum(np.minimum(difference,0)**2),np.sum(np.maximum(difference,0)**2)])
                    sums[key][band]+=values
                    if is_low:lowvoice[key][band]+=values
                    # Flux of band-energy envelope: diagnostic of timing/attacks,
                    # but mixture includes vocals, so this isn't drum fidelity.
                    ea=np.sqrt(np.sum(a*a,axis=(0,1)));eb=np.sqrt(np.sum(b*b,axis=(0,1)))
                    fa=np.maximum(np.diff(ea),0);fb=np.maximum(np.diff(eb),0)
                    bands[band]={'output_to_mixture_power_db':float(10*np.log10(max(values[1],1e-30)/max(values[0],1e-30))),
                        'positive_flux_relative_error':float(np.linalg.norm(fa-fb)/max(np.linalg.norm(fa),1e-15))}
                row['systems'][key]=bands
            report['windows'].append(row)
    finally:
        for h in handles+list(files.values()):h.close()
    report['low_voice_window_count']=lowvoice_count
    for scope,data in [('whole_record_mixture_comparison',sums),('model_selected_low_voice_windows',lowvoice)]:
        report['band_summary'][scope]={}
        for key in paths:
            report['band_summary'][scope][key]={}
            for band,values in data[key].items():
                report['band_summary'][scope][key][band]={
                    'output_to_mixture_power_db':float(10*np.log10(max(values[1],1e-30)/max(values[0],1e-30))),
                    'spectral_deficit_relative_to_mixture':float(values[2]/max(values[0],1e-30)),
                    'spectral_excess_relative_to_mixture':float(values[3]/max(values[0],1e-30))}
    for key,path in paths.items():
        report['systems'][key]={'file':str(path),'sha256':digest(path),
            'reconstruction_from_original_model_estimates_max_abs_error':max_errors[key]}
        assert max_errors[key]<2e-6
        for start,end in [(40,56),(80,96),(140,156),(220,236)]:
            wave,_=sf.read(path,start=start*rate,stop=end*rate,always_2d=True)
            sf.write(OUT/f'Ezo_{key.upper()}_{start}_{end}.wav',wave,rate,subtype='FLOAT')
    report['interpretation']='Band deficit relative to the mixture includes desired vocal removal. Low-voice windows are selected by Viper, not verified isolated music. Flux is a mixture-envelope proxy, not isolated kick/snare/bass fidelity. A smaller difference to the source can also mean more retained voice. Full-record Viper vocal probes reuse a model in both ensembles and are biased diagnostics, not independent ground truth.'
    save=lambda:(OUT/'comparison.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    save();print('WAVEFORM AND BAND CHECK DONE',max_errors,'lowvoice windows',lowvoice_count,flush=True)
    del original
    # No replay: this diagnostic runs the network for both full outputs.
    separation_checkpoint.attach_checkpoint=lambda *args,**kwargs:None
    for key,path in paths.items():
        idle();wave,_=sf.read(path,dtype='float64',always_2d=True)
        h=.25/max(1.,float(np.max(np.abs(wave))));prepared=WORK/f'{key}_probe_input.wav'
        sf.write(prepared,wave*h,rate,subtype='FLOAT');last=[-1]
        def progress(p,m):
            step=int(p*10)
            if step>last[0]:print(key,'VOCAL PROBE',round(p*100),m,flush=True);last[0]=step
        started=time.monotonic()
        estimate=run_model_estimate(core,prepared,PRESET['models'][0],WORK,rate,len(wave),len(wave),h,progress)
        sf.write(OUT/f'Ezo_{key.upper()}_Estimated_Residual_Voice.wav',estimate,rate,subtype='FLOAT')
        windows=[]
        for start in range(0,len(wave),rate):
            rms=np.sqrt(np.mean(estimate[start:start+rate]**2))
            windows.append({'start':start/rate,'estimated_vocal_rms_dbfs':float(20*np.log10(max(rms,1e-12)))})
        report['systems'][key]['vocal_probe']={'model':PRESET['models'][0]['model_key'],
            'seconds_to_process':time.monotonic()-started,'independent_from_ensemble':False,
            'estimated_vocal_rms_dbfs':float(20*np.log10(max(float(np.sqrt(np.mean(estimate**2))),1e-12))),
            'windows':windows,'highest_estimated_windows':sorted(windows,key=lambda row:row['estimated_vocal_rms_dbfs'],reverse=True)[:8]}
        save();del wave,estimate
    print('FULL AUDIT DONE',str(OUT/'comparison.json'),flush=True)


if __name__=='__main__':main()
