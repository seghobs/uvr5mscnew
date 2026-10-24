"""Summarize the completed paired audit without inventing reference fidelity."""
import json
from pathlib import Path
import numpy as np
import soundfile as sf

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'outputs/Ezo_V1_V2_Music_Comparison'


def main():
    path=OUT/'comparison.json';report=json.loads(path.read_text(encoding='utf8'))
    assert all('vocal_probe' in report['systems'][k] for k in ('v1','v2'))
    summary={}
    for scope,windows in [('all_windows',report['windows']),
                          ('model_selected_low_voice_windows',[w for w in report['windows'] if w['low_voice_model_window']]),
                          ('selected_solo_140_156',[w for w in report['windows'] if 140<=w['start']<156])]:
        summary[scope]={'window_count':len(windows),'positive_flux_relative_error_mean':{
            key:{band:float(np.mean([w['systems'][key][band]['positive_flux_relative_error'] for w in windows]))
                 for band in windows[0]['systems'][key]} for key in ('v1','v2')}}
    report['transient_summary']=summary
    report['asr_diagnostics']={}
    for key in ('v1','v2'):
        data=json.loads((ROOT/f'cache/ezo_karaoke/asr_current_{key}.json').read_text(encoding='utf8'))
        report['asr_diagnostics'][key]=[
            {'start':c['start'],'end':c['end'],'recognized_token_count':len(c['tokens']),
             'matching_reference_token_count':c.get('matching_reference_token_count'),
             'usable_lyric_reference':c.get('usable_lyric_reference')} for c in data['clips']]
    with sf.SoundFile(report['systems']['v1']['file']) as first,sf.SoundFile(report['systems']['v2']['file']) as second:
        energies=np.zeros(3);peak=0.
        while True:
            a=first.read(262144,always_2d=True)
            if not len(a):break
            b=second.read(len(a),always_2d=True);difference=b-a
            energies+=np.array([np.sum(a*a),np.sum(b*b),np.sum(difference*difference)])
            peak=max(peak,float(np.max(np.abs(difference))))
    report['paired_difference']={'v2_to_v1_power_db':float(10*np.log10(energies[1]/energies[0])),
        'difference_energy_relative_to_v1':float(energies[2]/energies[0]),'max_abs_sample_difference':peak,
        'is_music_loss_measurement':False}
    v1=report['systems']['v1']['vocal_probe']['estimated_vocal_rms_dbfs']
    v2=report['systems']['v2']['vocal_probe']['estimated_vocal_rms_dbfs']
    report['vocal_probe_comparison']={'v1_dbfs':v1,'v2_dbfs':v2,'v2_minus_v1_db':v2-v1,
        'lower_estimate':'v2' if v2<v1 else 'v1','is_true_leakage_measurement':False,
        'both_contain_nonzero_model_estimated_voice':True}
    report['conclusions']={
        'music':'V2 is slightly closer to the source mixture in the model-selected low-voice windows for band deficit and positive spectral flux. Bass differences are extremely small. This does not establish audible superiority or isolated drum/bass fidelity.',
        'vocals':'Full-record Viper estimates are nonzero for both. Viper belongs to both ensembles, can label instruments as voice, and cannot prove actual vocal leakage. ASR matches none of the original lyrics in the three usable clips for either version; no ASR winner.',
        'reference_limitation':'No isolated original instrumental, drums, bass or vocals; no true fidelity winner, SDR or zero-leakage guarantee. No perceptual listening was performed. No preset was changed during this comparison.'}
    path.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    brief={key:report[key] for key in ('seconds','paired_difference','vocal_probe_comparison','asr_diagnostics','conclusions')}
    (OUT/'summary.json').write_text(json.dumps(brief,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps(brief,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
