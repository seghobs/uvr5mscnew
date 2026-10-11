"""Compare new experts and signal-dependent blends against the deployed V2."""
import json
from pathlib import Path
import sys
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from tools import atlas_alternative_screen as a, atlas_refinement as r
from tools.atlas_sdr_optimize import score,summary,eligible
from tools.atlas_benchmark import write_json
from atlas_band_ensemble import spectrum,combine_frequency
from tools.atlas_new_models import WORK,EXPERTS

BASE_INDICES=[0,1,2,4,7,8,9,10,11]

def development():return a.read(WORK/'plan.json')['development']

def reference_leakage(ref,wave):
    """Instantaneous two-reference projection; a crosstalk proxy, not BSS Eval SDR."""
    result={}
    for stem,other,estimate in [('vocal','instrumental',wave),('instrumental','vocal',ref['source']-wave)]:
        target=ref[stem].ravel();opposite=ref[other].ravel();estimate=estimate.ravel()
        gram=np.array([[target@target,target@opposite],[opposite@target,opposite@opposite]])
        coefficients=np.linalg.lstsq(gram,np.array([target@estimate,opposite@estimate]),rcond=None)[0]
        result[stem]=float(coefficients[1]**2*gram[1,1]/max(gram[0,0],1e-12))
    return result

def proposed_spectra(center,experts,source):
    """No ground-truth-dependent decisions; retain complex phase in consensus."""
    pool=np.concatenate([center[None],experts],axis=0)
    distance=np.abs(pool-center[None])
    scale=np.median(distance,axis=0)+1e-12
    proposals={'new_mean':experts.mean(axis=0),
        'complex_median':np.median(pool.real,axis=0)+1j*np.median(pool.imag,axis=0),
        'magnitude_median':np.median(np.abs(pool),axis=0)*np.exp(1j*np.angle(center))}
    for power in (1,2):
        confidence=1/(1+(distance/scale[None])**power)
        proposals[f'disagreement_{power}']=(pool*confidence).sum(axis=0)/confidence.sum(axis=0)
    # Reject gross inter-expert disagreement smoothly instead of taking max magnitude.
    proposals['conservative_consensus']=center+(experts.mean(axis=0)-center)*np.exp(-np.std(np.abs(experts),axis=0)/(np.abs(center)+1e-9))
    # Mix consistency projection distributes the residual with source-independent energy weights.
    vocal=experts[0];inst=source-experts[1]
    residual=source-vocal-inst
    energy=np.abs(vocal)**2/(np.abs(vocal)**2+np.abs(inst)**2+1e-12)
    proposals['energy_consistency']=vocal+residual*energy
    return proposals

def screen():
    preset=a.read(ROOT/'frontend/src/lib/atlas-studio-v2-preset.json')
    indices=BASE_INDICES+[item[0] for item in EXPERTS]
    rows={};baseline=[]
    for track in development():
        ref,x=r.load(track,indices)
        current=combine_frequency(ref['source'],list(x[:len(BASE_INDICES)]),preset['frequency_weights'])[0]
        baseline.append(score(ref,current))
        z=np.stack([spectrum(w) for w in x[len(BASE_INDICES):]])
        proposals=proposed_spectra(spectrum(current),z,spectrum(ref['source']))
        alternatives={name:a.reconstruct(value,len(current)) for name,value in proposals.items()}
        alternatives.update({f'expert_{index}':wave for index,wave in zip(indices[len(BASE_INDICES):],x[len(BASE_INDICES):])})
        for name,wave in alternatives.items():
            for alpha in (.025,.05,.1,.2,.4,.7,1.):
                rows.setdefault(f'{name}:{alpha}',[]).append(score(ref,current*(1-alpha)+wave*alpha))
        print('SCREENED',track['name'],flush=True)
    base=summary(baseline)
    trials=[{'method':name,'summary':summary(values),'gain_db':summary(values)['vocal']['sdr_db']-base['vocal']['sdr_db'],
        'content_safe':eligible(summary(values),base)} for name,values in rows.items()]
    trials.sort(key=lambda row:row['gain_db'],reverse=True)
    write_json(WORK/'screening.json',{'development':development(),'baseline':base,'trials':trials,'production_changed':False})
    print(json.dumps(trials[:8],indent=2),flush=True)

def fit(regularizations=(.001,.01,.1),maxiter=100,initial_weights=None,ftol=1e-9,content_margin=(.99,.99,.99,.99)):
    from tools import atlas_sdr_optimize as optimizer
    from threadpoolctl import threadpool_limits
    original=optimizer.read
    def read(path):
        value=original(path)
        if path.name=='manifest.json':
            value['development']=development()
            value['candidate_indices']=BASE_INDICES+[item[0] for item in EXPERTS]
        elif path.name=='atlas-studio-v2-preset.json':
            value['frequency_weights']['weights'] += [[0.]*len(value['frequency_weights']['anchors_hz']) for _ in EXPERTS]
        return value
    optimizer.read=read;optimizer.WORK=WORK/'fit'
    try:
        with threadpool_limits(limits=1):
            optimizer.main(content_margin=content_margin,regularizations=regularizations,maxiter=maxiter,spectral_stride=1,initial_weights=initial_weights,ftol=ftol)
    finally:optimizer.read=original

def choose_confirmation_manifest(folder,count=8):
    """Fixed order; reference-only silence eligibility, before any model output."""
    import hashlib
    from tools import atlas_extended as extended,atlas_benchmark as benchmark
    path=folder/'validation_manifest.json'
    if path.exists():return a.read(path)
    existing={p.name for p in (extended.WORK/'references').iterdir()}
    files=sorted((benchmark.WORK/'dataset').glob('*/*.stem.mp4'),key=lambda p:hashlib.sha256(('atlas-sdr-20261010:'+p.name).encode()).hexdigest())
    tracks=[];excluded=[]
    for file in files:
        identifier=hashlib.sha256(file.name.encode()).hexdigest()[:12]
        if identifier in existing:continue
        track={'id':identifier,'name':file.stem.removesuffix('.stem'),'file':str(file.resolve()),'split':'evaluation'}
        reference_folder=extended.prepare_reference(track)
        with np.load(reference_folder/'reference.npz') as reference:
            source_energy=float(np.sum(reference['source']**2))
            ratios={stem:float(np.sum(reference[stem]**2))/max(source_energy,1e-12) for stem in ('vocal','instrumental')}
        if source_energy<=1e-12 or any(ratio<=1e-8 for ratio in ratios.values()):
            excluded.append({'track':track,'reference_energy_ratios':ratios,'reason':'A silent reference stem has no meaningful SDR; no candidate produced or scored.'})
            continue
        tracks.append(track)
        if len(tracks)==count:break
    if len(tracks)!=count:raise RuntimeError(f'{count} fresh non-silent two-stem references required')
    data={'tracks':tracks,'excluded_silent_references':excluded,'selection':'Fixed SHA order among previously uncached references; only reference-energy eligibility (>1e-8 of mixture for both stems), never model quality.'}
    write_json(path,data);return data

def confirm(confirmation_size=8):
    import hashlib
    from tools import atlas_sdr_validate as validation, atlas_new_models as new
    from tools import atlas_extended as extended
    from tools.atlas_content_refine import passes_robust_confirmation
    frozen=a.read(WORK/'fit/frozen.json')
    if not frozen['selected']:
        print('No eligible frequency fit; production preserved',flush=True)
        return
    actual=hashlib.sha256((ROOT/'frontend/src/lib/atlas-studio-v2-preset.json').read_bytes()).hexdigest()
    if actual!=frozen['preset_sha256']:raise RuntimeError('Baseline changed during experiment')
    new.assert_idle_backend()
    validation.WORK=WORK/'confirmation'
    if not (validation.WORK/'frozen.json').exists():write_json(validation.WORK/'frozen.json',frozen)
    manifest=choose_confirmation_manifest(validation.WORK,confirmation_size)
    manifest['candidate_indices']=BASE_INDICES+[item[0] for item in EXPERTS]
    write_json(validation.WORK/'validation_manifest.json',manifest)
    for track in manifest['tracks']:
        for index,model in zip(BASE_INDICES,frozen['baseline_preset']['models']):
            print('CONFIRMATION BASELINE',index,track['name'],flush=True)
            new.assert_idle_backend()
            extended.infer_one(extended.prepare_reference(track),index,model)
    new.infer(manifest['tracks'],record_development=False)
    if 16 in manifest['candidate_indices']:
        from tools.atlas_big_model import infer as infer_big
        infer_big(manifest['tracks'])
    validation.evaluate()
    result=a.read(validation.WORK/'validation.json')
    delta=np.array([row['systems']['candidate']['vocal']['sdr_db']-row['systems']['current']['vocal']['sdr_db'] for row in result['rows']])
    result['bootstrap_97_5pct']=np.quantile(np.random.default_rng(20261011).choice(delta,(10000,len(delta)),replace=True).mean(axis=1),[.0125,.9875]).tolist()
    leakage={key:[] for key in ('current','candidate')}
    for track in manifest['tracks']:
        ref,x=r.load(track,manifest['candidate_indices'])
        for key,spec in [('current',frozen['baseline_preset']['frequency_weights']),('candidate',result['frozen_spec'])]:
            wave=combine_frequency(ref['source'],list(x),spec)[0]
            leakage[key].append(reference_leakage(ref,wave))
    result['reference_projection_leakage_proxy']={key:{stem:float(np.mean([row[stem] for row in rows])) for stem in ('vocal','instrumental')} for key,rows in leakage.items()}
    result['leakage_safe']=all(result['reference_projection_leakage_proxy']['candidate'][stem]<=result['reference_projection_leakage_proxy']['current'][stem]+1e-10 for stem in ('vocal','instrumental'))
    result['accepted']=passes_robust_confirmation(result) and result['leakage_safe']
    write_json(validation.WORK/'validation.json',result)
    report_name='atlas-studio-v2-new-models-round-two.json' if WORK.name=='round_two' else 'atlas-studio-v2-new-models.json'
    write_json(ROOT/'docs'/report_name,{'date':'2026-10-11','development':development(),
        'screening':a.read(WORK/'screening.json'),'selected_fit':frozen,'confirmation_manifest':manifest,
        'confirmation':result,'production_applied':False,'baseline_sha256':actual,
        'acceptance_plan':a.read(new.WORK/'acceptance.json')})
    print('FINAL NEW MODEL ACCEPTANCE',result['accepted'],flush=True)

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('phase',choices=['screen','fit','confirm'])
    globals()[parser.parse_args().phase]()
