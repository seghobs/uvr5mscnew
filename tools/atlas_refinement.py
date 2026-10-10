"""Second experiment: previous diagnostic sets become development, fresh audio stays sealed.

No parameter is selected from the fresh evaluation results. Mean content checks
compare BOTH V1 and the deployed V2. Original full mixes are never ground truth.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import time
import numpy as np
from scipy.optimize import minimize
from scipy.signal import istft

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from tools import atlas_extended as extended
from tools import atlas_benchmark as pilot
from atlas_band_ensemble import spectrum,combine_frequency,frequency_matrix,RATE,FFT,HOP

WORK=ROOT/'cache/atlas_refinement'
INDICES=[0,1,2,4]
BASE=extended.BASE[INDICES]
CURRENT=extended.CURRENT[INDICES]
GRIDS=[[0,250,1000,4000,22050],extended.ANCHORS]


def manifest():
    path=WORK/'manifest.json'
    if path.exists():return json.loads(path.read_text(encoding='utf8'))
    old=json.loads((pilot.WORK/'manifest.json').read_text(encoding='utf8'))['tracks']
    previous=extended.tracks()
    known={t['id']:t for t in old+previous}
    development=[]
    for t in known.values():
        file=Path(t['file'])
        if not file.is_absolute():file=pilot.WORK/'dataset'/file
        development.append({**t,'file':str(file.resolve()),'split':'development'})
    paths=list((pilot.WORK/'dataset'/'test').glob('*.stem.mp4'))
    paths.sort(key=lambda p:hashlib.sha256(('atlas-pilot-v1:'+p.name).encode()).hexdigest())
    fresh=[{'name':p.stem.removesuffix('.stem'),'file':str(p.resolve()),'split':'evaluation',
        'id':hashlib.sha256(p.name.encode()).hexdigest()[:12]} for p in paths[16:24]]
    if len(development)!=32 or len(fresh)!=8 or set(known)&{t['id'] for t in fresh}:
        raise ValueError('Development/evaluation separation failed')
    result={'models':[extended.MODELS[i] for i in INDICES], 'development':development,'evaluation':fresh,
        'method':'Previously inspected 32 recordings are DEVELOPMENT, never held-out evidence. Fresh fixed test[16:24] are evaluated once after freezing.',
        'acceptance':'Mean SDR gain >=0.2 dB over V1; positive paired bootstrap lower bounds over BOTH baselines; both mean SI-SDR and all four mean content proxies no worse than BOTH baselines.'}
    pilot.write_json(path,result)
    return result


def infer():
    selected=manifest()
    needed={i:extended.MODELS[i] for i in INDICES}
    needed.update(dict(zip(selected.get('candidate_indices',INDICES),selected['models'])))
    # Known development outputs are reused; only missing outputs use the GPU.
    for t in selected['development']+selected['evaluation']:
        folder=extended.prepare_reference(t)
        for i,model in needed.items():
            if (folder/f'candidate_{i}.npy').exists():continue
            print('INFER',t['split'],t['name'],i,flush=True)
            extended.infer_one(folder,i,model)


def load(t,indices=None):
    folder=extended.WORK/'references'/t['id']
    with np.load(folder/'reference.npz') as ref:
        result={k:ref[k] for k in ('source','vocal','instrumental')}
    if indices is None:indices=manifest().get('candidate_indices',INDICES)
    return result,np.stack([np.load(folder/f'candidate_{i}.npy').astype(np.float64) for i in indices])


def waveform_statistics(candidates,target,anchors):
    """Exact quadratic error of the actual STFT -> inverse-STFT production mix."""
    frequencies=np.fft.rfftfreq(FFT,1/RATE)
    basis=np.stack([np.interp(frequencies,anchors,row) for row in np.eye(len(anchors))],axis=1)
    waves=[]
    for candidate in candidates:
        transformed=spectrum(candidate)
        for column in basis.T:
            _,wave=istft(transformed*column[None,:,None],fs=RATE,nperseg=FFT,
                noverlap=FFT-HOP,input_onesided=True,boundary=True)
            waves.append(wave.T[:len(target)].ravel())
    waves=np.stack(waves);raw_energy=float(np.sum(target**2));energy=max(raw_energy,1e-12)
    return waves@waves.T/energy,waves@target.ravel()/energy,raw_energy/energy


def fit():
    configuration=manifest();development=configuration['development']
    grids=configuration.get('anchor_grids',GRIDS)
    spectra=[];statistics={len(a):[] for a in grids};current_errors=[]
    control_content={'v1':np.zeros(4),'current':np.zeros(4)}
    candidate_indices=configuration.get('candidate_indices',INDICES)
    count=len(candidate_indices)
    for t in development:
        ref,candidates=load(t)
        x=np.stack([spectrum(c)[:,::4,::4] for c in candidates]);v=spectrum(ref['vocal'])[:,::4,::4]
        src=spectrum(ref['source'])[:,::4,::4];inst=src-v
        controls=candidates if candidate_indices==INDICES else load(t,INDICES)[1]
        current=np.tensordot(CURRENT,controls,axes=(0,0))
        current_error=float(np.sum((current-ref['vocal'])**2))/max(float(np.sum(ref['vocal']**2)),1e-12)
        current_errors.append(current_error)
        for name,wave in [('v1',np.tensordot(BASE,controls,axes=(0,0))),('current',current)]:
            out=spectrum(wave)[:,::4,::4]
            for j,(target,estimate) in enumerate(((v,out),(inst,src-out))):
                delta=np.abs(estimate)-np.abs(target);denom=max(float(np.sum(np.abs(target)**2)),1e-12)
                control_content[name][j*2]+=float(np.sum(np.minimum(delta,0)**2))/denom/len(development)
                control_content[name][j*2+1]+=float(np.sum(np.maximum(delta,0)**2))/denom/len(development)
        scale=(1/max(float(np.sum(np.abs(v)**2)),1e-12)+1/max(float(np.sum(np.abs(inst)**2)),1e-12))/(2*len(development))
        spectra.append((x,src,v,inst,scale))
        for anchors in grids:
            folder=extended.WORK/'references'/t['id']
            inputs=[folder/'reference.npz',*[folder/f'candidate_{i}.npy' for i in candidate_indices]]
            fingerprint=hashlib.sha256(json.dumps({'anchors':anchors,'FFT':FFT,'HOP':HOP,'RATE':RATE,
                'combiner':hashlib.sha256((ROOT/'atlas_band_ensemble.py').read_bytes()).hexdigest(),
                'indices':candidate_indices,'inputs':[(p.stat().st_size,p.stat().st_mtime_ns) for p in inputs]}).encode()).hexdigest()[:16]
            cache=folder/f'exact_waveform_{fingerprint}.npz'
            if cache.exists():
                with np.load(cache) as data:g=data['gram'];b=data['linear'];c=float(data['constant'])
            else:
                g,b,c=waveform_statistics(candidates,ref['vocal'],anchors)
                np.savez(cache,gram=g,linear=b,constant=c)
            ratio=float(np.sum(ref['vocal']**2))/max(float(np.sum(ref['instrumental']**2)),1e-12)
            if configuration.get('objective_mode')=='relative_error':
                error=max(current_error,1e-12)
                scale=1/(len(development)*error)
            else:scale=(1+ratio)/(2*len(development))
            statistics[len(anchors)].append((g,b,c,scale))
        print('EXACT STATISTICS',t['name'],flush=True)
    trials=[]
    for anchors in grids:
        n=len(anchors);freq=np.fft.rfftfreq(FFT,1/RATE)[::4]
        basis=np.stack([np.interp(freq,anchors,row) for row in np.eye(n)],axis=1)
        gram=np.zeros((count*n,count*n));linear=np.zeros(count*n);constant=0.
        for g,b,c,scale in statistics[n]:gram+=g*scale;linear+=b*scale;constant+=c*scale
        def content(w,derivatives=False):
            value=np.zeros(4);jac=np.zeros((4,count,n))
            for x,src,v,inst,_ in spectra:
                if derivatives:
                    p,j=extended.content_statistics(w,basis,x,src,np.abs(v),np.abs(inst),True)
                    value+=p;jac+=j
                else:value+=extended.content_statistics(w,basis,x,src,np.abs(v),np.abs(inst))
            return (value/len(spectra),jac/len(spectra)) if derivatives else value/len(spectra)
        default_initial=[CURRENT[INDICES.index(i)] if i in INDICES else 0 for i in candidate_indices]
        initial=np.asarray(configuration.get('initial_weights',default_initial),dtype=float)
        if initial.shape!=(count,) or not np.isfinite(initial).all() or (initial<0).any() or not np.isclose(initial.sum(),1):
            raise ValueError('Invalid development-only initialization weights')
        prior=np.repeat(initial[:,None],n,axis=1)
        margin=np.asarray(configuration.get('content_margin',[0,0,0,0]),dtype=float)
        if margin.shape!=(4,) or not np.isfinite(margin).all() or (margin<0).any() or (margin>=1).any():
            raise ValueError('Invalid development content safety margin')
        limit=np.minimum(control_content['v1'],control_content['current'])*(1-margin)
        equality=np.tile(np.eye(n),(1,count))
        per_gram=np.stack([s[0] for s in statistics[n]]);per_linear=np.stack([s[1] for s in statistics[n]])
        per_constant=np.array([s[2] for s in statistics[n]])
        prior_flat=prior.ravel()
        regression=float(configuration.get('max_development_regression_db',0))
        if not np.isfinite(regression) or regression<0:raise ValueError('Invalid per-recording development cap')
        per_limit=np.array(current_errors)*10**(regression/10)
        def recording_constraint(w):
            return per_limit-(np.einsum('i,tij,j->t',w,per_gram,w)-2*per_linear@w+per_constant)
        def recording_jac(w):return -2*(np.einsum('tij,j->ti',per_gram,w)-per_linear)
        for regularization in configuration.get('regularizations',(.001,.01,.1)):
            memo={}
            def constraint(flat):
                if 'x' not in memo or not np.array_equal(flat,memo['x']):
                    p,j=content(flat.reshape(count,n),True)
                    memo.update(x=flat.copy(),value=limit-p,jac=-j.reshape(4,count*n))
                return memo
            def objective(flat):
                w=flat.reshape(count,n)
                # Stronger smoothing and anchoring discourage frequency overfitting.
                return float(flat@gram@flat-2*linear@flat+constant
                    +regularization*np.sum(np.diff(w,axis=1)**2)
                    +regularization*.1*np.sum((w-prior)**2))
            def gradient(flat):
                w=flat.reshape(count,n);delta=np.diff(w,axis=1);smooth=np.zeros_like(w)
                smooth[:,:-1]-=delta;smooth[:,1:]+=delta
                return 2*(gram@flat-linear)+2*regularization*smooth.ravel()+.2*regularization*(w-prior).ravel()
            print('FIT START',n,regularization,flush=True)
            iteration=[0]
            def progress(flat):
                iteration[0]+=1
                if iteration[0]%20==0:
                    violation=max(0.,float(-constraint(flat)['value'].min()),float(-recording_constraint(flat).min()))
                    print('FIT PROGRESS',n,regularization,iteration[0],'violation',violation,flush=True)
            start=prior
            if configuration.get('optimizer_initial_frequency_weights') is not None:
                start=frequency_matrix(configuration['optimizer_initial_frequency_weights'],count,np.asarray(anchors))
            solved=minimize(objective,start.ravel(),jac=gradient,method='SLSQP',bounds=[(0,1)]*(count*n),callback=progress,
                constraints=[{'type':'eq','fun':lambda w:equality@w-1,'jac':lambda w:equality},
                    {'type':'ineq','fun':lambda w:constraint(w)['value'],'jac':lambda w:constraint(w)['jac']},
                    {'type':'ineq','fun':recording_constraint,'jac':recording_jac}],
                options={'ftol':1e-9,'maxiter':int(configuration.get('max_iterations',100))})
            if not solved.success:
                print('FIT FAILED',n,regularization,solved.message,flush=True);continue
            w=solved.x.reshape(count,n);p=content(w)
            loss=float(solved.x@gram@solved.x-2*linear@solved.x+constant)
            trials.append({'anchors_hz':anchors,'weights':w.tolist(),'regularization':regularization,
                'loss':loss,'proxy':p.tolist(),'limit':limit.tolist(),
                'worst_development_error_slack':float(np.min(recording_constraint(solved.x))),
                'safe':bool(np.all(p<=limit+1e-8) and np.min(recording_constraint(solved.x))>=-1e-8)})
            print('FIT',n,regularization,'loss',loss,'proxy',p.tolist(),flush=True)
    eligible=[t for t in trials if t['safe']]
    if not eligible:raise RuntimeError('No solution meets both baseline content constraints')
    best=min(eligible,key=lambda t:t['loss'])
    pilot.write_json(WORK/'frozen_fit.json',{'best':best,'trials':trials,'indices':candidate_indices,
        'baseline_indices':INDICES,
        'development_ids':[t['id'] for t in development],'evaluation_used_for_fitting':False,
        'objective_mode':configuration.get('objective_mode','normalized_stem_error'),
        'max_development_regression_db':configuration.get('max_development_regression_db',0),
        'method':'Exact production waveform error; per-recording development error cap; mean content constraints against both baselines'})
    print('FROZEN',best,flush=True)


def accepted(report):
    summary=report['summary'];candidate=summary['refined']
    return (all(report['comparisons'][baseline]['mean_sdr_delta_db']>0 for baseline in ('v1','current'))
        and all(report['comparisons'][baseline]['bootstrap_95pct'][0]>0 for baseline in ('v1','current'))
        and all(candidate[stem]['si_sdr_db']>=summary[baseline][stem]['si_sdr_db']
            for baseline in ('v1','current') for stem in ('vocal','instrumental'))
        and all(candidate[stem][k]<=summary[baseline][stem][k]+1e-8
            for baseline in ('v1','current') for stem in ('vocal','instrumental')
            for k in ('spectral_deficit','spectral_excess')))


def select_development():
    """Select on known recordings using full waveform and full STFT metrics.

    This can run only BEFORE opening validation. Sparse optimization proxies
    never replace the real production-output content checks.
    """
    if (WORK/'evaluation.json').exists():raise RuntimeError('Cannot select after validation was opened')
    frozen=json.loads((WORK/'frozen_fit.json').read_text(encoding='utf8'))
    trials=[t for t in frozen['trials'] if t['safe']]
    systems=['v1','current',*[str(i) for i in range(len(trials))]]
    sums={name:{s:{k:0. for k in ('sdr_db','si_sdr_db','spectral_deficit','spectral_excess')}
        for s in ('vocal','instrumental')} for name in systems}
    development=manifest()['development']
    for t in development:
        ref,candidates=load(t);transformed=[spectrum(c) for c in candidates]
        prepared={s:(ref[s],np.abs(spectrum(ref[s])),ref[s]-ref[s].mean(axis=0)) for s in ('vocal','instrumental')}
        def score(name,vocal):
            for stem,wave in [('vocal',vocal),('instrumental',ref['source']-vocal)]:
                target,magnitude,center=prepared[stem];energy=max(float(np.sum(target**2)),1e-12)
                e=wave-wave.mean(axis=0)
                projection=float(np.sum(center*e))/max(float(np.sum(center**2)),1e-12)*center
                difference=np.abs(spectrum(wave))-magnitude;denom=max(float(np.sum(magnitude**2)),1e-12)
                values={'sdr_db':float(10*np.log10(energy/max(float(np.sum((wave-target)**2)),1e-12))),
                    'si_sdr_db':float(10*np.log10(max(float(np.sum(projection**2)),1e-12)/max(float(np.sum((e-projection)**2)),1e-12))),
                    'spectral_deficit':float(np.sum(np.minimum(difference,0)**2)/denom),
                    'spectral_excess':float(np.sum(np.maximum(difference,0)**2)/denom)}
                for k,v in values.items():sums[name][stem][k]+=v/len(development)
        controls=candidates if manifest().get('candidate_indices',INDICES)==INDICES else load(t,INDICES)[1]
        score('v1',np.tensordot(BASE,controls,axes=(0,0)))
        score('current',np.tensordot(CURRENT,controls,axes=(0,0)))
        for i,trial in enumerate(trials):
            frequencies=np.fft.rfftfreq(FFT,1/RATE)
            weights=extended.frequency_matrix(trial,len(candidates),frequencies);merged=np.zeros_like(transformed[0])
            for j,value in enumerate(transformed):merged+=value*weights[j][None,:,None]
            _,wave=istft(merged,fs=RATE,nperseg=FFT,noverlap=FFT-HOP,input_onesided=True,boundary=True)
            score(str(i),wave.T[:len(ref['source'])])
        print('DEVELOPMENT FULL SCORE',t['name'],flush=True)
    eligible=[]
    for i,trial in enumerate(trials):
        candidate=sums[str(i)]
        safe=all(candidate[s][k]<=sums[b][s][k]+1e-8 for b in ('v1','current')
            for s in ('vocal','instrumental') for k in ('spectral_deficit','spectral_excess'))
        safe &= all(candidate[s]['si_sdr_db']>=sums[b][s]['si_sdr_db'] for b in ('v1','current') for s in ('vocal','instrumental'))
        if safe:eligible.append(i)
    pilot.write_json(WORK/'development_selection.json',{'summaries':sums,'eligible':eligible,
        'evaluation_used':False,'development_ids':[t['id'] for t in development]})
    if not eligible:raise RuntimeError('No candidate passes full development content checks against BOTH baselines')
    chosen=max(eligible,key=lambda i:sums[str(i)]['vocal']['sdr_db'])
    frozen['best']=trials[chosen];frozen['development_selection']={'trial':chosen,'summary':sums[str(chosen)],'evaluation_used':False}
    pilot.write_json(WORK/'frozen_fit.json',frozen)
    print('SELECTED FULL DEVELOPMENT',chosen,sums[str(chosen)],flush=True)


def evaluate():
    if (WORK/'evaluation.json').exists():raise RuntimeError('Evaluation already opened. Do not rerun selection against this holdout.')
    for t in manifest()['evaluation']:
        folder=extended.WORK/'references'/t['id']
        if any(not (folder/f'candidate_{i}.npy').exists() for i in set(INDICES+manifest().get('candidate_indices',INDICES))):
            raise RuntimeError('Evaluation inference is incomplete; wait for all models before scoring')
    frozen=json.loads((WORK/'frozen_fit.json').read_text(encoding='utf8'));spec={k:frozen['best'][k] for k in ('anchors_hz','weights')}
    rows=[]
    for t in manifest()['evaluation']:
        ref,candidates=load(t)
        controls=candidates if manifest().get('candidate_indices',INDICES)==INDICES else load(t,INDICES)[1]
        outputs={'v1':np.tensordot(BASE,controls,axes=(0,0)),
            'current':np.tensordot(CURRENT,controls,axes=(0,0)),
            'refined':combine_frequency(ref['source'],list(candidates),spec)[0]}
        row={**t,'systems':{name:{stem:pilot.metrics(ref[stem],wave) for stem,wave in
            [('vocal',vocal),('instrumental',ref['source']-vocal)]} for name,vocal in outputs.items()}}
        rows.append(row);print('EVALUATED',t['name'],flush=True)
    summary={name:{stem:{k:float(np.mean([r['systems'][name][stem][k] for r in rows]))
        for k in rows[0]['systems'][name][stem]} for stem in ('vocal','instrumental')} for name in outputs}
    comparisons={};rng=np.random.default_rng(20261012)
    for name in ('v1','current'):
        delta=np.array([r['systems']['refined']['vocal']['sdr_db']-r['systems'][name]['vocal']['sdr_db'] for r in rows])
        comparisons[name]={'mean_sdr_delta_db':float(delta.mean()),'improved':int(np.sum(delta>0)),
            'bootstrap_95pct':np.quantile(np.mean(rng.choice(delta,(10000,len(delta)),replace=True),axis=1),[.025,.975]).tolist()}
    report={'manifest':manifest(),'fit':frozen,'spec':spec,'summary':summary,'comparisons':comparisons,'rows':rows,
        'limitations':['Fresh held-out from parameter fitting only; model training overlap unknown',
            'Short non-Turkish reference excerpts; full Turkish mixes do not establish true stem loss',
            'Mean acceptance is not superiority on every song or zero loss']}
    report['accepted']=accepted(report)
    report['target_gain_0_2db_reached']=report['comparisons']['v1']['mean_sdr_delta_db']>=.2
    pilot.write_json(WORK/'evaluation.json',report)
    print(json.dumps({'comparisons':comparisons,'summary':summary,'accepted':report['accepted']},indent=2),flush=True)


def recipe(report):
    models=[]
    for model,row in zip(report['manifest']['models'],report['spec']['weights']):
        models.append({**model,'weight':float(np.mean(row))})
    return {'id':'atlas_studio_v2','name':'Atlas Studio V2','models':models,
        'frequency_weights':report['spec'],
        'calibration':{'report':'docs/atlas-studio-v2-refinement.json',
            'accepted':report['accepted'],'scope':'Mean metrics on frozen held-out reference excerpts; no zero-loss guarantee'}}


def export_report():
    report=json.loads((WORK/'evaluation.json').read_text(encoding='utf8'))
    old=json.loads((ROOT/'docs/atlas-studio-v2-benchmark.json').read_text(encoding='utf8'))
    def digest(path):
        hasher=hashlib.sha256()
        with path.open('rb') as handle:
            for chunk in iter(lambda:handle.read(1024*1024),b''):hasher.update(chunk)
        return hasher.hexdigest()
    report['provenance']={**old['provenance'],
        'model_files':[m for m in old['provenance']['model_files']
            if m['model_key'] in {m['model_key'] for m in report['manifest']['models']}],
        'export_script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'combiner_sha256':hashlib.sha256((ROOT/'atlas_band_ensemble.py').read_bytes()).hexdigest(),
        'production_combiner_sha256':hashlib.sha256((ROOT/'atlas_studio.py').read_bytes()).hexdigest()}
    report['provenance']['prior_pilot_core_sha256']=old['provenance']['core_sha256']
    report['provenance']['core_sha256']=digest(ROOT/'core.py')
    report['provenance']['confirmation_inference_core_sha256']=digest(ROOT/'core.py')
    report['provenance']['development_cache_note']='Original experts reuse prior pilot/extended outputs where available; final confirmation outputs were generated with the current core. Adapters leave full-window original expert inputs unchanged.'
    discovery=report['manifest'].get('discovery_report')
    if discovery:
        previous=json.loads((ROOT/discovery).read_text(encoding='utf8'))
        if previous['spec']!=report['spec']:raise ValueError('Final recipe differs from frozen discovery recipe')
        report['discovery']={'accepted':previous['accepted'],'comparisons':previous['comparisons'],
            'summary':previous['summary'],'ids':[t['id'] for t in previous['rows']],
            'source_report_sha256':digest(ROOT/discovery)}
    report['provenance']['short_input_adapter_sha256']=digest(ROOT/'roformer_input.py')
    report['provenance']['model_config_adapter_sha256']=digest(ROOT/'roformer_config.py')
    for model in report['manifest']['models']:
        if not model['model_key'].startswith('BS-Roformer-Resurrection '):continue
        isolated=ROOT/'models'/('roformer_custom_'+hashlib.sha256(model['model_key'].encode()).hexdigest()[:12])
        checkpoints=list(isolated.glob('*.ckpt'))
        if len(checkpoints)!=1:raise ValueError('New model checkpoint identity is ambiguous')
        checkpoint=checkpoints[0];effective=isolated/'config_bs_roformer.yaml'
        report['provenance']['model_files'].append({**model,'file':checkpoint.relative_to(ROOT).as_posix(),
            'bytes':checkpoint.stat().st_size,'sha256':digest(checkpoint),
            'config':effective.relative_to(ROOT).as_posix(),'config_sha256':digest(effective),
            'repository_revision':'8fc1a62f765e3e738db8394d7e87e379acc4c675'})
    invocation=WORK/'invocation_provenance.json'
    report['provenance']['fit_invocation']=json.loads(invocation.read_text(encoding='utf8')) if invocation.exists() else {'fit_code_sha256_recorded':False}
    turkish=WORK/'turkish_results.json'
    if turkish.exists():
        report['turkish']=json.loads(turkish.read_text(encoding='utf8'))
        for t in report['turkish']['tracks']:t['source_sha256']=digest(Path(t['file']))
    live=WORK/'live_check/results.json'
    if live.exists():report['live_check']=json.loads(live.read_text(encoding='utf8'))
    report['recipe']=recipe(report)
    pilot.write_json(ROOT/'docs/atlas-studio-v2-refinement.json',report)
    pilot.write_json(WORK/'candidate_preset.json',report['recipe'])
    lines=['# Atlas Studio V2: son iyileştirme doğrulaması','',
        f"Karar: **{'Kabul edildi' if report['accepted'] else 'Kabul edilmedi'}**. {len(report['manifest']['models'])} model; {len(report['fit']['development_ids'])} geliştirme kaydı, {len(report['rows'])} ayrı doğrulama kaydı.",'',
        'Ağırlıklar doğrulama sonuçları açılmadan sabitlendi. Karşılaştırmalar aynı kaynak, seviye ve %87,5 örtüşme koşullarında yapıldı.','',
        '| Ölçüm | V1 | Önceki V2 | Yeni aday |','|---|---:|---:|---:|']
    for stem,label in [('vocal','Vokal'),('instrumental','Enstrümantal')]:
        for metric,description in [('sdr_db','SDR (dB, yüksek iyi)'),('si_sdr_db','SI-SDR (dB, yüksek iyi)'),
                                   ('spectral_deficit','eksik içerik göstergesi (düşük iyi)'),('spectral_excess','fazla içerik göstergesi (düşük iyi)')]:
            values=[report['summary'][name][stem][metric] for name in ('v1','current','refined')]
            lines.append(f"| {label} {description} | "+' | '.join(f'{v:.6f}' for v in values)+' |')
    lines.extend(['','| Karşılaştırma | Ortalama SDR farkı | %95 eşleştirilmiş bootstrap aralığı | İyileşen kayıt |',
                  '|---|---:|---:|---:|'])
    for name,label in [('v1','V1'),('current','Önceki V2')]:
        c=report['comparisons'][name];lo,hi=c['bootstrap_95pct']
        lines.append(f"| {label} | {c['mean_sdr_delta_db']:+.6f} dB | [{lo:+.6f}, {hi:+.6f}] dB | {c['improved']}/{len(report['rows'])} |")
    lines.extend(['','SDR doğrudan örnek hata oranıdır; MVSEP veya BSSEval puanlarıyla aynı ölçüm değildir. Spektral göstergeler gerçek sızıntı yüzdeleri değildir.',
        '', 'Kabul için iki sürüme karşı pozitif SDR kazancı ve pozitif güven aralığı alt sınırı; iki kanalın ortalama SI-SDR ve dört içerik göstergesinin tamamında kötüleşmeme aranır. 0,2 dB ayrıca hedef olarak kaydedilir.',
        '', 'Bunlar kısa referans kayıtlarının ortalamalarıdır. Model eğitim verileriyle örtüşme bilinmiyor. Türkçe tam şarkılarda gerçek stüdyo kanalları olmadığı için kayıp veya sızıntı oranı ölçülemez. Her şarkıda üstünlük ve sıfır kayıp garantisi verilmez.',
        '', '[Önceki başarısız denemeler dahil deney geçmişi](atlas-studio-v2-refinement-attempts.md). Checkpoint kimlikleri, ağırlıklar, tek tek kayıt sonuçları ve çalışma koşulları [JSON raporunda](atlas-studio-v2-refinement.json).'])
    if 'turkish' in report:
        duration=sum(t['seconds'] for t in report['turkish']['tracks'])
        error=max(t['sum_max_abs_error'] for t in report['turkish']['tracks'])
        lines.extend(['',f"Üç Türkçe tam şarkı: {duration:.3f} saniye. Gerçek üretim birleştiricisiyle süre/kanal boyutları korundu; çıktı toplamının kaynakla en büyük mutlak örnek farkı {error:.3g}. Bu kontroller seslerin doğru kanala atanmasını kanıtlamaz."])
    if 'live_check' in report:
        check=report['live_check']
        lines.extend(['',f"Canlı API isteği: {len(check['models'])} gerçek model, {check['frames']} stereo örnek, {check['rate']} Hz. İki WAV oluşturuldu; kaynak toplamı farkı {check['sum_max_abs_error']:.3g}. Bu bir çalışma testi, ayrı kalite benchmarkı değildir."])
    (ROOT/'docs/atlas-studio-v2-refinement.md').write_text('\n'.join(lines)+'\n',encoding='utf8')
    print('EXPORTED accepted:',report['accepted'],flush=True)


def full_export():
    import soundfile as sf
    from atlas_studio import combine
    report=json.loads((WORK/'evaluation.json').read_text(encoding='utf8'));preset=recipe(report)
    rows=[];lines=['# Yeni V2 tam şarkı karşılaştırmaları','',
        'Aynı kaynak seviyesi ve tam uzunluk. Gerçek stüdyo kanalları yoktur; bu dosyalar sıfır kayıp kanıtı değildir.','']
    for t in extended.full_tracks():
        folder=extended.WORK/'turkish'/t['id'];out=WORK/'turkish'/t['id'];out.mkdir(parents=True,exist_ok=True)
        with np.load(folder/'reference.npz') as ref:source=ref['source']
        estimates=[np.load(folder/f'candidate_{i}.npy').astype(np.float64) for i in manifest().get('candidate_indices',INDICES)]
        estimates=[source-e if m['estimate']=='inst' else e for e,m in zip(estimates,preset['models'])]
        vocal,inst=combine(source,estimates,preset)
        del estimates
        for name,wave in [('Vocals',vocal),('Instrumental',inst)]:sf.write(out/f'V2_refined_{name}.wav',wave,RATE,subtype='FLOAT')
        v,vr=sf.read(out/'V2_refined_Vocals.wav',always_2d=True,dtype='float64')
        a,ar=sf.read(out/'V2_refined_Instrumental.wav',always_2d=True,dtype='float64')
        error=float(np.abs(v+a-source).max())
        if vr!=RATE or ar!=RATE or v.shape!=source.shape or a.shape!=source.shape or error>1e-6 or not np.isfinite(v).all() or not np.isfinite(a).all():
            raise ValueError('Full-song production combiner failed duration/finite/source check')
        rows.append({**t,'frames':len(v),'sum_max_abs_error':error,'output_directory':str(out),
            'reference_stems_available':False,'quality_measured':False})
        lines.extend([f"## {t['name']}",'','| Sürüm | Vokal | Enstrümantal |','|---|---|---|'])
        for label,path,prefix in [('V1',folder/'comparison','V1'),('Önceki V2',folder/'comparison','V2_current'),('Yeni V2',out,'V2_refined')]:
            lines.append(f"| {label} | [Dinle](<{(path/f'{prefix}_Vocals.wav').as_posix()}>) | [Dinle](<{(path/f'{prefix}_Instrumental.wav').as_posix()}>) |")
        lines.append('');print('FULL EXPORTED',t['name'],flush=True)
        del source,vocal,inst,v,a
    pilot.write_json(WORK/'turkish_results.json',{'tracks':rows,'complete':len(rows)==3,'quality_measured':False})
    (WORK/'KARSILASTIRMA.md').write_text('\n'.join(lines),encoding='utf8')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('phase',choices=['infer','fit','select-development','evaluate','export-report','full-export'])
    parser.add_argument('--work-dir',type=Path)
    args=parser.parse_args()
    if args.work_dir is not None:WORK=args.work_dir.resolve()
    globals()[args.phase.replace('-','_')]()
