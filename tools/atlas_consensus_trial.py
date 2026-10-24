"""Frozen three-model consensus trials; select on development before evaluation."""
import json
from pathlib import Path
import sys
import numpy as np
from scipy.signal import istft
from scipy.ndimage import uniform_filter
from threadpoolctl import threadpool_limits
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from tools.atlas_benchmark import load,metrics
from tools.atlas_karaoke_check import projection
from atlas_band_ensemble import spectrum


def render(source,candidates,method):
    z=np.stack([spectrum(x) for x in candidates])
    base=np.array([.55,.25,.20])[:,None,None,None]
    mean=np.sum(base*z,axis=0)
    center=np.median(z.real,axis=0)+1j*np.median(z.imag,axis=0)
    if method=='median':merged=center
    elif method=='half_median':merged=.5*center+.5*mean
    elif method=='geometric':
        merged=mean
        for _ in range(6):
            distance=np.maximum(np.abs(z-merged),1e-8)
            w=base/distance
            merged=np.sum(w*z,axis=0)/np.sum(w,axis=0)
    elif method=='robust':
        distance=uniform_filter(np.abs(z-center),size=(1,1,5,3),mode='nearest')
        scale=np.maximum(np.median(distance,axis=0),1e-8)
        w=base/(1+(distance/scale)**2)
        merged=np.sum(w*z,axis=0)/np.sum(w,axis=0)
    else:raise ValueError(method)
    _,wave=istft(merged,fs=44100,nperseg=2048,noverlap=1536,boundary=True)
    return source-wave.T[:len(source)]


def score(ref,inst):
    result={**metrics(ref['instrumental'],inst),**projection(ref['instrumental'],ref['vocal'],inst)}
    a=spectrum(ref['instrumental']);b=spectrum(inst);f=np.fft.rfftfreq(2048,1/44100)
    for name,lo,hi in [('bass',20,250),('body',250,1000),('attack',1000,10000)]:
        mask=(f>=lo)&(f<hi)
        result[name+'_complex_error']=float(np.sum(np.abs(a[:,mask]-b[:,mask])**2)/max(float(np.sum(np.abs(a[:,mask])**2)),1e-15))
    return result


def main():
    tracks=json.loads((ROOT/'cache/atlas_benchmark/manifest.json').read_text(encoding='utf8'))['tracks']
    methods=['median','half_median','geometric','robust'];rows=[]
    for track in tracks:
        if track['split']!='train':continue
        ref,c=load(track);c=c[[0,2,4]]
        systems={'previous_v2':score(ref,ref['source']-np.tensordot([.55,.25,.2],c,axes=(0,0)))}
        for method in methods:systems[method]=score(ref,render(ref['source'],c,method))
        rows.append({'name':track['name'],'systems':systems})
    summary={method:{key:float(np.mean([r['systems'][method][key] for r in rows])) for key in rows[0]['systems'][method]}
             for method in ['previous_v2',*methods]}
    baseline=summary['previous_v2']
    accepted=[method for method in methods if summary[method]['sdr_db']>baseline['sdr_db'] and all(
        summary[method][metric]<=baseline[metric] for metric in ('spectral_deficit','spectral_excess','vocal_leakage','artifact_residual','bass_complex_error','body_complex_error','attack_complex_error'))]
    report={'development_summary':summary,'accepted_development_methods':accepted,'development_rows':rows,'evaluation_rows':[]}
    if accepted:
        selected=max(accepted,key=lambda key:summary[key]['sdr_db']);report['selected_on_development']=selected
        print('FROZEN',selected,flush=True)
        for track in tracks:
            if track['split']!='test':continue
            ref,c=load(track);c=c[[0,2,4]]
            report['evaluation_rows'].append({'name':track['name'],'systems':{
                'previous_v2':score(ref,ref['source']-np.tensordot([.55,.25,.2],c,axes=(0,0))),
                selected:score(ref,render(ref['source'],c,selected))}})
        report['evaluation_summary']={method:{metric:float(np.mean([r['systems'][method][metric] for r in report['evaluation_rows']]))
            for metric in report['evaluation_rows'][0]['systems'][method]} for method in ('previous_v2',selected)}
    (ROOT/'cache/atlas_music_fit/consensus-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps({k:v for k,v in report.items() if not k.endswith('rows')},indent=2),flush=True)


if __name__=='__main__':
    with threadpool_limits(limits=1):main()
