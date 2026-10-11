"""Independent validation: choose unseen cached-dataset recordings, then score once."""
import hashlib
import json
from pathlib import Path
import sys
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from tools import atlas_extended as e,atlas_benchmark as b,atlas_refinement as r
from tools.atlas_sdr_optimize import WORK,read,score,summary,eligible
from atlas_band_ensemble import combine_frequency


def manifest():
    path=WORK/'validation_manifest.json'
    if path.exists():return read(path)
    existing={p.name for p in (e.WORK/'references').iterdir()}
    files=list((b.WORK/'dataset').glob('*/*.stem.mp4'))
    files.sort(key=lambda p:hashlib.sha256(('atlas-sdr-20261010:'+p.name).encode()).hexdigest())
    tracks=[]
    for p in files:
        identifier=hashlib.sha256(p.name.encode()).hexdigest()[:12]
        if identifier not in existing:
            tracks.append({'id':identifier,'name':p.stem.removesuffix('.stem'),'file':str(p.resolve()),'split':'evaluation'})
        if len(tracks)==8:break
    if len(tracks)!=8:raise RuntimeError('Eight unseen reference recordings are required')
    original=read(ROOT/'cache/atlas_confirmation/manifest.json')
    data={'tracks':tracks,'candidate_indices':original['candidate_indices'],'models':original['models'],
          'selection':'First eight previously uncached dataset recordings in fixed SHA256 order; no metrics inspected. Dataset train/test labels are unrelated to this frozen optimization split; model training overlap is unknown.'}
    b.write_json(path,data);return data


def infer():
    data=manifest()
    for track in data['tracks']:
        folder=e.prepare_reference(track)
        for index,model in zip(data['candidate_indices'],data['models']):
            print('VALIDATION INFERENCE',track['name'],index,flush=True)
            e.infer_one(folder,index,model)


def passes_validation(summaries,interval):
    return eligible(summaries['candidate'],summaries['current']) and interval[0]>0


def evaluate():
    target=WORK/'validation.json'
    if target.exists():raise RuntimeError('Validation already opened; never tune against these results')
    frozen=read(WORK/'frozen.json');chosen=frozen['selected']
    if not chosen:raise RuntimeError('No development candidate selected')
    spec={'anchors_hz':frozen['baseline_preset']['frequency_weights']['anchors_hz'],'weights':chosen['weights']}
    rows=[];data=manifest()
    for track in data['tracks']:
        ref,estimates=r.load(track,data['candidate_indices'])
        waves={'current':combine_frequency(ref['source'],list(estimates),frozen['baseline_preset']['frequency_weights'])[0],
               'candidate':combine_frequency(ref['source'],list(estimates),spec)[0]}
        rows.append({'id':track['id'],'name':track['name'],'systems':{k:score(ref,v) for k,v in waves.items()}})
    summaries={k:summary([row['systems'][k] for row in rows]) for k in waves}
    delta=np.array([row['systems']['candidate']['vocal']['sdr_db']-row['systems']['current']['vocal']['sdr_db'] for row in rows])
    rng=np.random.default_rng(20261010)
    interval=np.quantile(rng.choice(delta,(10000,len(delta)),replace=True).mean(axis=1),[.025,.975]).tolist()
    accepted=passes_validation(summaries,interval)
    result={'summary':summaries,'rows':rows,'mean_delta_db':float(delta.mean()),'bootstrap_95pct':interval,
            'improved_recordings':int((delta>0).sum()),'accepted':accepted,'frozen_spec':spec,
            'limitations':['Short reference excerpts, unknown model-training overlap','No true Turkish studio stems; no claim of zero loss or universal superiority']}
    b.write_json(target,result);print(json.dumps({k:v for k,v in result.items() if k not in ('rows','frozen_spec')},indent=2),flush=True)


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('phase',choices=['infer','evaluate'])
    globals()[parser.parse_args().phase]()
