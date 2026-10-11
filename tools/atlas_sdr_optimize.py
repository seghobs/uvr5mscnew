"""Optimize against the deployed frequency recipe, never against an old scalar V2.

Use existing development outputs; freeze selection before any new validation.
No model inference or production preset modification occurs in this tool.
"""
import hashlib
import json
from pathlib import Path
import sys
import numpy as np
from scipy.optimize import minimize
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from tools import atlas_refinement as r
from tools import atlas_extended as e
from tools import atlas_benchmark as b
from atlas_band_ensemble import spectrum,combine_frequency,frequency_matrix,FFT,HOP,RATE
WORK=ROOT/'cache/atlas_sdr_optimize'


def read(path):return json.loads(path.read_text(encoding='utf8'))


def score(ref,vocal):
    return {stem:b.metrics(ref[stem],wave) for stem,wave in
            [('vocal',vocal),('instrumental',ref['source']-vocal)]}


def summary(rows):
    return {s:{k:float(np.mean([row[s][k] for row in rows])) for k in rows[0][s]}
            for s in ('vocal','instrumental')}


def eligible(candidate,baseline):
    return all(candidate[s]['sdr_db']>baseline[s]['sdr_db'] and
               candidate[s]['si_sdr_db']>=baseline[s]['si_sdr_db'] and
               all(candidate[s][k]<=baseline[s][k]+1e-8 for k in ('spectral_deficit','spectral_excess'))
               for s in ('vocal','instrumental'))


def main(content_margin=None, regularizations=(.0001,.001,.01), maxiter=200, spectral_stride=4, initial_weights=None, ftol=1e-9):
    if (WORK/'frozen.json').exists():raise RuntimeError('Frozen experiment already exists; do not overwrite it')
    preset=read(ROOT/'frontend/src/lib/atlas-studio-v2-preset.json')
    manifest=read(ROOT/'cache/atlas_confirmation/manifest.json')
    tracks=manifest['development'];indices=manifest['candidate_indices']
    anchors=preset['frequency_weights']['anchors_hz'];count=len(indices);n=len(anchors)
    prior=np.array(preset['frequency_weights']['weights']);flat_prior=prior.ravel()
    initial=flat_prior
    if initial_weights is not None:
        # A development-only warm start must remain a valid source-preserving blend.
        from atlas_band_ensemble import validate_frequency_weights
        _,starting=validate_frequency_weights({'anchors_hz':anchors,'weights':initial_weights},count)
        initial=starting.ravel()
    gram=[];linear=[];constant=[];spectra=[];limits=np.zeros(4);baseline=[]
    if not isinstance(spectral_stride,int) or spectral_stride<1:raise ValueError('Invalid spectral stride')
    freq=np.fft.rfftfreq(FFT,1/RATE)[::spectral_stride]
    basis=np.stack([np.interp(freq,anchors,row) for row in np.eye(n)],axis=1)
    for t in tracks:
        ref,candidates=r.load(t,indices);folder=e.WORK/'references'/t['id']
        inputs=[folder/'reference.npz',*[folder/f'candidate_{i}.npy' for i in indices]]
        key=hashlib.sha256(json.dumps({'anchors':anchors,'FFT':FFT,'HOP':HOP,'RATE':RATE,
            'combiner':hashlib.sha256((ROOT/'atlas_band_ensemble.py').read_bytes()).hexdigest(),
            'indices':indices,'inputs':[(p.stat().st_size,p.stat().st_mtime_ns) for p in inputs]}).encode()).hexdigest()[:16]
        cache=folder/f'exact_waveform_{key}.npz'
        if cache.exists():
            with np.load(cache) as d:g=d['gram'];l=d['linear'];c=float(d['constant'])
        else:
            g,l,c=r.waveform_statistics(candidates,ref['vocal'],anchors)
            np.savez_compressed(cache,gram=g,linear=l,constant=c)
        gram.append(g);linear.append(l);constant.append(c)
        vocal=combine_frequency(ref['source'],list(candidates),preset['frequency_weights'])[0]
        baseline.append(score(ref,vocal))
        x=np.stack([spectrum(w)[:,::spectral_stride,::spectral_stride] for w in candidates])
        src=spectrum(ref['source'])[:,::spectral_stride,::spectral_stride];v=spectrum(ref['vocal'])[:,::spectral_stride,::spectral_stride]
        inst=spectrum(ref['instrumental'])[:,::spectral_stride,::spectral_stride]
        spectra.append((x,src,np.abs(v),np.abs(inst)))
        limits+=e.content_statistics(prior,basis,x,src,np.abs(v),np.abs(inst))/len(tracks)
        print('PREPARED',t['name'],flush=True)
    if content_margin is not None:
        margin=np.asarray(content_margin,dtype=float)
        if margin.shape!=(4,) or not np.isfinite(margin).all() or (margin<=0).any() or (margin>1).any():
            raise ValueError('Content margins must be four finite factors in (0,1]')
        limits*=margin
    gram=np.stack(gram);linear=np.stack(linear);constant=np.array(constant)
    def errors(w):return np.einsum('i,tij,j->t',w,gram,w)-2*linear@w+constant
    prior_errors=errors(flat_prior);cap=prior_errors*10**(.03/10)
    equality=np.tile(np.eye(n),(1,count));trials=[]
    def content(w):
        values=np.zeros(4);jac=np.zeros((4,count,n))
        for x,src,v,inst in spectra:
            p,j=e.content_statistics(w.reshape(count,n),basis,x,src,v,inst,True)
            values+=p/len(tracks);jac+=j/len(tracks)
        return values,jac.reshape(4,count*n)
    for regularization in regularizations:
        memo={}
        def constraint(w):
            if 'w' not in memo or not np.array_equal(w,memo['w']):
                p,j=content(w);memo.update(w=w.copy(),value=limits-p,jac=-j)
            return memo
        def objective(w):
            return float(np.mean(np.log(np.maximum(errors(w),1e-12)))+
                regularization*np.sum((w-flat_prior)**2))
        def gradient(w):
            return np.mean(2*(np.einsum('tij,j->ti',gram,w)-linear)/np.maximum(errors(w),1e-12)[:,None],axis=0)+2*regularization*(w-flat_prior)
        print('OPTIMIZE',regularization,flush=True)
        steps=[0]
        def progress(w):
            steps[0]+=1
            if steps[0]%10==0:
                print('ITERATION',steps[0],'content_slack',float(constraint(w)['value'].min()),flush=True)
        solved=minimize(objective,initial,jac=gradient,method='SLSQP',bounds=[(0,1)]*(count*n),
            callback=progress,
            constraints=[{'type':'eq','fun':lambda w:equality@w-1,'jac':lambda w:equality},
                {'type':'ineq','fun':lambda w:cap-errors(w),'jac':lambda w:-2*(np.einsum('tij,j->ti',gram,w)-linear)},
                {'type':'ineq','fun':lambda w:constraint(w)['value'],'jac':lambda w:constraint(w)['jac']}],
            options={'ftol':ftol,'maxiter':maxiter})
        valid=bool(solved.success and (cap-errors(solved.x)).min()>=-1e-8 and constraint(solved.x)['value'].min()>=-1e-8)
        trials.append({'regularization':regularization,'converged':bool(solved.success),'message':str(solved.message),
                       'valid':valid,'weights':solved.x.reshape(count,n).tolist(),
                       'content_slack_min':float(constraint(solved.x)['value'].min()),
                       'waveform_slack_min':float((cap-errors(solved.x)).min()),
                       'development_mean_sdr_gain_db':float(np.mean(10*np.log10(prior_errors/np.maximum(errors(solved.x),1e-12))))})
        print('TRIAL',regularization,valid,trials[-1]['development_mean_sdr_gain_db'],flush=True)
    base=summary(baseline);full=[]
    for trial in trials:
        if not trial['valid']:continue
        spec={'anchors_hz':anchors,'weights':trial['weights']};rows=[]
        for t in tracks:
            ref,candidates=r.load(t,indices);rows.append(score(ref,combine_frequency(ref['source'],list(candidates),spec)[0]))
        metrics=summary(rows);trial['full_development']=metrics;trial['eligible']=eligible(metrics,base)
        if trial['eligible']:full.append(trial)
        print('FULL METRICS',trial['regularization'],trial['eligible'],metrics,flush=True)
    chosen=max(full,key=lambda t:t['full_development']['vocal']['sdr_db']) if full else None
    b.write_json(WORK/'frozen.json',{'baseline_preset':preset,'development_ids':[t['id'] for t in tracks],
        'baseline_summary':base,'trials':trials,'selected':chosen,'evaluation_used_for_selection':False,
        'preset_sha256':hashlib.sha256((ROOT/'frontend/src/lib/atlas-studio-v2-preset.json').read_bytes()).hexdigest(),
        'content_margin':None if content_margin is None else list(content_margin),
        'maxiter':maxiter,'regularizations':list(regularizations),'spectral_stride':spectral_stride,
        'initial_weights':initial_weights,
        'ftol':ftol,
        'method':'Mean log exact waveform error; nonnegative frequency weights sum to one; per-recording .03 dB regression cap; four content constraints and full development metric screening'})
    print('FROZEN',bool(chosen),flush=True)


if __name__=='__main__':main()
