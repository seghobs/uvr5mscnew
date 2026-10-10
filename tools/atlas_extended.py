"""Expanded reference experiment plus FULL Turkish songs without reference claims."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import time
import numpy as np
import soundfile as sf
from scipy.optimize import minimize

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from tools import atlas_benchmark as pilot
from atlas_band_ensemble import spectrum,combine_frequency,frequency_matrix,RATE,FFT

WORK=ROOT/'cache/atlas_extended'
MODELS=pilot.MODELS+[
 {'model_type':'roformer','model_key':'BS-Roformer-Revive 2 (Bleedless) by pcunwa','estimate':'vocal'},
 {'model_type':'roformer','model_key':'BS-Roformer-Revive 3e (Fullness) by pcunwa','estimate':'vocal'},
 {'model_type':'roformer','model_key':'BS-Roformer-Resurrection Vocals by pcunwa','estimate':'vocal'},
 {'model_type':'roformer','model_key':'BS-Roformer-Resurrection Instrumental by pcunwa','estimate':'inst'},
]
ANCHORS=[0,125,250,500,1000,2000,4000,8000,16000,22050]
BASE=np.array([.5,0,.25,0,.25,0,0])
CURRENT=np.array([.4736964441851915,.06874969751320373,.19796380035913153,0,.2595900579424732,0,0])


def passes_expanded(report):
    """Predeclared mean improvement and content checks, never used for fitting."""
    baseline=report['summary']['test']['v1']
    candidate=report['summary']['test']['v2_band']
    return (report['test_mean_delta_db']>=.2 and report['bootstrap_95pct'][0]>0
        and all(candidate[s]['si_sdr_db']>=baseline[s]['si_sdr_db'] for s in ('vocal','instrumental'))
        and all(candidate[s][k]<=baseline[s][k]+1e-8
            for s in ('vocal','instrumental') for k in ('spectral_deficit','spectral_excess')))


def tracks():
    manifest=WORK/'manifest.json'
    if manifest.exists():return json.loads(manifest.read_text(encoding='utf8'))['tracks']
    result=[]
    for split in ('train','test'):
        paths=list((pilot.WORK/'dataset'/split).glob('*.stem.mp4'))
        paths.sort(key=lambda p:hashlib.sha256(('atlas-pilot-v1:'+p.name).encode()).hexdigest())
        selected=paths[:16] if split=='train' else paths[8:16]
        for path in selected:
            result.append({'name':path.stem.removesuffix('.stem'),'split':split,
                'file':str(path.resolve()),'id':hashlib.sha256(path.name.encode()).hexdigest()[:12]})
    if len(result)!=24:raise ValueError('Expected 16 development and 8 new evaluation tracks')
    pilot.write_json(manifest,{'models':MODELS,'tracks':result,'selection':'same fixed SHA ordering: train[:16], test[8:16]',
        'note':'Old test[0:8] is not used for fitting or fresh evaluation.'})
    return result


def prepare_reference(track):
    folder=WORK/'references'/track['id']; folder.mkdir(parents=True,exist_ok=True)
    old=pilot.WORK/'estimates'/track['id']
    for name in ('reference.npz','input.wav',*[f'candidate_{i}.npy' for i in range(5)]):
        if (old/name).exists() and not (folder/name).exists():shutil.copy2(old/name,folder/name)
    if not (folder/'reference.npz').exists():
        previous=pilot.WORK
        try:
            pilot.WORK=WORK/'references_work'
            generated=pilot.decode(track)
            for name in ('reference.npz','input.wav'):shutil.copy2(generated/name,folder/name)
        finally:pilot.WORK=previous
    return folder


def infer_one(folder,index,model):
    import core
    from studio_pro import classify_stem
    target=folder/f'candidate_{index}.npy'
    if target.exists():return
    with np.load(folder/'reference.npz') as ref:
        source=ref['source']; headroom=float(ref['headroom'])
    started=time.monotonic()
    try:
        files=core.roformer_separator(str(folder/'input.wav'),model['model_key'],'wav',256,False,8,1,1.,0.,'',
            work_dir=str(folder),overlap_factor=8,float_output=True)
        pair={classify_stem(p):p for p in files}
        if set(pair)!={'vocal','inst'}:raise ValueError('Incomplete model pair')
        estimate,rate=sf.read(pair[model['estimate']],dtype='float64',always_2d=True)
        if rate!=RATE or estimate.shape!=(max(16*RATE,len(source)),2) or not np.isfinite(estimate).all() or np.abs(estimate).max()>=.999:
            raise ValueError('Invalid output gain/timebase')
        estimate=estimate[:len(source)]/headroom
        candidate=source-estimate if model['estimate']=='inst' else estimate
        temp=target.with_suffix('.tmp.npy');np.save(temp,candidate.astype(np.float32));os.replace(temp,target)
        pilot.write_json(folder/f'timing_{index}.json',{'seconds':time.monotonic()-started})
        for p in files:Path(p).unlink(missing_ok=True)
    finally:core.clear_gpu_and_ram_cache()
    print(f'DONE seconds={time.monotonic()-started:.1f}',flush=True)


def infer():
    selected=tracks()
    # First test the genuinely new experts; keep GPU work sequential.
    for index in [5,6,0,1,2,3,4]:
        for number,track in enumerate(selected):
            folder=prepare_reference(track)
            if (folder/f'candidate_{index}.npy').exists():continue
            print(f"REFERENCE model={index+1}/7 track={number+1}/24 {track['name']}",flush=True)
            infer_one(folder,index,MODELS[index])


def load(track):
    folder=WORK/'references'/track['id']
    with np.load(folder/'reference.npz') as ref:data={k:ref[k] for k in ('source','vocal','instrumental')}
    return data,np.stack([np.load(folder/f'candidate_{i}.npy').astype(np.float64) for i in range(7)])


def frequency_statistics(x,target,basis,scale):
    """Complex error quadratic form; model-major/anchor-major coefficient order."""
    count=len(x);anchors=basis.shape[1];dimension=count*anchors
    cross=np.einsum('mcft,ncft->fmn',x,x.conj(),optimize=True).real
    correlation=np.einsum('mcft,cft->fm',x,target.conj(),optimize=True).real
    gram=scale*np.einsum('fmn,fa,fb->manb',cross,basis,basis,optimize=True).reshape(dimension,dimension)
    linear=scale*np.einsum('fm,fa->ma',correlation,basis,optimize=True).ravel()
    constant=scale*float(np.sum(np.abs(target)**2))
    return gram,linear,constant


def content_statistics(weights,basis,x,src,v,inst,derivatives=False):
    estimate=np.einsum('mf,mcft->cft',weights@basis.T,x,optimize=True)
    values=np.zeros(4);jac=np.zeros((4,*weights.shape))
    for j,(reference,result) in enumerate(((v,estimate),(inst,src-estimate))):
        delta=np.abs(result)-reference;denom=max(float(np.sum(reference**2)),1e-12)
        for k,residual in enumerate((np.minimum(delta,0),np.maximum(delta,0))):
            values[j*2+k]=float(np.sum(residual**2))/denom
            if derivatives:
                direction=result.conj()/np.maximum(np.abs(result),1e-12)
                coefficient=2*residual*direction/denom*(1 if j==0 else -1)
                correlation=np.einsum('cft,mcft->fm',coefficient,x,optimize=True).real
                jac[j*2+k]=correlation.T@basis
    return (values,jac) if derivatives else values


def fit():
    development=[t for t in tracks() if t['split']=='train']
    n=len(ANCHORS);dimension=7*n;gram=np.zeros((dimension,dimension));linear=np.zeros(dimension);constant=0.
    frequencies=np.fft.rfftfreq(FFT,1/RATE)[::4]
    basis=np.stack([np.interp(frequencies,ANCHORS,row) for row in np.eye(n)],axis=1)
    spectral=[]
    for track in development:
        ref,candidates=load(track)
        x=np.stack([spectrum(c)[:,::4,::4] for c in candidates]);v=spectrum(ref['vocal'])[:,::4,::4]
        src=spectrum(ref['source'])[:,::4,::4];inst=src-v
        scale=(1/max(float(np.sum(np.abs(v)**2)),1e-12)+1/max(float(np.sum(np.abs(inst)**2)),1e-12))/(2*len(development))
        g,b,c=frequency_statistics(x,v,basis,scale)
        gram+=g;linear+=b;constant+=c
        spectral.append((x,src,np.abs(v),np.abs(inst)))
    def proxy(weights,derivatives=False):
        values=np.zeros(4);jac=np.zeros((4,7,n))
        for x,src,v,inst in spectral:
            if derivatives:
                p,j=content_statistics(weights,basis,x,src,v,inst,True);values+=p;jac+=j
            else:values+=content_statistics(weights,basis,x,src,v,inst)
        if derivatives:return values/len(development),jac/len(development)
        return values/len(development)
    baseline=np.repeat(BASE[:,None],n,axis=1);baseline_proxy=proxy(baseline)
    trials=[]
    # Always retain V1's experts: mixing back toward V1 stays within four slots.
    for extra in (1,3,5,6):
        indices=sorted([0,2,4,extra]);var_indices=np.array([i*n+a for i in indices for a in range(n)])
        g=gram[np.ix_(var_indices,var_indices)];b=linear[var_indices];prior=baseline[indices]
        for regularization in (.0001,.001,.01):
            def objective(flat):
                matrix=flat.reshape(4,n)
                return float(flat@g@flat-2*b@flat+constant+regularization*np.sum(np.diff(matrix,axis=1)**2))
            def gradient(flat):
                matrix=flat.reshape(4,n);delta=np.diff(matrix,axis=1);smooth=np.zeros_like(matrix)
                smooth[:,:-1]-=delta;smooth[:,1:]+=delta
                return 2*(g@flat-b)+2*regularization*smooth.ravel()
            equality=np.tile(np.eye(n),(1,4))
            memo={}
            def constrained(flat):
                if 'x' not in memo or not np.array_equal(flat,memo['x']):
                    weights=np.zeros((7,n));weights[indices]=flat.reshape(4,n)
                    p,j=proxy(weights,True)
                    memo.update(x=flat.copy(),value=baseline_proxy-p,
                        jac=-j[:,indices,:].reshape(4,4*n))
                return memo
            result=minimize(objective,prior.ravel(),jac=gradient,method='SLSQP',bounds=[(0,1)]*(4*n),
                constraints=[{'type':'eq','fun':lambda w:equality@w-1,'jac':lambda w:equality},
                    {'type':'ineq','fun':lambda w:constrained(w)['value'],'jac':lambda w:constrained(w)['jac']}],
                options={'ftol':1e-10,'maxiter':500})
            if not result.success:continue
            for alpha in (.25,.5,.75,1.):
                weights=np.zeros((7,n));weights[indices]=(1-alpha)*prior+alpha*result.x.reshape(4,n)
                p=proxy(weights);flat=weights.ravel();loss=float(flat@gram@flat-2*linear@flat+constant)
                trial={'indices':indices,'regularization':regularization,'alpha':alpha,'loss':loss,
                    'weights':weights.tolist(),'proxy':p.tolist(),'safe_development':bool(np.all(p<=baseline_proxy+1e-8))}
                trials.append(trial)
            print(f'FIT extra={extra} regularization={regularization}',flush=True)
    eligible=[t for t in trials if t['safe_development']]
    if not eligible:raise RuntimeError('No frequency blend meets development content constraints')
    best=min(eligible,key=lambda t:t['loss'])
    pilot.write_json(WORK/'frozen_band_fit.json',{'best':best,'anchors_hz':ANCHORS,'trials':trials,
        'baseline_proxy':baseline_proxy.tolist(),'test_used_for_fitting':False,
        'method':'complex STFT normalized error; nonnegative frequency simplex; smoothness; development-only subset/regularization/alpha selection'})
    print('SELECTED',best['indices'],best['loss'],best['proxy'],flush=True)


def evaluate():
    frozen=json.loads((WORK/'frozen_band_fit.json').read_text(encoding='utf8'));best=frozen['best'];ix=best['indices']
    spec={'anchors_hz':ANCHORS,'weights':np.array(best['weights'])[ix].tolist()}
    rows=[]
    for track in tracks():
        ref,candidates=load(track);row={'name':track['name'],'split':track['split'],'systems':{}}
        outputs={'v1':np.tensordot(BASE,candidates,axes=(0,0)),
                 'v2_current':np.tensordot(CURRENT,candidates,axes=(0,0)),
                 'v2_band':combine_frequency(ref['source'],[candidates[i] for i in ix],spec)[0]}
        for name,vocal in outputs.items():
            row['systems'][name]={stem:pilot.metrics(ref[stem],value) for stem,value in
                [('vocal',vocal),('instrumental',ref['source']-vocal)]}
        rows.append(row);print('SCORED',track['split'],track['name'],flush=True)
    summary={}
    for split in ('train','test'):
        chosen=[r for r in rows if r['split']==split]
        summary[split]={name:{stem:{key:float(np.mean([r['systems'][name][stem][key] for r in chosen]))
            for key in chosen[0]['systems'][name][stem]} for stem in ('vocal','instrumental')} for name in outputs}
    chosen=[r for r in rows if r['split']=='test'];delta=np.array([r['systems']['v2_band']['vocal']['sdr_db']-r['systems']['v1']['vocal']['sdr_db'] for r in chosen])
    rng=np.random.default_rng(20261011);interval=np.quantile(np.mean(rng.choice(delta,(10000,len(delta)),replace=True),axis=1),[.025,.975]).tolist()
    report={'fit':frozen,'spec':spec,'models':[MODELS[i] for i in ix],'summary':summary,'rows':rows,
        'test_mean_delta_db':float(delta.mean()),'bootstrap_95pct':interval,'improved':int(np.sum(delta>0)),
        'limitations':['Reference excerpts are not Turkish full songs','Model training data overlap unknown','No listening judgement from objective metrics alone']}
    report['accepted_for_production']=passes_expanded(report)
    pilot.write_json(WORK/'band_results.json',report);print(json.dumps(summary,indent=2),flush=True)


def full_tracks():
    manifest=WORK/'turkish_manifest.json'
    if manifest.exists():return json.loads(manifest.read_text(encoding='utf8'))['tracks']
    result=[]
    for prefix in ('Bilal SONSES - Nefret','Ezhel - Ba','Gözleri Fettan'):
        paths=[p for p in (ROOT/'ytdl').glob('*.wav') if p.name.startswith(prefix)]
        if len(paths)!=1:raise ValueError(f'Cannot identify source: {prefix}')
        p=paths[0];info=sf.info(p)
        result.append({'name':p.stem,'file':str(p),'id':hashlib.sha256(p.name.encode()).hexdigest()[:12],
                       'seconds':info.duration,'ground_truth':False})
    pilot.write_json(manifest,{'tracks':result,'note':'Original full mixes, NOT reference stems; no SDR/quality claims allowed.'})
    return result


def full_infer(required=None):
    if required is None:
        frozen=json.loads((WORK/'frozen_band_fit.json').read_text(encoding='utf8'))
        required=sorted(set([0,1,2,4]+frozen['best']['indices']))
    for track in full_tracks():
        folder=WORK/'turkish'/track['id'];folder.mkdir(parents=True,exist_ok=True)
        if not (folder/'reference.npz').exists():
            source,rate=sf.read(track['file'],always_2d=True,dtype='float64')
            if rate!=RATE or source.shape[1]!=2:raise ValueError('Source must be 44.1k stereo')
            headroom=.25/max(1.,float(np.max(np.abs(source))))
            sf.write(folder/'input.wav',source*headroom,RATE,subtype='FLOAT')
            np.savez(folder/'reference.npz',source=source,headroom=headroom)
        for index in required:
            if (folder/f'candidate_{index}.npy').exists():continue
            print('FULL SONG',track['name'],'MODEL',index,flush=True)
            infer_one(folder,index,MODELS[index])


def full_base():
    full_infer([0,1,2,4])


def full_export(ready_only=False):
    frozen=json.loads((WORK/'frozen_band_fit.json').read_text(encoding='utf8'));ix=frozen['best']['indices']
    spec={'anchors_hz':ANCHORS,'weights':np.array(frozen['best']['weights'])[ix].tolist()};report=[]
    for track in full_tracks():
        folder=WORK/'turkish'/track['id'];out=folder/'comparison';out.mkdir(exist_ok=True)
        required=sorted(set([0,1,2,4]+ix))
        if ready_only and any(not (folder/f'candidate_{i}.npy').exists() for i in required):continue
        with np.load(folder/'reference.npz') as ref:source=ref['source']
        def candidate(i):return np.load(folder/f'candidate_{i}.npy').astype(np.float64)
        v1=sum(BASE[i]*candidate(i) for i in (0,2,4));current=sum(CURRENT[i]*candidate(i) for i in (0,1,2,4))
        band=combine_frequency(source,[candidate(i) for i in ix],spec)[0]
        row={**track,'systems':{}}
        for name,vocal in [('V1',v1),('V2_current',current),('V2_band_candidate',band)]:
            instrumental=source-vocal
            sf.write(out/f'{name}_Vocals.wav',vocal,RATE,subtype='FLOAT')
            sf.write(out/f'{name}_Instrumental.wav',instrumental,RATE,subtype='FLOAT')
            v,_=sf.read(out/f'{name}_Vocals.wav',dtype='float64',always_2d=True)
            a,_=sf.read(out/f'{name}_Instrumental.wav',dtype='float64',always_2d=True)
            if v.shape!=source.shape or a.shape!=source.shape or not np.isfinite(v).all() or not np.isfinite(a).all():
                raise ValueError('Full-song export changed duration/channels or contains invalid samples')
            sum_error=float(np.abs(v+a-source).max())
            if sum_error>1e-6:raise ValueError('Full-song export failed source consistency')
            row['systems'][name]={'frames':len(v),'seconds':len(v)/RATE,
                'sum_max_abs_error':sum_error,'finite':True,
                'peak_vocal':float(np.abs(v).max()),'peak_instrumental':float(np.abs(a).max()),
                'output_directory':str(out),'quality_measured':False}
        report.append(row);print('EXPORTED FULL',track['name'],flush=True)
    pilot.write_json(WORK/'turkish_results.json',{'tracks':report,'reference_stems_available':False,
        'complete':len(report)==len(full_tracks()),
        'note':'These are full-duration technical checks and A/B outputs, not proof of less stem loss.'})
    lines=['# Türkçe tam şarkı karşılaştırmaları','',
        'Üç sürüm aynı kaynak seviyesinde, tam uzunlukta float WAV olarak hazırlanır.',
        'Yeni frekans adayı deneysel: ortalama referans hatası daha düşük, fakat üretim kabul ölçütünü geçmedi.',
        'Gerçek stüdyo kanalları olmadığından bu dosyalar Türkçe kayıtlarda sıfır kayıp kanıtı değildir.','']
    labels={'V1':'Atlas V1','V2_current':'Mevcut V2','V2_band_candidate':'Yeni frekans adayı'}
    for row in report:
        lines.extend([f"## {row['name']}",'',f"Tam süre: {row['seconds']:.3f} saniye.",'',
            '| Sürüm | Vokal | Enstrümantal |','|---|---|---|'])
        for name,result in row['systems'].items():
            path=Path(result['output_directory'])
            v=(path/f'{name}_Vocals.wav').as_posix();a=(path/f'{name}_Instrumental.wav').as_posix()
            lines.append(f'| {labels[name]} | [Dinle](<{v}>) | [Dinle](<{a}>) |')
        lines.append('')
    (WORK/'KARSILASTIRMA.md').write_text('\n'.join(lines),encoding='utf8')


def export_ready():
    full_export(ready_only=True)


def export_report():
    report=json.loads((WORK/'band_results.json').read_text(encoding='utf8'))
    report['manifest']=json.loads((WORK/'manifest.json').read_text(encoding='utf8'))
    report['turkish']=json.loads((WORK/'turkish_results.json').read_text(encoding='utf8'))
    if not report['turkish']['complete']:raise ValueError('Full-song experiment is incomplete')
    report['provenance']={'previous_models':json.loads((ROOT/'docs/atlas-studio-v2-benchmark.json').read_text(encoding='utf8'))['provenance'],
        'new_models':[], 'new_inferences':len(list((WORK/'references').rglob('timing_*.json'))),
        'reused_inferences':40}
    def digest(path):
        h=hashlib.sha256()
        with path.open('rb') as handle:
            for chunk in iter(lambda:handle.read(1024*1024),b''):h.update(chunk)
        return h.hexdigest()
    for model,filename in [(MODELS[5],'bs_roformer_revive2.ckpt'),(MODELS[6],'bs_roformer_revive3e.ckpt')]:
        paths=list((ROOT/'models').rglob(filename))
        if len(paths)!=1:raise ValueError('Ambiguous model checkpoint')
        path=paths[0];config=path.parent/'config_bs_roformer.yaml'
        report['provenance']['new_models'].append({'model':model,'file':path.relative_to(ROOT).as_posix(),
            'sha256':digest(path),'config_sha256':digest(config),
            'repository_revision':'3f912884cdf9cbe8549297ce465f86a38572236c'})
    report['provenance']['experiment_script_sha256']=digest(Path(__file__))
    report['provenance']['frequency_combiner_sha256']=digest(ROOT/'atlas_band_ensemble.py')
    for track in report['turkish']['tracks']:track['source_sha256']=digest(Path(track['file']))
    pilot.write_json(ROOT/'docs/atlas-studio-v2-expanded.json',report)
    print('REPORT EXPORTED; accepted:',report['accepted_for_production'],flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('phase',choices=['infer','fit','evaluate','full-base','full-infer','full-export','export-ready','export-report'])
    globals()[parser.parse_args().phase.replace('-','_')]()
