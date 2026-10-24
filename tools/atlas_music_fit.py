"""Fit a smooth three-expert instrumental blend on cached development stems only."""
import json
from pathlib import Path
import sys
import numpy as np
from scipy.optimize import minimize
from scipy.signal import istft
from threadpoolctl import threadpool_limits

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from tools.atlas_benchmark import load,metrics
from tools.atlas_karaoke_check import projection
from atlas_band_ensemble import spectrum,combine_frequency

ANCHORS=np.array([0,80,250,1000,4000,10000,22050])
BASE=np.array([.55,.25,.20])


def main():
    tracks=json.loads((ROOT/'cache/atlas_benchmark/manifest.json').read_text(encoding='utf8'))['tracks']
    frequencies=np.fft.rfftfreq(2048,1/44100)
    interpolation=np.stack([np.interp(frequencies,ANCHORS,np.eye(len(ANCHORS))[i]) for i in range(len(ANCHORS))],axis=1)
    gram=np.zeros((21,21));linear=np.zeros(21);constant=0.;count=0
    artifact_gram=np.zeros((21,21));voice_gram=np.zeros((21,21))
    for track in tracks:
        if track['split']!='train':continue
        ref,c=load(track);z=np.stack([spectrum(ref['source']-c[i]) for i in (0,2,4)])
        target=spectrum(ref['instrumental']);den=np.sum(np.abs(target)**2)
        g=np.einsum('icft,jcft->fij',z.conj(),z).real/den
        h=np.einsum('icft,cft->fi',z.conj(),target).real/den
        gram+=np.einsum('fk,fl,fij->ikjl',interpolation,interpolation,g).reshape(21,21)
        linear+=np.einsum('fk,fi->ik',interpolation,h).reshape(21)
        basis=[]
        for model in range(3):
            for knot in range(7):
                _,wave=istft(z[model]*interpolation[:,knot][None,:,None],fs=44100,nperseg=2048,noverlap=1536,boundary=True)
                basis.append(wave.T[:len(ref['source'])].ravel())
        basis=np.array(basis)
        references=np.stack([ref['instrumental'].ravel(),ref['vocal'].ravel()])
        rgram=references@references.T;cross=basis@references.T
        coefficients=np.linalg.solve(rgram,cross.T)
        artifact_gram+=(basis@basis.T-cross@coefficients)/max(float(np.sum(ref['instrumental']**2)),1e-15)
        voice_gram+=np.outer(coefficients[1],coefficients[1])
        constant+=1.;count+=1
    gram/=count;linear/=count;constant/=count;artifact_gram/=count;voice_gram/=count
    initial=np.repeat(BASE[:,None],7,axis=1)
    # Freeze one objective, parameter bounds and smoothing before evaluation.
    # No frequency is muted: nonnegative expert weights sum to one at every bin.
    def objective(flat):
        weights=flat.reshape(3,7)
        smooth=np.diff(weights,axis=1)
        return float(flat@gram@flat-2*linear@flat+constant+.002*np.sum(smooth**2))
    result=minimize(objective,initial.ravel(),method='SLSQP',
        bounds=[(max(0.,float(w)-.35),min(1.,float(w)+.35)) for w in initial.ravel()],
        constraints=[{'type':'eq','fun':lambda x:x.reshape(3,7).sum(axis=0)-1},
                     {'type':'ineq','fun':lambda x:float(initial.ravel()@artifact_gram@initial.ravel()-x@artifact_gram@x),
                      'jac':lambda x:-2*artifact_gram@x},
                     {'type':'ineq','fun':lambda x:float(initial.ravel()@voice_gram@initial.ravel()-x@voice_gram@x),
                      'jac':lambda x:-2*voice_gram@x}],
        options={'maxiter':500,'ftol':1e-12})
    if not result.success:raise RuntimeError(result.message)
    spec={'anchors_hz':ANCHORS.tolist(),'weights':result.x.reshape(3,7).tolist()}
    report={'frequency_weights':spec,'fit_split':'train','fit_used_test':False,
        'development_constraints':'No increase in mean conditional artifact residual or mean vocal projection power against previous V2; simplex and smoothness regularization.',
        'scope':'Previously reused local 8-development/8-evaluation seven-second pool; not a fresh unseen-song result.',
        'models_used':[0,2,4],'new_models':0,'trials':[]}
    print('FROZEN',json.dumps(spec),flush=True)
    for track in tracks:
        ref,c=load(track);candidates=c[[0,2,4]]
        systems={}
        for key,weights in [('v1',np.array([.5,.25,.25])),('previous_v2',BASE),('frequency_candidate',None)]:
            if weights is None:_,inst=combine_frequency(ref['source'],candidates,spec)
            else:inst=ref['source']-np.tensordot(weights,candidates,axes=(0,0))
            values={**metrics(ref['instrumental'],inst),**projection(ref['instrumental'],ref['vocal'],inst)}
            r=spectrum(ref['instrumental']);e=spectrum(inst)
            f=np.fft.rfftfreq(2048,1/44100)
            for name,lo,hi in [('bass',20,250),('body',250,1000),('attack',1000,10000)]:
                mask=(f>=lo)&(f<hi);den=max(float(np.sum(np.abs(r[:,mask])**2)),1e-15)
                values[f'{name}_complex_error']=float(np.sum(np.abs(e[:,mask]-r[:,mask])**2)/den)
                a=np.sqrt(np.sum(np.abs(r[:,mask])**2,axis=(0,1)));b=np.sqrt(np.sum(np.abs(e[:,mask])**2,axis=(0,1)))
                ar=np.maximum(np.diff(a),0);br=np.maximum(np.diff(b),0)
                values[f'{name}_flux_error']=float(np.sum((ar-br)**2)/max(float(np.sum(ar**2)),1e-15))
            systems[key]=values
        report['trials'].append({'name':track['name'],'split':track['split'],'systems':systems})
    report['summary']={split:{key:{metric:float(np.mean([r['systems'][key][metric] for r in report['trials'] if r['split']==split]))
                       for metric in report['trials'][0]['systems'][key]} for key in ('v1','previous_v2','frequency_candidate')}
                       for split in ('train','test')}
    folder=ROOT/'cache/atlas_music_fit';folder.mkdir(exist_ok=True)
    (folder/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps(report['summary'],indent=2),flush=True)


if __name__=='__main__':
    with threadpool_limits(limits=1):main()
