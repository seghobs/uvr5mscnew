"""Freeze one challenger using full DEVELOPMENT metrics, before validation."""
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from tools.atlas_benchmark import write_json


def choose():
    candidates=[]
    for name in ['atlas_resurrection','atlas_resurrection_six','atlas_resurrection_six_warm']:
        folder=ROOT/'cache'/name
        if (folder/'evaluation.json').exists():raise RuntimeError('Validation was already opened')
        selection=folder/'development_selection.json'
        if not selection.exists():continue
        report=json.loads(selection.read_text(encoding='utf8'))
        frozen=json.loads((folder/'frozen_fit.json').read_text(encoding='utf8'))
        if not report['eligible']:continue
        assert not frozen['evaluation_used_for_fitting']
        score=frozen['development_selection']['summary']['vocal']['sdr_db']
        candidates.append({'work':name,'development_vocal_sdr_db':score,
            'models':len(json.loads((folder/'manifest.json').read_text())['models'])})
    if not candidates:raise RuntimeError('No challenger passes full development checks')
    best=max(candidates,key=lambda row:row['development_vocal_sdr_db'])
    write_json(ROOT/'cache/atlas_resurrection_selection.json',{'selected':best,'candidates':candidates,
        'selection_uses_evaluation':False})
    print(json.dumps(best))


if __name__=='__main__':choose()
