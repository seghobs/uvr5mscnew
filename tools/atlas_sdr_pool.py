"""Screen adding other cached experts against the deployed V2 on development only."""
import json
from pathlib import Path
import sys
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from tools import atlas_extended as e,atlas_refinement as r,atlas_benchmark as b
from tools.atlas_sdr_optimize import score,summary,eligible
from atlas_band_ensemble import combine_frequency


def main():
    preset=json.loads((ROOT/'frontend/src/lib/atlas-studio-v2-preset.json').read_text())
    manifest=json.loads((ROOT/'cache/atlas_confirmation/manifest.json').read_text())
    tracks=[t for t in manifest['development'] if all((e.WORK/'references'/t['id']/f'candidate_{i}.npy').exists() for i in range(9))]
    rows=[];choices=[(i,a) for i in (3,5,6) for a in (.025,.05,.1,.2)]
    for t in tracks:
        ref,candidates=r.load(t,manifest['candidate_indices'])
        current=combine_frequency(ref['source'],list(candidates),preset['frequency_weights'])[0]
        base_error=float(np.sum((current-ref['vocal'])**2));values=[]
        for i in (3,5,6):
            other=np.load(e.WORK/'references'/t['id']/f'candidate_{i}.npy')
            for alpha in (.025,.05,.1,.2):
                output=(1-alpha)*current+alpha*other
                delta=float(10*np.log10(base_error/max(float(np.sum((output-ref['vocal'])**2)),1e-12)))
                values.append({'index':i,'alpha':alpha,'sdr_delta_db':delta})
        rows.append({'id':t['id'],'name':t['name'],'baseline':score(ref,current),'choices':values})
        print('POOL',t['name'],flush=True)
    ranked=sorted([{'index':i,'alpha':a,'mean_sdr_delta_db':float(np.mean([next(v['sdr_delta_db'] for v in row['choices'] if v['index']==i and v['alpha']==a) for row in rows]))} for i,a in choices],key=lambda t:t['mean_sdr_delta_db'],reverse=True)
    base=summary([row['baseline'] for row in rows]);best=ranked[0]
    for choice in ranked:
        if choice['mean_sdr_delta_db']<=0:
            choice['eligible']=False;continue
        metrics=[]
        for t in tracks:
            ref,candidates=r.load(t,manifest['candidate_indices']);current=combine_frequency(ref['source'],list(candidates),preset['frequency_weights'])[0]
            other=np.load(e.WORK/'references'/t['id']/f"candidate_{choice['index']}.npy")
            metrics.append(score(ref,(1-choice['alpha'])*current+choice['alpha']*other))
        choice['summary']=summary(metrics);choice['eligible']=eligible(choice['summary'],base)
    b.write_json(ROOT/'cache/atlas_sdr_optimize/model_pool.json',{'development_only':True,'development_ids':[t['id'] for t in tracks],
        'baseline_summary':base,'models':e.MODELS,'ranked':ranked,'best':best,'rows':rows})
    print('BEST',json.dumps(best),flush=True)


if __name__=='__main__':main()
