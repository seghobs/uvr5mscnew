"""Compare candidate pools on previously inspected DEVELOPMENT only."""
import itertools
import json
from pathlib import Path
import sys
import numpy as np
from scipy.optimize import minimize
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from tools import atlas_refinement as r


def screen():
    tracks=json.loads((ROOT/'cache/atlas_resurrection/manifest.json').read_text())['development'][:8]
    indices=[0,1,2,4,7,8];grams=[];linears=[];constants=[]
    for t in tracks:
        ref,estimates=r.load(t,indices);flat=estimates.reshape(len(indices),-1)
        norm=max(float(np.sum(ref['vocal']**2)),1e-12)
        grams.append(flat@flat.T/norm);linears.append(flat@ref['vocal'].ravel()/norm);constants.append(1.)
    g=np.mean(grams,axis=0);b=np.mean(linears,axis=0);rows=[]
    for subset in itertools.combinations(range(len(indices)),4):
        ix=list(subset);gg=g[np.ix_(ix,ix)];bb=b[ix]
        solved=minimize(lambda w:w@gg@w-2*bb@w+1,np.ones(4)/4,jac=lambda w:2*(gg@w-bb),
            bounds=[(0,1)]*4,constraints=[{'type':'eq','fun':lambda w:w.sum()-1}],method='SLSQP',options={'ftol':1e-12})
        rows.append({'indices':[indices[i] for i in ix],'weights':solved.x.tolist(),'normalized_error':float(solved.fun),'converged':bool(solved.success)})
    rows.sort(key=lambda v:v['normalized_error'])
    r.pilot.write_json(ROOT/'cache/atlas_new_experts/pool_screen.json',{'development_only':True,'development_ids':[t['id'] for t in tracks],'rows':rows})
    print(json.dumps(rows[:5],indent=2))


if __name__=='__main__':screen()
