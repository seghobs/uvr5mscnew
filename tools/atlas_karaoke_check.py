"""Instrumental-first three-model fit; freeze before evaluation, no GPU needed."""
import json
from pathlib import Path
import sys
import numpy as np
from scipy.optimize import minimize
from scipy.signal import stft
from threadpoolctl import threadpool_limits

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from tools.atlas_benchmark import load,metrics
from atlas_studio import transform_audio


def projection(reference,vocal,estimate):
    basis=np.stack([reference.ravel(),vocal.ravel()])
    gains=np.linalg.lstsq(basis.T,estimate.ravel(),rcond=None)[0]
    residual=estimate.ravel()-gains@basis
    return {'instrument_gain':float(gains[0]),'vocal_leakage':float(gains[1]**2),
            'artifact_residual':float(residual@residual/max(float(np.sum(reference**2)),1e-12))}


def main():
    tracks=json.loads((ROOT/'cache/atlas_benchmark/manifest.json').read_text(encoding='utf8'))['tracks']
    base=np.array([.5,.25,.25]);prepared=[]
    for track in tracks:
        if track['split']!='train':continue
        ref,c=load(track);est=ref['source'][None,:,:]-c[[0,2,4]]
        def spectrum(w):return stft(w.T,fs=44100,nperseg=2048,noverlap=1536)[2][:,::4,::4].ravel()
        z=np.stack([spectrum(w) for w in est]);target=np.abs(spectrum(ref['instrumental']))
        basis=np.stack([ref['instrumental'].ravel(),ref['vocal'].ravel()]);flat=est.reshape(3,-1)
        gains=np.linalg.lstsq(basis.T,flat.T,rcond=None)[0]
        residual=flat-gains.T@basis;den=max(float(np.sum(ref['instrumental']**2)),1e-12)
        error=flat-ref['instrumental'].ravel()
        prepared.append((z,target,gains,residual@residual.T/den,error@error.T/den))
    def measure(w):
        values=np.zeros(5)
        for z,target,gains,residual,error in prepared:
            difference=np.abs(w@z)-target;den=max(float(target@target),1e-12)
            values+=np.array([np.sum(np.minimum(difference,0)**2)/den,
                              np.sum(np.maximum(difference,0)**2)/den,
                              float((gains[1]@w)**2),float(w@residual@w),float(w@error@w)])
        return values/len(prepared)
    baseline=measure(base)
    result=minimize(lambda w:measure(w)[4],base,method='SLSQP',bounds=[(.45,.55),(.20,.30),(.20,.30)],
        constraints=[{'type':'eq','fun':lambda w:w.sum()-1},
                     {'type':'ineq','fun':lambda w:(baseline[:4]*np.array([1.01,1.0,1.0,1.01])-measure(w)[:4])/np.maximum(baseline[:4],1e-10)+1e-7}],
        options={'maxiter':100,'ftol':1e-12})
    if not result.success:raise RuntimeError(result.message)
    weights=result.x;print('FROZEN',weights,'DEVELOPMENT',measure(weights),flush=True)
    rows=[]
    for track in tracks:
        ref,c=load(track);est=ref['source'][None,:,:]-c[[0,2,4]]
        systems={}
        for name,w in [('atlas_studio',base),('karaoke_candidate',weights)]:
            wave=np.tensordot(w,est,axes=(0,0))
            systems[name]={**metrics(ref['instrumental'],wave),**projection(ref['instrumental'],ref['vocal'],wave)}
        rows.append({'id':track['id'],'name':track['name'],'split':track['split'],'systems':systems})
    summary={split:{name:{key:float(np.mean([row['systems'][name][key] for row in rows if row['split']==split]))
                         for key in rows[0]['systems'][name]} for name in ('atlas_studio','karaoke_candidate')}
             for split in ('train','test')}
    report={'weights':weights.tolist(),'objective':'Minimize instrumental waveform MSE, each weight within 0.05 of V1. Development spectral deficit/artifact budget at most +1%; no development increase in spectral excess or reference vocal projection leakage.',
        'fit_used_test':False,'scope':'16 existing seven-second excerpts, eight development/eight evaluation; previously used local reference pool, not evidence of universal quality.',
        'no_zero_loss_guarantee':True,'no_universal_superiority':True,
        'summary':summary,'tracks':rows}
    report['accepted']=all(summary[split]['karaoke_candidate']['spectral_deficit']<summary[split]['atlas_studio']['spectral_deficit']
        and all(summary[split]['karaoke_candidate'][key]<=summary[split]['atlas_studio'][key]*1.00001 for key in ('spectral_excess','vocal_leakage','artifact_residual'))
        and summary[split]['karaoke_candidate']['sdr_db']>=summary[split]['atlas_studio']['sdr_db'] for split in ('test',))
    augmented=[]
    for split in ('train','test'):
        for track in [t for t in tracks if t['split']==split][:2]:
            ref,c=load(track);folder=ROOT/'cache/atlas_conservative'/track['id']
            predictions=[]
            for index,candidate_index in enumerate((0,2,4)):
                original=ref['source']-c[candidate_index] if index==2 else c[candidate_index]
                estimate=.5*original
                for transform in ('swap_channels','invert_polarity'):
                    estimate+=.25*transform_audio(np.load(folder/f'{index}_{transform}.npy'),transform)
                predictions.append(ref['source']-estimate if index!=2 else estimate)
            systems={}
            for name,w in [('previous_v2',base),('karaoke_v2',weights)]:
                wave=np.tensordot(w,np.stack(predictions),axes=(0,0))
                systems[name]={**metrics(ref['instrumental'],wave),**projection(ref['instrumental'],ref['vocal'],wave)}
            augmented.append({'id':track['id'],'name':track['name'],'split':split,'systems':systems})
    transform_summary={name:{key:float(np.mean([row['systems'][name][key] for row in augmented if row['split']=='test']))
                            for key in augmented[0]['systems'][name]} for name in ('previous_v2','karaoke_v2')}
    before=transform_summary['previous_v2'];after=transform_summary['karaoke_v2']
    report['transform_check']={'tracks':augmented,'evaluation_summary':transform_summary}
    report['accepted']=bool(report['accepted'] and after['sdr_db']>before['sdr_db'] and all(
        after[key]<=before[key] for key in ('spectral_deficit','spectral_excess','vocal_leakage','artifact_residual')))
    (ROOT/'docs/atlas-studio-v2-karaoke-check.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n',encoding='utf8')
    print(json.dumps({'accepted':report['accepted'],'summary':summary},indent=2),flush=True)


if __name__=='__main__':
    with threadpool_limits(limits=1):main()
