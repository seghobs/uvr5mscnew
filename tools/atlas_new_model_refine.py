"""First opened confirmation is now development; never reuses it as holdout."""
from tools import atlas_new_mix_screen as s,atlas_new_models as n,atlas_alternative_screen as a
from tools.atlas_benchmark import write_json

def setup():
    s.WORK=n.WORK/'round_two'

def fit():
    first=a.read(n.WORK/'confirmation/validation.json')
    if first['accepted']:raise RuntimeError('First confirmation passed; do not retune a passing recipe here')
    tracks=a.read(n.WORK/'plan.json')['development']+a.read(n.WORK/'confirmation/validation_manifest.json')['tracks']
    setup()
    write_json(s.WORK/'plan.json',{'development':tracks,'acceptance':a.read(n.WORK/'acceptance.json'),
        'reason':'The first eight opened scores are explicitly development, not independent evidence. Target 5% lower vocal excess, both deficits 1% lower, instrumental excess 1% lower; stronger regularization 0.01.'})
    # Keep the original pool screen as history; it is not recomputed or relabelled.
    write_json(s.WORK/'screening.json',{'first_development_screen':str(n.WORK/'screening.json'),
        'first_confirmation_rejected':True,'round_two_method':'Full-resolution constrained refit, 24 development recordings.'})
    initial=a.read(n.WORK/'fit/frozen.json')['selected']['weights']
    s.fit(regularizations=(.01,),maxiter=100,initial_weights=initial,ftol=1e-8,content_margin=(.99,.95,.99,.99))

def confirm():
    setup()
    if not a.read(s.WORK/'development_projection.json')['safe']:
        raise RuntimeError('Development crosstalk gate failed')
    s.confirm(confirmation_size=16)

def shrinkage():
    import numpy as np
    from atlas_band_ensemble import combine_frequency
    from tools import atlas_refinement as r
    from tools.atlas_sdr_optimize import score,summary,eligible
    from threadpoolctl import threadpool_limits
    setup();plan=a.read(s.WORK/'plan.json')
    first=a.read(n.WORK/'fit/frozen.json');indices=s.BASE_INDICES+[item[0] for item in n.EXPERTS]
    prior=np.array(first['baseline_preset']['frequency_weights']['weights']);chosen=np.array(first['selected']['weights'])
    baseline=[];rows={alpha:[] for alpha in (.1,.25,.4,.55,.7,.85,1.)}
    leakbase=[];leaks={alpha:[] for alpha in rows}
    with threadpool_limits(limits=1):
        for track in plan['development']:
            ref,x=r.load(track,indices)
            current=combine_frequency(ref['source'],list(x),first['baseline_preset']['frequency_weights'])[0]
            candidate=combine_frequency(ref['source'],list(x),{'anchors_hz':first['baseline_preset']['frequency_weights']['anchors_hz'],'weights':chosen})[0]
            baseline.append(score(ref,current));leakbase.append(s.reference_leakage(ref,current))
            for alpha in rows:
                wave=current+alpha*(candidate-current)
                rows[alpha].append(score(ref,wave));leaks[alpha].append(s.reference_leakage(ref,wave))
            print('SHRINKAGE',track['name'],flush=True)
    base=summary(baseline);trials=[]
    for alpha,values in rows.items():
        metrics=summary(values)
        safe=eligible(metrics,base) and all(np.mean([row[stem] for row in leaks[alpha]])<=np.mean([row[stem] for row in leakbase])+1e-10 for stem in ('vocal','instrumental'))
        group_safe=all(eligible(summary(values[part]),summary(baseline[part])) for part in (slice(0,16),slice(16,None)))
        trials.append({'alpha':alpha,'eligible':bool(safe and group_safe),'full_development':metrics,
            'development_mean_sdr_gain_db':metrics['vocal']['sdr_db']-base['vocal']['sdr_db'],
            'weights':(prior+alpha*(chosen-prior)).tolist(),'both_development_groups_safe':bool(group_safe)})
    eligible_trials=[trial for trial in trials if trial['eligible']]
    selected=max(eligible_trials,key=lambda trial:trial['development_mean_sdr_gain_db']) if eligible_trials else None
    write_json(s.WORK/'shrinkage/frozen.json',{'baseline_preset':first['baseline_preset'],
        'preset_sha256':first['preset_sha256'],'development_ids':[track['id'] for track in plan['development']],
        'baseline_summary':base,'trials':trials,'selected':selected,'method':'Conservative residual shrinkage; previously opened confirmation is development; each development group and reference-projection proxies must remain safe.'})
    print('SHRINKAGE SELECTED',None if selected is None else selected['alpha'],flush=True)

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('phase',choices=['fit','confirm','shrinkage'])
    globals()[parser.parse_args().phase]()
