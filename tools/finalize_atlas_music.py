"""Promote the frozen candidate only if the recorded acceptance gates pass."""
import json
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[1]


def read(path):return json.loads((ROOT/path).read_text(encoding='utf8'))
def write(path,value):(ROOT/path).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf8')


def main():
    fit=read('cache/atlas_music_fit/report.json')
    ezo=read('outputs/Ezo_Music_Refined/candidate-report.json')
    old=read('frontend/src/lib/atlas-studio-v2-preset.json')
    v1path='frontend/src/lib/atlas-studio-preset.json'
    assert read(v1path)==json.loads(subprocess.check_output(['git','show','HEAD:'+v1path],cwd=ROOT,text=True,encoding='utf8'))
    before=fit['summary']['test']['previous_v2'];after=fit['summary']['test']['frequency_candidate']
    components=read('cache/atlas_music_fit/component-report.json')
    checks={'reference_sdr_improves':after['sdr_db']>before['sdr_db']}
    for metric in ('drum_gain_squared_error','bass_gain_squared_error'):
        checks['reference_'+metric]=components['summary']['refined'][metric]<components['summary']['previous_v2'][metric]
    for metric in ('spectral_deficit','spectral_excess','vocal_leakage','artifact_residual',
                   'bass_complex_error','bass_flux_error','body_complex_error','body_flux_error','attack_complex_error','attack_flux_error'):
        checks['reference_'+metric]=after[metric]<before[metric]
    for band,data in ezo['low_voice_windows']['refined'].items():
        for metric,value in data.items():checks['ezo_'+band+'_'+metric]=value<=ezo['low_voice_windows']['previous_v2'][band][metric]
    checks['ezo_vocal_model_estimate_not_increased']=ezo['vocal_probe']['estimated_voice_dbfs']<=ezo['vocal_probe']['previous_v2_dbfs']
    checks['ezo_no_peak_overload']=ezo['peak']<1.
    checks['ezo_pair_sum']=ezo['source_sum_max_error']<1e-6
    asr=read('cache/ezo_karaoke/asr_refined_v2.json')
    checks['asr_no_new_reference_matches']=all(c['matching_reference_token_count']==0 for c in asr['clips'] if c['usable_lyric_reference'])
    report={'acceptance_plan':read('cache/atlas_music_fit/acceptance-plan.json'),'checks':checks,
        'accepted':all(checks.values()),'isolated_reference_stems_available':False,
        'zero_leakage_verified':False,'true_instrumental_sdr_db':None,
        'true_music_fidelity_improvement_verified':False,'perceptual_listening_performed':False,
        'distinct_separation_models':3,'full_inference_passes':3,'secondary_vocal_subtraction':False,
        'reference':fit,'reference_components':components,'ezo':ezo,'rejected_consensus':read('cache/atlas_music_fit/consensus-report.json'),
        'asr_summary':[{'start':c['start'],'usable_reference':c['usable_lyric_reference'],
                        'matching_reference_token_count':c['matching_reference_token_count']} for c in asr['clips']],
        'scope':'Only a small previously reused reference pool and one Ezo recording. Numerical improvements do not establish clear audible superiority or true Ezo drum/bass fidelity. Historical Ezo and earlier V2 reports do not describe this recipe.'}
    if not report['accepted']:
        write('cache/atlas_music_fit/rejected-final-report.json',report)
        raise RuntimeError('Candidate failed: '+str([k for k,v in checks.items() if not v]))
    preset={**old,'revision':'three-model-smooth-music-v2','frequency_weights':fit['frequency_weights'],
        'validation':{'status':'local_reference_and_ezo_checks_passed',
            'report':'docs/atlas-studio-v2-refined-check.json',
            'scope':'Same three models and three passes. Smooth frequency-dependent mixture fitted on eight development excerpts, evaluated on eight previously reused local reference excerpts and Ezo proxies. No isolated Ezo reference stems or listening test; no zero-loss, zero-leakage or clear audible superiority claim.'}}
    report['selected_preset']=preset
    write('docs/atlas-studio-v2-refined-check.json',report)
    write('frontend/src/lib/atlas-studio-v2-preset.json',preset)
    print('PROMOTED',preset['revision'],'checks',len(checks))


if __name__=='__main__':main()
