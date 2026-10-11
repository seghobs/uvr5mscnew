"""Diagnostic: measure the tradeoff from maximizing SDR without content guards.

Development data only. Does not change the frozen challenger or production.
"""
import hashlib
import json
from pathlib import Path
import sys
import numpy as np
from scipy.optimize import minimize
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from tools import atlas_refinement as r,atlas_extended as e,atlas_benchmark as b
from tools.atlas_sdr_optimize import WORK,read,score,summary,eligible
from atlas_band_ensemble import FFT,HOP,RATE,combine_frequency


def main():
    frozen=read(WORK/'frozen.json');preset=frozen['baseline_preset']
    manifest=read(ROOT/'cache/atlas_confirmation/manifest.json');tracks=manifest['development'];indices=manifest['candidate_indices']
    anchors=preset['frequency_weights']['anchors_hz'];prior=np.asarray(preset['frequency_weights']['weights']).ravel()
    grams=[];linears=[];constants=[]
    for t in tracks:
        folder=e.WORK/'references'/t['id'];inputs=[folder/'reference.npz',*[folder/f'candidate_{i}.npy' for i in indices]]
        key=hashlib.sha256(json.dumps({'anchors':anchors,'FFT':FFT,'HOP':HOP,'RATE':RATE,
            'combiner':hashlib.sha256((ROOT/'atlas_band_ensemble.py').read_bytes()).hexdigest(),'indices':indices,
            'inputs':[(p.stat().st_size,p.stat().st_mtime_ns) for p in inputs]}).encode()).hexdigest()[:16]
        with np.load(folder/f'exact_waveform_{key}.npz') as d:
            grams.append(d['gram']);linears.append(d['linear']);constants.append(float(d['constant']))
    g=np.stack(grams);l=np.stack(linears);c=np.array(constants);n=len(anchors);count=len(indices)
    def errors(w):return np.maximum(np.einsum('i,tij,j->t',w,g,w)-2*l@w+c,1e-12)
    eq=np.tile(np.eye(n),(1,count))
    solved=minimize(lambda w:float(np.mean(np.log(errors(w)))),prior,
        jac=lambda w:np.mean(2*(np.einsum('tij,j->ti',g,w)-l)/errors(w)[:,None],axis=0),
        method='SLSQP',bounds=[(0,1)]*len(prior),constraints=[{'type':'eq','fun':lambda w:eq@w-1,'jac':lambda w:eq}],
        options={'ftol':1e-9,'maxiter':200})
    if not solved.success:raise RuntimeError(solved.message)
    spec={'anchors_hz':anchors,'weights':solved.x.reshape(count,n).tolist()};rows=[]
    for t in tracks:
        ref,candidates=r.load(t,indices);rows.append(score(ref,combine_frequency(ref['source'],list(candidates),spec)[0]))
        print('RELAXED SCORE',t['name'],flush=True)
    metrics=summary(rows)
    result={'development_only':True,'development_ids':frozen['development_ids'],'spec':spec,'summary':metrics,
            'baseline_summary':frozen['baseline_summary'],'eligible':eligible(metrics,frozen['baseline_summary']),
            'mean_sdr_gain_db':metrics['vocal']['sdr_db']-frozen['baseline_summary']['vocal']['sdr_db'],
            'production_changed':False,'method':'Pure development mean log waveform error; removed content and per-recording regression constraints to quantify tradeoffs'}
    b.write_json(WORK/'relaxed.json',result);print(json.dumps({k:v for k,v in result.items() if k not in ('spec','development_ids')},indent=2),flush=True)


if __name__=='__main__':main()
