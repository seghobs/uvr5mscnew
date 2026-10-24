"""Recompute the final V1/V2 pair audit from actual WAVs; do not fit or change presets."""
import hashlib
import json
from pathlib import Path
import sys
import numpy as np
import soundfile as sf
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from atlas_studio import PRESET,PRESET_V2,combine
from atlas_band_ensemble import spectrum


def digest(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as file:
        for block in iter(lambda:file.read(1024*1024),b''):h.update(block)
    return h.hexdigest()


def reduction(before,after):return float(100*(1-after/max(before,1e-30)))


def main():
    prior=json.loads((ROOT/'outputs/Ezo_V1_V2_Music_Comparison/comparison.json').read_text(encoding='utf8'))
    historical=json.loads((ROOT/'docs/atlas-studio-v2-ezo-check.json').read_text(encoding='utf8'))
    candidate=json.loads((ROOT/'outputs/Ezo_Music_Refined/candidate-report.json').read_text(encoding='utf8'))
    assert PRESET_V2['revision']=='three-model-smooth-music-v2'
    assert candidate['frequency_weights']==PRESET_V2['frequency_weights']
    source=Path(historical['source']);wave,rate=sf.read(source,always_2d=True)
    assert digest(source)==prior['source_sha256']==historical['source_sha256']
    paths={'v1':Path(prior['systems']['v1']['file']),
           'new_v2':ROOT/'outputs/Ezo_Music_Refined/Ezo_V2_Refined_Instrumental.wav'}
    h=.25/max(1.,float(np.max(np.abs(wave))));capture=ROOT/'cache/ezo_karaoke/captured'
    patterns=['atlas_input_(Vocals)_model_bs*','atlas_input_(vocals)_mel_band_roformer_kim_ft2*','atlas_input_(Instrumental)_melband_roformer_inst_v2*']
    estimates=[]
    for pattern in patterns:
        matches=list(capture.glob(pattern));assert len(matches)==1
        x,sr=sf.read(matches[0],always_2d=True);assert sr==rate and x.shape==wave.shape
        estimates.append(x/h)
    report={'song':source.name,'seconds':len(wave)/rate,'source_sha256':digest(source),
        'presets':{'v1':PRESET,'new_v2':PRESET_V2},'new_neural_inference_run':False,
        'methods':'Fresh waveform reconstruction and spectral/attack measurements from actual full WAVs. Re-measure stored full-length vocal-network outputs, checking the probe inputs against each instrumental.',
        'isolated_ezo_reference_stems_available':False,'true_music_loss_percentage':None,
        'true_drum_loss_percentage':None,'true_bass_loss_percentage':None,
        'true_vocal_leakage_percentage':None,'perceptual_listening_performed':False,'systems':{}}
    outputs={}
    for key,preset in [('v1',PRESET),('new_v2',PRESET_V2)]:
        _,expected=combine(wave,estimates,preset)
        x,sr=sf.read(paths[key],always_2d=True)
        assert sr==rate and x.shape==wave.shape and np.isfinite(x).all()
        error=float(np.max(np.abs(expected-x)));assert error<1e-6
        outputs[key]=x
        report['systems'][key]={'file':str(paths[key]),'sha256':digest(paths[key]),
            'preset_reconstruction_max_abs_error':error,'frames':len(x),'sample_rate':sr,
            'peak':float(np.max(np.abs(x))),'rms_dbfs':float(20*np.log10(np.sqrt(np.mean(x*x))))}
        print('VERIFIED',key,error,flush=True)
    del estimates,expected
    bands={'bass_20_250':(20,250),'body_250_1000':(250,1000),'attack_1000_10000':(1000,10000)}
    totals={scope:{key:{band:np.zeros(6) for band in bands} for key in outputs} for scope in ('full_record','fixed_39_low_voice_seconds')}
    low_seconds={round(w['start']) for w in prior['windows'] if w['low_voice_model_window']}
    assert len(low_seconds)==39
    freq=np.fft.rfftfreq(2048,1/rate)
    for start in range(0,len(wave),rate):
        end=min(len(wave),start+rate);original=np.abs(spectrum(wave[start:end]))
        scopes=['full_record']+(['fixed_39_low_voice_seconds'] if start//rate in low_seconds else [])
        for key,x in outputs.items():
            rendered=np.abs(spectrum(x[start:end]))
            for band,(lo,hi) in bands.items():
                mask=(freq>=lo)&(freq<hi);a=original[:,mask];b=rendered[:,mask]
                af=np.maximum(np.diff(np.sqrt(np.sum(a*a,axis=(0,1)))),0)
                bf=np.maximum(np.diff(np.sqrt(np.sum(b*b,axis=(0,1)))),0)
                values=np.array([np.sum(np.maximum(a-b,0)**2),np.sum(a*a),
                    np.sum((af-bf)**2),np.sum(af*af),np.sum(b*b),np.sum(np.maximum(b-a,0)**2)])
                for scope in scopes:totals[scope][key][band]+=values
    report['spectral_and_attack_diagnostics']={}
    for scope,systems in totals.items():
        result={}
        for band in bands:
            result[band]={}
            for key in outputs:
                s=systems[key][band]
                result[band][key]={'normalized_squared_magnitude_deficit':float(s[0]/s[1]),
                    'positive_spectral_flux_error':float(s[2]/s[3]),
                    'output_to_mixture_band_power_db':float(10*np.log10(s[4]/s[1])),
                    'normalized_squared_magnitude_excess':float(s[5]/s[1])}
            result[band]['deficit_metric_reduction_percent']=reduction(result[band]['v1']['normalized_squared_magnitude_deficit'],result[band]['new_v2']['normalized_squared_magnitude_deficit'])
            result[band]['flux_error_reduction_percent']=reduction(result[band]['v1']['positive_spectral_flux_error'],result[band]['new_v2']['positive_spectral_flux_error'])
        report['spectral_and_attack_diagnostics'][scope]=result
    probes={'v1':(ROOT/'cache/ezo_music_audit/v1_probe_input.wav',ROOT/'outputs/Ezo_V1_V2_Music_Comparison/Ezo_V1_Estimated_Residual_Voice.wav'),
            'new_v2':(ROOT/'cache/atlas_music_fit/ezo_refined_probe_input.wav',ROOT/'outputs/Ezo_Music_Refined/Ezo_Refined_Estimated_Residual_Voice.wav')}
    for key,(input_path,estimate_path) in probes.items():
        x=outputs[key];ph=.25/max(1.,float(np.abs(x).max()))
        prepared,sr=sf.read(input_path,always_2d=True)
        assert sr==rate and prepared.shape==x.shape
        probe_error=float(np.max(np.abs(prepared-x*ph)));assert probe_error<1e-6
        estimate,sr=sf.read(estimate_path,always_2d=True)
        assert sr==rate and estimate.shape==x.shape and np.isfinite(estimate).all()
        rms=float(np.sqrt(np.mean(estimate**2)));windows=[]
        for start in range(0,len(x),rate):
            piece=estimate[start:start+rate]
            windows.append({'start':start/rate,'rms_dbfs':float(20*np.log10(max(float(np.sqrt(np.mean(piece**2))),1e-12)))})
        report['systems'][key]['vocal_model_probe']={'model':PRESET['models'][0]['model_key'],
            'independent_from_presets':False,'input_match_max_abs_error':probe_error,
            'estimated_voice_rms_dbfs':float(20*np.log10(rms)),
            'estimated_voice_energy':float(np.sum(estimate**2)),'estimate_sha256':digest(estimate_path),
            'windows':windows,'highest_windows':sorted(windows,key=lambda r:r['rms_dbfs'],reverse=True)[:8]}
    a=report['systems']['v1']['vocal_model_probe'];b=report['systems']['new_v2']['vocal_model_probe']
    report['vocal_model_comparison']={'v1_estimated_voice_dbfs':a['estimated_voice_rms_dbfs'],
        'new_v2_estimated_voice_dbfs':b['estimated_voice_rms_dbfs'],
        'estimate_drop_db':a['estimated_voice_rms_dbfs']-b['estimated_voice_rms_dbfs'],
        'estimated_component_energy_reduction_percent':reduction(a['estimated_voice_energy'],b['estimated_voice_energy']),
        'actual_vocal_leakage_reduction_verified':False,
        'seconds_with_lower_estimated_voice_in_new_v2':sum(y['rms_dbfs']<x['rms_dbfs'] for x,y in zip(a['windows'],b['windows']))}
    report['asr_comparison']={}
    for key,label in [('v1','current_v1'),('new_v2','refined_v2')]:
        asr=json.loads((ROOT/f'cache/ezo_karaoke/asr_{label}.json').read_text(encoding='utf8'))
        report['asr_comparison'][key]=[{'start':c['start'],'usable_reference':c['usable_lyric_reference'],
            'matching_reference_token_count':c['matching_reference_token_count']} for c in asr['clips']]
    report['limits']='Magnitude deficit is squared spectral difference, not missing instrument energy. Flux measures mixture-envelope changes, not isolated drums. Whole-record mixture deficits include desired voice removal. Low-voice seconds are model-selected and biased. Stored Viper estimates reuse an ensemble model and can include instruments. ASR non-recognition is not absence of voice. No actual Ezo loss percentages, true SDR or zero-leakage result can be established.'
    dest=ROOT/'outputs/Ezo_Music_Refined/v1-vs-final-v2-recheck.json'
    dest.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps({'low_voice':report['spectral_and_attack_diagnostics']['fixed_39_low_voice_seconds'],
                     'vocal':report['vocal_model_comparison'],'report':str(dest)},indent=2),flush=True)


if __name__=='__main__':main()
