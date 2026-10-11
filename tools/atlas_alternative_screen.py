"""Development-only dual-output expert and nonlinear ensemble screening.

Never changes production or claims that inspected recordings are held out.
"""
import hashlib
import json
from pathlib import Path
import sys
import numpy as np
from scipy.signal import istft
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from tools import atlas_extended as e,atlas_refinement as r,atlas_benchmark as b
from tools.atlas_sdr_optimize import read,score,summary,eligible
from atlas_band_ensemble import spectrum,combine_frequency,FFT,HOP,RATE
WORK=ROOT/'cache/atlas_alternatives'
MODEL_CACHE=WORK
REV='2da74427d682a3df47a774378fc24d7a1a0cdaad'
MODEL='Experimental becruily Deux pinned'

def tracks():return read(ROOT/'cache/atlas_confirmation/manifest.json')['development'][:8]

def infer():
    import requests
    import core
    # Abort rather than compete with an active user separation.
    try:jobs=requests.get('http://127.0.0.1:8000/api/audio/jobs',timeout=10).json()['jobs']
    except requests.ConnectionError:
        # The offline benchmark does not depend on the web service being open.
        print('Web backend offline; continuing standalone benchmark',flush=True);jobs=[]
    if any(j.get('status') in ('running','queued','processing') for j in jobs):
        raise RuntimeError('User audio jobs are active')
    folder=MODEL_CACHE/'model';folder.mkdir(parents=True,exist_ok=True)
    for remote,local in [('becruily_deux.ckpt','becruily_deux.ckpt'),('config_deux_becruily.yaml','config_mel_band_roformer.yaml')]:
        target=folder/local
        if target.exists():continue
        url=f'https://huggingface.co/becruily/mel-band-roformer-deux/resolve/{REV}/{remote}'
        print('DOWNLOAD',remote,flush=True)
        with requests.get(url,stream=True,timeout=(30,120)) as response:
            response.raise_for_status()
            with target.with_suffix(target.suffix+'.tmp').open('wb') as out:
                for chunk in response.iter_content(1024*1024):out.write(chunk)
        target.with_suffix(target.suffix+'.tmp').replace(target)
    checkpoint=folder/'becruily_deux.ckpt'
    digest=hashlib.sha256(checkpoint.read_bytes()).hexdigest()
    if digest!='10255c02295bf3e3865d4ee50ff752d7b19b124ed5fd93b147babc4333eda3aa':
        raise RuntimeError('Published checkpoint hash mismatch')
    old=core.Separator.download_model_files
    def download(self,name,*args,**kwargs):
        if name=='becruily_deux.ckpt':
            return name,'MDXC',MODEL,str(checkpoint),str(folder/'config_mel_band_roformer.yaml')
        return old(self,name,*args,**kwargs)
    core.Separator.download_model_files=download
    core.roformer_models[MODEL]='becruily_deux.ckpt'
    if not (WORK/'provenance.json').exists():
        b.write_json(WORK/'provenance.json',{'repo':'becruily/mel-band-roformer-deux','revision':REV,'checkpoint_sha256':digest,'development_ids':[t['id'] for t in tracks()]})
    try:
        for t in tracks():
            print('DEVELOPMENT DEUX',t['name'],flush=True)
            e.infer_one(e.prepare_reference(t),9,{'model_key':MODEL,'estimate':'vocal'})
    finally:core.Separator.download_model_files=old

def reconstruct(z,length):
    return istft(z,fs=RATE,nperseg=FFT,noverlap=FFT-HOP,input_onesided=True,boundary=True)[1].T[:length]

def infer_xe():
    import requests,yaml,core
    from roformer_config import compatible_single_target_config
    repo='pcunwa/BS-Roformer-Leap'
    revision='4e47d6662ae82eaa8b4ac4329fe66099a843b48e'
    response=requests.get(f'https://huggingface.co/api/models/{repo}/revision/{revision}?blobs=true',timeout=30)
    response.raise_for_status();info=response.json();old=core.Separator.download_model_files
    provenance=[]
    for index,stem in [(10,'voc'),(11,'inst')]:
        folder=MODEL_CACHE/f'xe_{stem}';folder.mkdir(parents=True,exist_ok=True)
        checkpoint=folder/f'bs_leap_xe_{stem}.ckpt';remote='Xe/'+checkpoint.name
        expected=next(s['lfs']['sha256'] for s in info['siblings'] if s['rfilename']==remote)
        if not checkpoint.exists():
            print('DOWNLOAD XE',stem,flush=True)
            with requests.get(f'https://huggingface.co/{repo}/resolve/{revision}/{remote}',stream=True,timeout=(30,120)) as response:
                response.raise_for_status()
                with checkpoint.with_suffix('.tmp').open('wb') as out:
                    for chunk in response.iter_content(1024*1024):out.write(chunk)
            checkpoint.with_suffix('.tmp').replace(checkpoint)
        digest=hashlib.sha256(checkpoint.read_bytes()).hexdigest()
        if digest!=expected:raise RuntimeError('Xe hash mismatch')
        response=requests.get(f'https://huggingface.co/{repo}/resolve/{revision}/Xe/leap_xe_config_{stem}.yaml',timeout=30)
        response.raise_for_status();config=compatible_single_target_config(yaml.load(response.text,Loader=yaml.FullLoader))
        config['inference']['batch_size']=1
        path=folder/'config_bs_roformer.yaml';path.write_text(yaml.dump(config),encoding='utf8')
        name=f'Experimental Leap Xe {stem}'
        def download(self,filename,*args,**kwargs):
            if filename==checkpoint.name:return filename,'MDXC',name,str(checkpoint),str(path)
            return old(self,filename,*args,**kwargs)
        core.Separator.download_model_files=download;core.roformer_models[name]=checkpoint.name
        try:
            for t in tracks():
                print('DEVELOPMENT XE',stem,t['name'],flush=True)
                e.infer_one(e.prepare_reference(t),index,{'model_key':name,'estimate':'vocal' if stem=='voc' else 'inst'})
        finally:core.Separator.download_model_files=old
        provenance.append({'repo':repo,'revision':revision,'file':remote,'sha256':digest,'index':index})
    b.write_json(WORK/'xe_provenance.json',provenance)

def screen():
    preset=read(ROOT/'frontend/src/lib/atlas-studio-v2-preset.json')
    indices=[0,1,2,4,7,8];rows={};baseline=[]
    for t in tracks():
        ref,x=r.load(t,indices);current=combine_frequency(ref['source'],list(x),preset['frequency_weights'])[0]
        baseline.append(score(ref,current));z=np.stack([spectrum(w) for w in x]);center=spectrum(current)
        magnitude=np.abs(z);order=np.argsort(magnitude,axis=0)
        alternatives={
            'wave_median':np.median(x,axis=0),
            'complex_median':reconstruct(np.median(z.real,axis=0)+1j*np.median(z.imag,axis=0),len(current)),
            'magnitude_median':reconstruct(np.median(magnitude,axis=0)*np.exp(1j*np.angle(center)),len(current)),
            'complex_trimmed':reconstruct(np.take_along_axis(z,order,axis=0)[1:-1].mean(axis=0),len(current)),
        }
        # Local disagreement confidence, no reference-dependent weights.
        distance=np.abs(z-center[None]);scale=np.median(distance,axis=0)+1e-12
        for power in (1,2):
            weight=1/(1+(distance/scale[None])**power)
            alternatives[f'adaptive_{power}']=reconstruct((z*weight).sum(axis=0)/weight.sum(axis=0),len(current))
        new=e.WORK/'references'/t['id']/'candidate_9.npy'
        if new.exists():alternatives['deux']=np.load(new).astype(float)
        for index,name in [(10,'xe_vocal'),(11,'xe_instrumental')]:
            path=e.WORK/'references'/t['id']/f'candidate_{index}.npy'
            if path.exists():alternatives[name]=np.load(path).astype(float)
        if 'xe_vocal' in alternatives and 'xe_instrumental' in alternatives:
            alternatives['xe_pair_consistency']=(alternatives['xe_vocal']+alternatives['xe_instrumental'])/2
        src=spectrum(ref['source']);other=src-center
        for power in (1,2):
            a=np.abs(center)**power;c=np.abs(other)**power
            alternatives[f'wiener_{power}']=reconstruct(src*a/(a+c+1e-12),len(current))
        for name,wave in alternatives.items():
            for alpha in (.1,.25,.5,1.):
                key=f'{name}_{alpha}';rows.setdefault(key,[]).append(score(ref,current*(1-alpha)+wave*alpha))
        print('SCREENED',t['name'],flush=True)
    base=summary(baseline)
    results=[{'method':k,'count':len(v),'summary':summary(v),'gain_db':summary(v)['vocal']['sdr_db']-base['vocal']['sdr_db'],'content_safe':len(v)==len(baseline) and eligible(summary(v),base)} for k,v in rows.items() if len(v)==len(baseline)]
    results.sort(key=lambda q:q['gain_db'],reverse=True)
    result={'development_only':True,'tracks':tracks(),'baseline':base,'trials':results,'production_changed':False,
            'acceptance':'Development screening cannot establish superiority. Fresh frozen comparison requires >=0.2 dB mean gain, positive 95% paired interval, both SI-SDR and all four content proxies no worse.'}
    b.write_json(WORK/'screening.json',result)
    print(json.dumps(results[:5],indent=2),flush=True)

def fit():
    """Reuse the constrained optimizer with three truly new experts, on development only."""
    from tools import atlas_sdr_optimize as optimizer
    original=optimizer.read
    indices=[0,1,2,4,7,8,9,10,11]
    for t in tracks():
        if any(not (e.WORK/'references'/t['id']/f'candidate_{i}.npy').exists() for i in indices):
            raise RuntimeError('All development inferences must finish before fitting')
    def modified(path):
        result=original(path)
        if path.name=='atlas-studio-v2-preset.json':
            result['frequency_weights']['weights']+=[[0.]*10 for _ in range(3)]
        if path.name=='manifest.json':
            result['development']=tracks();result['candidate_indices']=indices
        return result
    optimizer.read=modified;optimizer.WORK=WORK/'constrained_fit'
    try:optimizer.main()
    finally:optimizer.read=original

def validation_manifest():
    path=WORK/'validation_manifest.json'
    if path.exists():return read(path)
    if not (WORK/'constrained_fit/frozen.json').exists():raise RuntimeError('Freeze before confirmation')
    existing={p.name for p in (e.WORK/'references').iterdir()}
    files=sorted((b.WORK/'dataset').glob('*/*.stem.mp4'),key=lambda p:hashlib.sha256(('atlas-alternatives-20261010:'+p.name).encode()).hexdigest())
    selected=[]
    for p in files:
        identifier=hashlib.sha256(p.name.encode()).hexdigest()[:12]
        if identifier not in existing:selected.append({'id':identifier,'name':p.stem.removesuffix('.stem'),'file':str(p.resolve()),'split':'evaluation'})
        if len(selected)==8:break
    if len(selected)!=8:raise RuntimeError('Eight previously uncached recordings required')
    result={'tracks':selected,'selection':'First eight previously uncached recordings in fixed SHA order; frozen candidate selected before any new inference or scoring. Model-training overlap unknown.'}
    b.write_json(path,result);return result

def validate_infer():
    selected=validation_manifest()['tracks']
    original=globals()['tracks'];globals()['tracks']=lambda:selected
    try:
        for t in selected:
            for index in [0,1,2,4,7,8]:
                print('UNSEEN BASELINE',t['name'],index,flush=True)
                e.infer_one(e.prepare_reference(t),index,e.MODELS[index])
        infer();infer_xe()
    finally:globals()['tracks']=original

def validate():
    target=WORK/'validation.json'
    if target.exists():raise RuntimeError('Confirmation already scored; never retune on it')
    plan=read(WORK/'confirmation_plan.json')
    if plan['candidates'] not in (['candidate','xe_half'],['candidate']):raise RuntimeError('Confirmation plan changed')
    frozen=read(WORK/'constrained_fit/frozen.json');chosen=frozen['selected']
    if not chosen:raise RuntimeError('No eligible candidate')
    preset=read(ROOT/'frontend/src/lib/atlas-studio-v2-preset.json')
    if hashlib.sha256((ROOT/'frontend/src/lib/atlas-studio-v2-preset.json').read_bytes()).hexdigest()!=frozen['preset_sha256']:
        raise RuntimeError('Production baseline changed')
    spec={'anchors_hz':preset['frequency_weights']['anchors_hz'],'weights':chosen['weights']};rows=[]
    for t in validation_manifest()['tracks']:
        ref,x=r.load(t,[0,1,2,4,7,8,9,10,11])
        waves={'current':combine_frequency(ref['source'],list(x[:6]),preset['frequency_weights'])[0],
               'candidate':combine_frequency(ref['source'],list(x),spec)[0]}
        if 'xe_half' in plan['candidates']:waves['xe_half']=.5*waves['current']+.5*x[7]
        rows.append({'id':t['id'],'name':t['name'],'systems':{name:score(ref,v) for name,v in waves.items()}})
    summaries={name:summary([row['systems'][name] for row in rows]) for name in waves}
    comparisons={}
    for name in plan['candidates']:
        delta=np.array([row['systems'][name]['vocal']['sdr_db']-row['systems']['current']['vocal']['sdr_db'] for row in rows])
        # Two frozen comparisons: Bonferroni-adjusted 97.5% intervals.
        interval=np.quantile(np.random.default_rng(20261010).choice(delta,(10000,len(delta)),replace=True).mean(axis=1),[.0125,.9875]).tolist()
        comparisons[name]={'mean_delta_db':float(delta.mean()),'bootstrap_97_5pct':interval,
            'accepted':bool(delta.mean()>=.2 and interval[0]>0 and eligible(summaries[name],summaries['current']))}
    delta=np.array([row['systems']['candidate']['vocal']['sdr_db']-row['systems']['current']['vocal']['sdr_db'] for row in rows])
    interval=comparisons['candidate']['bootstrap_97_5pct']
    passing=[name for name in plan['candidates'] if comparisons[name]['accepted']]
    selected=max(passing,key=lambda name:comparisons[name]['mean_delta_db']) if passing else None
    accepted=bool(selected)
    result={'rows':rows,'summary':summaries,'mean_delta_db':float(delta.mean()),'bootstrap_97_5pct':interval,'accepted':accepted,
            'comparisons':comparisons,'confirmation_plan':plan,'selected_confirmed':selected,
            'production_changed':False,'candidate_spec':spec,'limitations':['Eight short reference excerpts, not full-song Turkish stems','Unknown model-training overlap; no universal superiority or zero-loss claim']}
    b.write_json(target,result);print(json.dumps({k:v for k,v in result.items() if k not in ('rows','candidate_spec')},indent=2),flush=True)

def report():
    confirmation=read(WORK/'validation.json');fit_result=read(WORK/'constrained_fit/frozen.json')
    data={'date':'2026-10-10','development_screening':read(WORK/'screening.json'),
          'constrained_fit':fit_result,'confirmation_manifest':validation_manifest(),'confirmation':confirmation,
          'deux_provenance':read(WORK/'provenance.json'),'xe_provenance':read(WORK/'xe_provenance.json'),
          'candidate_indices':[0,1,2,4,7,8,9,10,11],
          'candidate_models':[e.MODELS[i] for i in [0,1,2,4,7,8]]+[
              {'model_key':MODEL,'estimate':'vocal'}, {'model_key':'Experimental Leap Xe voc','estimate':'vocal'},
              {'model_key':'Experimental Leap Xe inst','estimate':'inst'}],
          'baseline_note':'The optimizer snapshot pads baseline frequency weights with three zero rows; the deployed baseline itself still has six models.',
          'experiment_tool_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
          'production_preset_sha256':hashlib.sha256((ROOT/'frontend/src/lib/atlas-studio-v2-preset.json').read_bytes()).hexdigest()}
    b.write_json(ROOT/'docs/atlas-studio-v2-alternatives.json',data)
    print(json.dumps({'accepted':confirmation['accepted'],'delta_db':confirmation['mean_delta_db'],'interval':confirmation['bootstrap_97_5pct']},indent=2))

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('phase',choices=['infer','infer_xe','screen','fit','validate_infer','validate','report']);globals()[p.parse_args().phase]()
