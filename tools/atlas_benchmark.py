"""Reproducible reference-stem pilot. Fit on train excerpts, then freeze before test.

Audio/candidate caches remain local. The report is not an unseen-song guarantee.
Run from repo root: env/python tools/atlas_benchmark.py prepare|infer|fit|evaluate|export
"""
import argparse
import hashlib
import itertools
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import zipfile

import numpy as np
import soundfile as sf
from scipy.optimize import minimize
from scipy.signal import stft

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
WORK = ROOT / 'cache/atlas_benchmark'
# Freeze candidate identities independently of the preset we will update.
MODELS = [
    {'model_type':'roformer','model_key':'BS-Roformer-Viperx-1297','estimate':'vocal'},
    {'model_type':'roformer','model_key':'BS Roformer Leap Vocals by pcunwa','estimate':'vocal'},
    {'model_type':'roformer','model_key':'MelBand Roformer Kim | FT 2 Bleedless by unwa','estimate':'vocal'},
    {'model_type':'roformer','model_key':'MelBand Roformer | Vocals by becruily','estimate':'vocal'},
    {'model_type':'roformer','model_key':'MelBand Roformer Kim | Inst V2 by Unwa','estimate':'inst'},
]
RATE = 44100
DATASET_URL = 'https://github.com/sigsep/sigsep-mus-db/releases/download/v0.4.0/MUSDB18-7-STEMS.zip'


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding='utf8')
    os.replace(temp, path)


def prepare():
    import requests
    WORK.mkdir(parents=True,exist_ok=True)
    archive=WORK/'MUSDB18-7-STEMS.zip'
    if not archive.exists():
        temp=archive.with_suffix('.part')
        try:
            with requests.get(DATASET_URL,stream=True,timeout=(15,60)) as response:
                response.raise_for_status()
                with temp.open('wb') as handle:
                    for chunk in response.iter_content(1024*1024): handle.write(chunk)
            os.replace(temp,archive)
        finally:
            temp.unlink(missing_ok=True)
    destination=(WORK/'dataset').resolve()
    with zipfile.ZipFile(archive) as dataset:
        for member in dataset.infolist():
            target=(destination/member.filename).resolve()
            if not target.is_relative_to(destination):
                raise ValueError('Archive path escapes dataset directory')
        dataset.extractall(destination)
    tracks()  # Freeze split selection before inference/optimization.


def tracks():
    manifest = WORK / 'manifest.json'
    if manifest.exists():
        data=json.loads(manifest.read_text(encoding='utf8'))
        identities=lambda models:[(m['model_type'],m['model_key'],m['estimate']) for m in models]
        if identities(data['models'])!=identities(MODELS) or data['overlap_factor']!=8:
            raise ValueError('Cached benchmark configuration differs from this experiment')
        return data['tracks']
    selected = []
    for split in ('train', 'test'):
        paths = list((WORK/'dataset'/split).glob('*.stem.mp4'))
        if len(paths) < 8:
            raise ValueError('Official MUSDB 7s dataset is missing')
        paths.sort(key=lambda p: hashlib.sha256(('atlas-pilot-v1:'+p.name).encode()).hexdigest())
        for path in paths[:8]:
            selected.append({'name': path.stem.removesuffix('.stem'), 'split': split,
                             'file': path.relative_to(WORK).as_posix(),
                             'id': hashlib.sha256(path.name.encode()).hexdigest()[:12]})
    write_json(manifest, {'dataset_url': DATASET_URL,
                         'selection': 'sha256(atlas-pilot-v1:filename), first 8 per official split',
                         'models': MODELS, 'overlap_factor': 8, 'tracks': selected})
    return selected


def decode(track):
    folder = WORK/'estimates'/track['id']
    folder.mkdir(parents=True, exist_ok=True)
    reference = folder/'reference.npz'
    if reference.exists():
        return folder
    stems = []
    for stream in (1, 2, 3, 4):
        command = ['ffmpeg', '-v', 'error', '-i', str(WORK/track['file']),
                   '-map', f'0:a:{stream}', '-ac', '2', '-ar', str(RATE),
                   '-f', 'f32le', '-']
        result = subprocess.run(command, capture_output=True, check=True,
                                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        stems.append(np.frombuffer(result.stdout, dtype='<f4').reshape(-1, 2).astype(np.float64))
    if len({x.shape for x in stems}) != 1:
        raise ValueError('Reference stem shapes disagree')
    vocal = stems[3]
    instrumental = sum(stems[:3])
    source = vocal + instrumental  # Avoid the separately AAC-encoded mix's sum discrepancy.
    headroom = .25 / max(1., float(np.abs(source).max()))
    sf.write(folder/'input.wav', np.pad(source*headroom, ((0,max(0,16*RATE-len(source))), (0,0))), RATE, subtype='FLOAT')
    np.savez(reference, source=source, vocal=vocal, instrumental=instrumental, headroom=headroom)
    return folder


def infer():
    import core
    from studio_pro import classify_stem
    import torch
    if not torch.cuda.is_available():
        raise RuntimeError('CUDA unavailable; do not silently benchmark on CPU')
    # Use exactly the application's native window, headroom and overlap settings.
    for model_index, model in enumerate(MODELS):
        for index, track in enumerate(tracks()):
            folder = decode(track)
            target = folder/f'candidate_{model_index}.npy'
            if target.exists():
                continue
            with np.load(folder/'reference.npz') as ref:
                source = ref['source']; headroom = float(ref['headroom'])
            started = time.monotonic()
            print(f"INFER model={model_index+1}/5 track={index+1}/16 {track['name']}", flush=True)
            try:
                files = core.roformer_separator(str(folder/'input.wav'), model['model_key'], 'wav',
                    256, False, 8, 1, 1., 0., '', work_dir=str(folder),
                    overlap_factor=8, float_output=True)
                pair = {classify_stem(p): p for p in files}
                if set(pair) != {'vocal', 'inst'}:
                    raise ValueError('Incomplete model pair')
                estimate, rate = sf.read(pair[model['estimate']], always_2d=True, dtype='float64')
                if rate != RATE or estimate.shape != (max(16*RATE,len(source)),2) or not np.isfinite(estimate).all() or np.abs(estimate).max() >= .999:
                    raise ValueError('Output gain/timebase is invalid')
                estimate = estimate[:len(source)]/headroom
                candidate = source-estimate if model['estimate']=='inst' else estimate
                temp = target.with_suffix('.tmp.npy')
                np.save(temp, candidate.astype(np.float32)); os.replace(temp,target)
                write_json(folder/f'timing_{model_index}.json', {'seconds':time.monotonic()-started})
                for p in files:
                    Path(p).unlink(missing_ok=True)
            finally:
                core.clear_gpu_and_ram_cache()
            print(f'DONE seconds={time.monotonic()-started:.1f}', flush=True)


def load(track):
    folder = WORK/'estimates'/track['id']
    with np.load(folder/'reference.npz') as data:
        ref = {k:data[k] for k in ('source','vocal','instrumental')}
    candidates = np.stack([np.load(folder/f'candidate_{i}.npy').astype(np.float64) for i in range(5)])
    return ref,candidates


def fit_weights(gram, linear, constant, max_models=4):
    """Choose the subset using development error only; never inspect test audio."""
    if gram.shape != (len(linear),len(linear)) or not np.isfinite(gram).all() or not np.isfinite(linear).all():
        raise ValueError('Invalid development statistics')
    trials=[]
    for subset in itertools.combinations(range(len(linear)),max_models):
        ix=np.array(subset); g=gram[np.ix_(ix,ix)]; b=linear[ix]
        result=minimize(lambda w: float(w@g@w-2*b@w+constant),np.ones(max_models)/max_models,
            jac=lambda w:2*(g@w-b),method='SLSQP',bounds=[(0,1)]*max_models,
            constraints=[{'type':'eq','fun':lambda w: w.sum()-1,'jac':lambda w:np.ones(max_models)}],
            options={'ftol':1e-12,'maxiter':1000})
        if not result.success: raise RuntimeError(result.message)
        weights=np.zeros(len(linear)); weights[ix]=result.x
        trials.append({'indices':list(subset),'weights':weights.tolist(),'loss':float(result.fun)})
    return min(trials,key=lambda t:t['loss']),trials


def fit():
    # Nonnegative simplex, equal track weighting, normalized errors for BOTH stems.
    # No test track is read during fitting or subset choice.
    gram = np.zeros((5,5)); linear=np.zeros(5); constant=0.
    spectra=[]
    for track in tracks():
        if track['split']!='train': continue
        ref,candidates=load(track)
        x=candidates.reshape(5,-1); y=ref['vocal'].ravel()
        scale=(1/max(np.sum(ref['vocal']**2),1e-12)+1/max(np.sum(ref['instrumental']**2),1e-12))/16
        gram+=scale*(x@x.T); linear+=scale*(x@y); constant+=scale*(y@y)
        # Fixed sparse STFT grid keeps optimization practical. Final evaluation
        # uses the FULL grid, including bins omitted here. No test selection.
        def spectrum(wave):
            return stft(wave.T,fs=RATE,nperseg=2048,noverlap=1536)[2][:,::8,::8].ravel()
        spectra.append((np.stack([spectrum(c) for c in candidates]), spectrum(ref['source']),
                        np.abs(spectrum(ref['vocal'])),np.abs(spectrum(ref['instrumental']))))
    baseline=np.array([.5,0,.25,0,.25])
    original=np.array([0,.55,.15,.10,.20])
    wave_best,wave_trials=fit_weights(gram,linear,constant)
    def spectral_errors(weights):
        values=np.zeros(4)
        for candidates,source,vocal,instrumental in spectra:
            estimate=weights@candidates
            for i,(reference,output) in enumerate(((vocal,estimate),(instrumental,source-estimate))):
                difference=np.abs(output)-reference
                denominator=max(float(reference@reference),1e-12)
                values[2*i]+=float(np.sum(np.minimum(difference,0)**2))/denominator
                values[2*i+1]+=float(np.sum(np.maximum(difference,0)**2))/denominator
        return values/len(spectra)
    spectral_baseline=spectral_errors(baseline)
    def objective(weights):
        return float(weights@gram@weights-2*linear@weights+constant+.5*spectral_errors(weights).sum())
    trials=[]
    for trial in wave_trials:
        indices=trial['indices']; ix=np.array(indices)
        def full(w):
            result=np.zeros(5);result[ix]=w;return result
        result=minimize(lambda w:objective(full(w)),np.array(trial['weights'])[ix],
            method='SLSQP',bounds=[(0,1)]*4,
            constraints=[{'type':'eq','fun':lambda w:w.sum()-1},
                         {'type':'ineq','fun':lambda w:spectral_baseline+1e-8-spectral_errors(full(w))}],
            options={'ftol':1e-10,'maxiter':200})
        weights=full(result.x)
        constraints_met=bool(np.all(spectral_errors(weights)<=spectral_baseline+1e-7))
        trials.append({'indices':indices,'weights':weights.tolist(),'loss':objective(weights),
                       'success':bool(result.success and constraints_met),'message':str(result.message),
                       'development_spectral_errors':spectral_errors(weights).tolist()})
    eligible=[t for t in trials if t['success']]
    if not eligible:
        raise RuntimeError('No converged fit satisfies both-stem spectral safety constraints')
    best=min(eligible,key=lambda t:t['loss'])
    write_json(WORK/'frozen_fit.json',{'objective':'equal-track mean normalized waveform MSE for both stems + 0.5 summed normalized STFT magnitude errors',
        'constraints':'Nonnegative simplex, four models; mean development deficit/excess for BOTH stems <= V1 on fixed sparse STFT grid',
        'development_spectral_baseline':spectral_baseline.tolist(),'waveform_only_trials':wave_trials,
        'weights':best['weights'],'indices':best['indices'],'trials':trials,
        'v1_development_loss':objective(baseline),
        'original_v2_development_loss':objective(original),
        'selected_development_loss':best['loss'],
        'test_used_for_fitting':False})
    print(json.dumps(best),flush=True)


def metrics(reference, estimate):
    energy=max(float(np.sum(reference**2)),1e-12)
    error=max(float(np.sum((reference-estimate)**2)),1e-12)
    r=reference-reference.mean(axis=0); e=estimate-estimate.mean(axis=0)
    projection=float(np.sum(r*e))/max(float(np.sum(r*r)),1e-12)*r
    si=10*np.log10(max(float(np.sum(projection**2)),1e-12)/max(float(np.sum((e-projection)**2)),1e-12))
    # Linear STFT magnitude deficit/excess: proxies, NOT MVSEP Fullness/Bleedless.
    rm=np.abs(stft(reference.T,fs=RATE,nperseg=2048,noverlap=1536)[2])
    em=np.abs(stft(estimate.T,fs=RATE,nperseg=2048,noverlap=1536)[2])
    denom=max(float(np.sum(rm**2)),1e-12)
    return {'sdr_db':float(10*np.log10(energy/error)), 'si_sdr_db':float(si),
            'spectral_deficit':float(np.sum(np.maximum(rm-em,0)**2)/denom),
            'spectral_excess':float(np.sum(np.maximum(em-rm,0)**2)/denom)}


def evaluate():
    frozen=json.loads((WORK/'frozen_fit.json').read_text(encoding='utf8'))
    systems={'v1':np.array([.5,0,.25,0,.25]),'v2_initial':np.array([0,.55,.15,.1,.2]),
             'v2_fitted':np.array(frozen['weights'])}
    rows=[]
    for track in tracks():
        ref,candidates=load(track); row={**track,'systems':{}}
        for name,weights in systems.items():
            vocal=np.tensordot(weights,candidates,axes=(0,0))
            row['systems'][name]={stem:metrics(ref[stem],est) for stem,est in
                [('vocal',vocal),('instrumental',ref['source']-vocal)]}
        rows.append(row)
        print('SCORED',track['split'],track['name'],flush=True)
    summary={}
    for split in ('train','test'):
        selected=[r for r in rows if r['split']==split]
        summary[split]={name:{stem:{key:float(np.mean([r['systems'][name][stem][key] for r in selected]))
            for key in selected[0]['systems'][name][stem]} for stem in ('vocal','instrumental')} for name in systems}
    selected=[r for r in rows if r['split']=='test']
    deltas=np.array([r['systems']['v2_fitted']['vocal']['sdr_db']-r['systems']['v1']['vocal']['sdr_db'] for r in selected])
    rng=np.random.default_rng(20261010)
    bootstrap=np.mean(rng.choice(deltas,(10000,len(deltas)),replace=True),axis=1)
    report={'fit':frozen,'summary':summary,'rows':rows,'test_vocal_sdr_delta_db':float(deltas.mean()),
        'test_sdr_delta_bootstrap_95pct':np.quantile(bootstrap,[.025,.975]).tolist(),
        'test_tracks_improved':int(np.sum(deltas>0)), 'test_tracks_regressed':int(np.sum(deltas<0)),
        'limitations':['7-second AAC excerpts, not full songs','Model training data overlap is unknown; held-out only from weight fitting',
                      'SDR here is raw reference/error energy ratio, not filtered BSS Eval v4 or MVSEP leaderboard SDR',
                      'Small 8/8 pilot; no Turkish or arabesk guarantee','Magnitude deficit/excess are proxies, not true leakage or MVSEP metrics']}
    write_json(WORK/'results.json',report)
    print(json.dumps(summary,indent=2),flush=True)


def passes_pilot(report):
    """A limited pilot acceptance rule, never a universal separation guarantee."""
    if report['test_sdr_delta_bootstrap_95pct'][0]<=0:
        return False
    test=report['summary']['test']
    for stem in ('vocal','instrumental'):
        old=test['v1'][stem]; new=test['v2_fitted'][stem]
        if not all(np.isfinite(list(values.values())).all() for values in (old,new)):
            return False
        if new['sdr_db']<=old['sdr_db'] or new['si_sdr_db']<old['si_sdr_db']:
            return False
        if any(new[key]>old[key] for key in ('spectral_deficit','spectral_excess')):
            return False
    return True


def export():
    """Save measured evidence, not audio/model weights, in the repository."""
    import importlib.metadata
    import platform
    import core
    import torch
    report=json.loads((WORK/'results.json').read_text(encoding='utf8'))
    report['pilot_acceptance_passed']=passes_pilot(report)
    report['manifest']=json.loads((WORK/'manifest.json').read_text(encoding='utf8'))
    def digest(path):
        hasher=hashlib.sha256()
        with path.open('rb') as handle:
            for chunk in iter(lambda:handle.read(1024*1024),b''):hasher.update(chunk)
        return hasher.hexdigest()
    report['provenance']={'python':platform.python_version(),
        'gpu':torch.cuda.get_device_name(0),'torch':torch.__version__,
        'use_autocast':core.use_autocast,'core_sha256':digest(ROOT/'core.py'),
        'packages':{name:importlib.metadata.version(name) for name in ('audio-separator','numpy','scipy','soundfile')},
        'archive_sha256':digest(WORK/'MUSDB18-7-STEMS.zip'),'model_files':[]}
    configs=['model_bs_roformer_ep_317_sdr_12.9755.yaml','config_bs_roformer.yaml',
             'config_mel_band_roformer_kim_ft_unwa.yaml',
             'config_mel_band_roformer_vocals_becruily.yaml','config_melbandroformer_inst_v2.yaml']
    for model,config in zip(MODELS,configs):
        filename=core.roformer_models[model['model_key']]
        paths=list((ROOT/'models').rglob(filename))
        if len(paths)!=1: raise ValueError('Cannot uniquely identify benchmark checkpoint')
        path=paths[0]
        config_path=path.parent/config
        report['provenance']['model_files'].append({'model_key':model['model_key'],
            'file':path.relative_to(ROOT).as_posix(),'sha256':digest(path),'bytes':path.stat().st_size,
            'config':config_path.relative_to(ROOT).as_posix(),'config_sha256':digest(config_path)})
    report['provenance']['benchmark_script_sha256']=digest(Path(__file__))
    write_json(ROOT/'docs/atlas-studio-v2-benchmark.json',report)
    print('EXPORTED; pilot accepted:',report['pilot_acceptance_passed'],flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('phase',choices=['prepare','infer','fit','evaluate','export'])
    globals()[parser.parse_args().phase]()
