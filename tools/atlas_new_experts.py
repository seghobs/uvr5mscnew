"""Screen genuine new checkpoints on DEVELOPMENT audio before new holdouts."""
import argparse
import json
from pathlib import Path
import sys
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from tools import atlas_refinement as refinement
from tools import atlas_extended as extended
from tools import atlas_benchmark as pilot

MODELS=[
    {'model_type':'roformer','model_key':'BS-Roformer-Resurrection Vocals by pcunwa','estimate':'vocal'},
    {'model_type':'roformer','model_key':'BS-Roformer-Resurrection Instrumental by pcunwa','estimate':'inst'}]
WORK=ROOT/'cache/atlas_new_experts'


def screen():
    tracks=json.loads((ROOT/'cache/atlas_refinement_conservative/manifest.json').read_text(encoding='utf8'))['development'][:8]
    rows=[]
    for number,model in enumerate(MODELS):
        for t in tracks:
            folder=extended.prepare_reference(t)
            print('NEW DEVELOPMENT EXPERT',number,t['name'],flush=True)
            extended.infer_one(folder,7+number,model)
            with np.load(folder/'reference.npz') as ref:
                source=ref['source'];vocal=ref['vocal'];inst=ref['instrumental']
            candidate=np.load(folder/f'candidate_{7+number}.npy').astype(np.float64)
            old=np.stack([np.load(folder/f'candidate_{i}.npy').astype(np.float64) for i in refinement.INDICES])
            current=np.tensordot(refinement.CURRENT,old,axes=(0,0))
            rows.append({'name':t['name'],'expert':number,'systems':{name:{stem:pilot.metrics(target,wave)
                for stem,target,wave in [('vocal',vocal,v),('instrumental',inst,source-v)]}
                for name,v in [('current',current),('new_expert',candidate)]}})
            print('SCREEN DELTA',rows[-1]['systems']['new_expert']['vocal']['sdr_db']-rows[-1]['systems']['current']['vocal']['sdr_db'],flush=True)
    pilot.write_json(WORK/'screening.json',{'models':MODELS,'development_only':True,'rows':rows})


def full_infer():
    for track in extended.full_tracks():
        folder=extended.WORK/'turkish'/track['id']
        if not (folder/'reference.npz').exists():raise RuntimeError('Full-song reference preparation is missing')
        for number,model in enumerate(MODELS):
            print('NEW FULL EXPERT',number,track['name'],flush=True)
            extended.infer_one(folder,7+number,model)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('phase',nargs='?',default='screen',choices=['screen','full-infer'])
    globals()[parser.parse_args().phase.replace('-','_')]()
