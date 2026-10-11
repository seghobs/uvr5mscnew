"""Apply only the frozen, independently confirmed second-round recipe."""
import hashlib
from pathlib import Path
import shutil
import sys
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from tools.atlas_sdr_optimize import read,eligible
from tools.atlas_benchmark import write_json

def main():
    report_path=ROOT/'docs/atlas-studio-v2-alternatives-round-two.json';report=read(report_path)
    result=report['confirmation'];frozen=report['selected_fit']
    if not (result['accepted'] and result['mean_delta_db']>=.2 and result['bootstrap_97_5pct'][0]>0
            and eligible(result['summary']['candidate'],result['summary']['current'])):
        raise RuntimeError('Independent quality gate failed')
    target=ROOT/'frontend/src/lib/atlas-studio-v2-preset.json'
    if hashlib.sha256(target.read_bytes()).hexdigest()!=frozen['preset_sha256']:
        raise RuntimeError('Baseline changed; do not overwrite unknown work')
    recipe=read(target);recipe['models'] += [
        {'model_type':'roformer','model_key':'MelBand Roformer Deux by becruily','estimate':'vocal'},
        {'model_type':'roformer','model_key':'BS Roformer Leap Xe Vocals by pcunwa','estimate':'vocal'},
        {'model_type':'roformer','model_key':'BS Roformer Leap Xe Instrumental by pcunwa','estimate':'inst'}]
    recipe['frequency_weights']['weights']=frozen['selected']['weights']
    for model,weight in zip(recipe['models'],np.mean(recipe['frequency_weights']['weights'],axis=1)):
        model['weight']=float(weight)
    recipe['calibration']={'report':str(report_path.relative_to(ROOT)).replace('\\','/'),'accepted':True,
        'scope':'Second frozen confirmation: eight short reference excerpts; all eight SDR gains positive; both mean content checks improved. No zero-loss or universal superiority guarantee.'}
    import core
    catalog_path=ROOT/'assets/models.json';catalog=read(catalog_path)
    for model in recipe['models'][-3:]:
        name=model['model_key'];info=core._new_models[name];catalog[name]=info['download_files']
        directory=ROOT/'models'/('roformer_custom_'+hashlib.sha256(name.encode()).hexdigest()[:12]);directory.mkdir(exist_ok=True)
        if 'Deux' in name:source=ROOT/'cache/atlas_alternatives/model'
        else:source=ROOT/'cache/atlas_alternatives'/('xe_inst' if model['estimate']=='inst' else 'xe_voc')
        weight_source=source/info['filename']
        published=report['deux_provenance'] if 'Deux' in name else next(p for p in report['xe_provenance'] if p['index']==(11 if model['estimate']=='inst' else 10))
        expected=published.get('checkpoint_sha256',published.get('sha256'))
        if hashlib.sha256(weight_source.read_bytes()).hexdigest()!=expected:raise RuntimeError('Expert integrity failed')
        shutil.copy2(weight_source,directory/info['filename'])
        # Cache the exact publisher YAML; the production loader performs the same compatibility translation.
        import requests
        url=info['download_files'][1];response=requests.get(url,timeout=30);response.raise_for_status()
        (directory/url.rsplit('/',1)[1]).write_bytes(response.content)
    from atlas_studio import validate_models
    validate_models(recipe['models'],recipe)
    report['recipe']=recipe;report['production_applied']=True
    write_json(catalog_path,catalog);write_json(target,recipe)
    report['deployed_preset_sha256']=hashlib.sha256(target.read_bytes()).hexdigest()
    write_json(report_path,report)
    print('Applied independently confirmed Atlas V2: nine pinned experts',flush=True)

if __name__=='__main__':main()
