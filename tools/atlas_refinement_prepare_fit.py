"""Precompute exact development statistics while independent GPU inference runs."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import time
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from tools import atlas_refinement as r


def prepare(work):
    r.WORK=work.resolve();m=r.manifest();indices=m.get('candidate_indices',r.INDICES)
    for t in m['development']:
        folder=r.extended.WORK/'references'/t['id']
        inputs=[folder/'reference.npz',*[folder/f'candidate_{i}.npy' for i in indices]]
        while not all(p.exists() for p in inputs):time.sleep(2)
        ref,candidates=r.load(t)
        for anchors in r.GRIDS:
            key=hashlib.sha256(json.dumps({'anchors':anchors,'FFT':r.FFT,'HOP':r.HOP,'RATE':r.RATE,
                'combiner':hashlib.sha256((ROOT/'atlas_band_ensemble.py').read_bytes()).hexdigest(),
                'indices':indices,'inputs':[(p.stat().st_size,p.stat().st_mtime_ns) for p in inputs]}).encode()).hexdigest()[:16]
            target=folder/f'exact_waveform_{key}.npz'
            if not target.exists():
                g,b,c=r.waveform_statistics(candidates,ref['vocal'],anchors)
                np.savez(target,gram=g,linear=b,constant=c)
        print('PREPARED',t['name'],flush=True)
    r.pilot.write_json(work/'invocation_provenance.json',{'fit_code_sha256':hashlib.sha256((ROOT/'tools/atlas_refinement.py').read_bytes()).hexdigest(),
        'core_sha256':hashlib.sha256((ROOT/'core.py').read_bytes()).hexdigest(),
        'new_model_metadata_adapter_sha256':hashlib.sha256((ROOT/'roformer_config.py').read_bytes()).hexdigest(),
        'development_count':len(m['development']),'validation_opened':False})
    r.fit()


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('work',type=Path);prepare(parser.parse_args().work)
