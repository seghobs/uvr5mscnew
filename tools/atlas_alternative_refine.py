"""Round two: opened confirmation becomes development; margins frozen in advance."""
import argparse
import json
from pathlib import Path
import sys
import hashlib
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from tools import atlas_alternative_screen as a,atlas_sdr_optimize as optimizer
from tools.atlas_benchmark import write_json
BASE=a.WORK;WORK=BASE/'round_two'

def fit(content_margin=(.99,.95,.90,.95),suffix=''):
    development=a.tracks()+a.read(BASE/'validation_manifest.json')['tracks']
    indices=[0,1,2,4,7,8,9,10,11];original=optimizer.read
    def modified(path):
        value=original(path)
        if path.name=='atlas-studio-v2-preset.json':value['frequency_weights']['weights']+=[[0.]*10 for _ in range(3)]
        if path.name=='manifest.json':value['development']=development;value['candidate_indices']=indices
        return value
    write_json(WORK/f'development_plan{suffix}.json',{'tracks':development,'content_margin':list(content_margin),
        'reason':'First confirmation rejected: instrument deficit and vocal excess regressions. That audio is now DEVELOPMENT, never independent evidence for this refit.'})
    optimizer.read=modified;optimizer.WORK=WORK/f'constrained_fit{suffix}'
    try:optimizer.main(content_margin=list(content_margin))
    finally:optimizer.read=original

def fit_soft():fit((.995,.99,.97,.99),'_soft')

def infer():
    path=WORK/'validation_manifest.json'
    if not path.exists():
        known={p.name for p in (a.e.WORK/'references').iterdir()};tracks=[]
        files=sorted((a.b.WORK/'dataset').glob('*/*.stem.mp4'),key=lambda p:hashlib.sha256(('atlas-conservative-round2:'+p.name).encode()).hexdigest())
        for p in files:
            identifier=hashlib.sha256(p.name.encode()).hexdigest()[:12]
            if identifier not in known:tracks.append({'id':identifier,'name':p.stem.removesuffix('.stem'),'file':str(p.resolve()),'split':'evaluation'})
            if len(tracks)==8:break
        if len(tracks)!=8:raise RuntimeError('Fresh recordings exhausted')
        write_json(path,{'tracks':tracks,'selection':'Eight previously uncached recordings in fixed SHA order. Inference may overlap development fitting; no quality scoring until final development selection is frozen.'})
    a.WORK=WORK;a.validate_infer()

def choose():
    if (WORK/'confirmation_plan.json').exists():raise RuntimeError('Selection already frozen')
    target=WORK/'constrained_fit/frozen.json'
    strict=a.read(target) if target.exists() else {'selected':None,'status':'Strict 10% instrumental margin attempt interrupted after over six minutes without completing the first optimization; not a measured infeasibility result.'}
    soft=a.read(WORK/'constrained_fit_soft/frozen.json')
    eligible=[(name,value) for name,value in [('strict',strict),('soft',soft)] if value['selected']]
    if not eligible:raise RuntimeError('No full-resolution eligible development fit')
    name,frozen=max(eligible,key=lambda pair:pair[1]['selected']['full_development']['vocal']['sdr_db'])
    # Preserve both original fits before creating the final frozen selection.
    write_json(WORK/'strict_fit.json',strict);write_json(WORK/'soft_fit.json',soft)
    frozen['selection']={'name':name,'basis':'Best eligible full-resolution DEVELOPMENT SDR only; no second confirmation metrics read'}
    write_json(target,frozen)
    write_json(WORK/'confirmation_plan.json',{'frozen_at':datetime.now(timezone.utc).isoformat(),'candidates':['candidate'],
        'selection':frozen['selection'],'acceptance':'Mean SDR gain >=0.2 dB; paired 97.5% interval lower >0; both SI-SDR and all four content means no worse.'})
    print('FROZEN SECOND ROUND',name,flush=True)

def validate():a.WORK=WORK;a.validate()

def report():
    result=a.read(WORK/'validation.json')
    write_json(ROOT/'docs/atlas-studio-v2-alternatives-round-two.json',{
        'round':2,'date':'2026-10-10','initial_confirmation_report':'docs/atlas-studio-v2-alternatives.json',
        'development_plan':a.read(WORK/'development_plan_soft.json'),
        'strict_attempt':a.read(WORK/'strict_fit.json'),'soft_attempt':a.read(WORK/'soft_fit.json'),
        'selected_fit':a.read(WORK/'constrained_fit/frozen.json'),
        'confirmation_manifest':a.read(WORK/'validation_manifest.json'),'confirmation':result,
        'deux_provenance':a.read(BASE/'provenance.json'),'xe_provenance':a.read(BASE/'xe_provenance.json'),
        'production_preset_sha256':hashlib.sha256((ROOT/'frontend/src/lib/atlas-studio-v2-preset.json').read_bytes()).hexdigest(),
        'experiment_tool_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()})
    print(json.dumps({'accepted':result['accepted'],'gain_db':result['mean_delta_db'],'interval':result['bootstrap_97_5pct']},indent=2))

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('phase',choices=['fit','fit_soft','infer','choose','validate','report']);globals()[parser.parse_args().phase]()
