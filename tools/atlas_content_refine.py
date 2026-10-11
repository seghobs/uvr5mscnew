"""Content-focused development refit against the current nine-expert preset.

Previously opened confirmations are development only. Never alters production.
"""
from pathlib import Path
import sys
import argparse
import hashlib
from datetime import datetime, timezone
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from tools import atlas_alternative_screen as a, atlas_sdr_optimize as optimizer
from tools.atlas_benchmark import write_json
WORK=ROOT/'cache/atlas_content_refine'

def passes_content_confirmation(result):
    return bool(result['accepted'] and all(
        result['summary']['candidate'][s]['spectral_deficit']<=.99*result['summary']['current'][s]['spectral_deficit']
        for s in ('vocal','instrumental')))

def passes_robust_confirmation(result):
    return bool(passes_content_confirmation(result) and result['bootstrap_97_5pct'][0]>0)

def run_fit(margin,folder,maxiter=60,full=False):
    development=a.tracks()+a.read(a.WORK/'validation_manifest.json')['tracks']+a.read(a.WORK/'round_two/validation_manifest.json')['tracks']
    if folder=='constrained_fit_robust':
        if not (WORK/'validation.json').exists():raise RuntimeError('First confirmation must be explicitly opened before reclassification')
        development+=a.read(WORK/'validation_manifest.json')['tracks']
    indices=[0,1,2,4,7,8,9,10,11]
    original=optimizer.read
    def read(path):
        value=original(path)
        if path.name=='manifest.json':
            value['development']=development
            value['candidate_indices']=indices
        return value
    write_json(WORK/(folder+'_plan.json'),{'tracks':development,'content_margin':margin,
        'reason':f'All {len(development)} previously scored recordings are development, never independent confirmation. Both deficits targeted together; no excess/SI-SDR regressions.'})
    optimizer.read=read
    optimizer.WORK=WORK/folder
    # Small matrix operations suffer from oversized BLAS thread pools.
    from threadpoolctl import threadpool_limits
    try:
        with threadpool_limits(limits=1):
            optimizer.main(content_margin=margin,maxiter=maxiter,spectral_stride=1 if full else 4,
                regularizations=(.01,) if full else (.0001,.001,.01))
    finally:optimizer.read=original

def fit():run_fit([.98,.995,.98,.995],'constrained_fit')

def fit_soft():run_fit([.995,1.,.995,1.],'constrained_fit_soft')

def fit_balanced():run_fit([.995,1.,.995,.99],'constrained_fit_balanced',100)

def fit_full():run_fit([.995,.995,.995,.995],'constrained_fit_full',60,True)

def fit_robust():run_fit([.99,.98,.99,.995],'constrained_fit_robust',100,True)

def infer_robust():
    frozen=a.read(WORK/'constrained_fit_robust/frozen.json')
    if not frozen['selected']:
        write_json(ROOT/'docs/atlas-studio-v2-content-refinement-round-two.json',{'date':'2026-10-11',
            'development':a.read(WORK/'constrained_fit_robust_plan.json'),'selected_fit':frozen,
            'accepted':False,'production_changed':False,'reason':'No eligible full-resolution development candidate; no further confirmation inference performed.'})
        print('ROBUST FIT REJECTED; PRODUCTION PRESERVED',flush=True)
        return
    target=WORK/'round_two'
    if not (target/'constrained_fit/frozen.json').exists():
        write_json(target/'constrained_fit/frozen.json',frozen)
        write_json(target/'confirmation_plan.json',{'frozen_at':datetime.now(timezone.utc).isoformat(),
            'acceptance':'Positive paired 97.5% SDR interval, both SI-SDR/excess no worse, both deficits at least 1% lower.',
            'baseline_sha256':frozen['preset_sha256'],'weights':frozen['selected']['weights']})
    a.WORK=target
    a.validate_infer()
    manifest=a.read(target/'validation_manifest.json');manifest['candidate_indices']=[0,1,2,4,7,8,9,10,11]
    write_json(target/'validation_manifest.json',manifest)

def evaluate_robust():
    from tools import atlas_sdr_validate as v
    target=WORK/'round_two';frozen=a.read(target/'constrained_fit/frozen.json')
    if hashlib.sha256((ROOT/'frontend/src/lib/atlas-studio-v2-preset.json').read_bytes()).hexdigest()!=frozen['preset_sha256']:
        raise RuntimeError('Production baseline changed')
    v.WORK=target
    if not (target/'frozen.json').exists():write_json(target/'frozen.json',frozen)
    v.evaluate()
    result=a.read(target/'validation.json')
    import numpy as np
    delta=np.array([row['systems']['candidate']['vocal']['sdr_db']-row['systems']['current']['vocal']['sdr_db'] for row in result['rows']])
    result['bootstrap_97_5pct']=np.quantile(np.random.default_rng(20261011).choice(delta,(10000,len(delta)),replace=True).mean(axis=1),[.0125,.9875]).tolist()
    result['accepted']=passes_robust_confirmation(result)
    result['production_changed']=False
    write_json(target/'validation.json',result)
    write_json(ROOT/'docs/atlas-studio-v2-content-refinement-round-two.json',{'date':'2026-10-11','acceptance_kind':'content_preservation',
        'development':a.read(WORK/'constrained_fit_robust_plan.json'),'selected_fit':frozen,
        'confirmation_plan':a.read(target/'confirmation_plan.json'),'confirmation_manifest':a.read(target/'validation_manifest.json'),
        'confirmation':result})
    print('ROBUST CONFIRMATION ACCEPTED',result['accepted'],flush=True)

def choose():
    if (WORK/'confirmation_plan.json').exists():
        raise RuntimeError('Confirmation already frozen; do not change development selection')
    attempts={name:a.read(WORK/name/'frozen.json') for name in ('constrained_fit','constrained_fit_soft','constrained_fit_balanced','constrained_fit_full')}
    eligible=[(name,data) for name,data in attempts.items() if data['selected']]
    write_json(WORK/'attempts.json',attempts)
    if not eligible:
        write_json(ROOT/'docs/atlas-studio-v2-content-refinement.json',{'date':'2026-10-11','attempts':attempts,
            'accepted':False,'production_changed':False,'reason':'No full-resolution eligible development candidate; no fresh confirmation performed.',
            'limitations':['Bounded optimization attempts do not prove improvement is impossible.','Two earlier uncompleted runs interrupted to adjust computation settings; no scores claimed.']})
        print('NO ELIGIBLE DEVELOPMENT CANDIDATE',flush=True)
        return
    name,frozen=max(eligible,key=lambda pair:pair[1]['selected']['full_development']['vocal']['sdr_db'])
    write_json(WORK/'constrained_fit/frozen.json',frozen)
    write_json(WORK/'development_plan.json',a.read(WORK/(name+'_plan.json')))
    print('FROZEN',name,flush=True)

def infer():
    frozen=a.read(WORK/'constrained_fit/frozen.json')
    if not frozen['selected']:raise RuntimeError('No eligible development fit; production preserved')
    plan=WORK/'confirmation_plan.json'
    if not plan.exists():
        write_json(plan,{'acceptance':'Positive paired 95% SDR interval, both mean SI-SDR and excess no worse, both mean deficits at least 1% lower.',
            'frozen_at':datetime.now(timezone.utc).isoformat(),
            'baseline_sha256':frozen['preset_sha256'],'weights':frozen['selected']['weights']})
    a.WORK=WORK
    a.validate_infer()
    manifest=a.read(WORK/'validation_manifest.json')
    manifest['candidate_indices']=[0,1,2,4,7,8,9,10,11]
    write_json(WORK/'validation_manifest.json',manifest)

def evaluate():
    from tools import atlas_sdr_validate as v
    frozen=a.read(WORK/'constrained_fit/frozen.json')
    if hashlib.sha256((ROOT/'frontend/src/lib/atlas-studio-v2-preset.json').read_bytes()).hexdigest()!=frozen['preset_sha256']:
        raise RuntimeError('Production baseline changed')
    v.WORK=WORK
    # The shared evaluator expects the frozen fit at the experiment root.
    target=WORK/'frozen.json'
    if not target.exists():write_json(target,frozen)
    v.evaluate()
    result=a.read(WORK/'validation.json')
    result['content_target_passed']=all(result['summary']['candidate'][s]['spectral_deficit']<=.99*result['summary']['current'][s]['spectral_deficit'] for s in ('vocal','instrumental'))
    result['accepted']=passes_content_confirmation(result)
    result['production_changed']=False
    write_json(WORK/'validation.json',result)
    write_json(ROOT/'docs/atlas-studio-v2-content-refinement.json',{'date':'2026-10-11','development':a.read(WORK/'development_plan.json'),
        'attempts':a.read(WORK/'attempts.json'),'selected_fit':frozen,
        'confirmation_plan':a.read(WORK/'confirmation_plan.json'),
        'confirmation_manifest':a.read(WORK/'validation_manifest.json'),'confirmation':result})
    print('CONTENT CONFIRMATION ACCEPTED',result['accepted'],flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('phase',choices=['fit','fit_soft','fit_balanced','fit_full','fit_robust','infer_robust','evaluate_robust','choose','infer','evaluate'])
    globals()[parser.parse_args().phase]()
