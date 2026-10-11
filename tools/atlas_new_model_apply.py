"""Apply only the frozen recipe that passed independent preservation guards."""
import copy
import hashlib
import json
from pathlib import Path
import shutil
import numpy as np
from roformer_publisher import REGISTRY, verify
from tools.atlas_content_refine import passes_robust_confirmation

ROOT=Path(__file__).resolve().parents[1]
REPORT='docs/atlas-studio-v2-new-models-round-two.json'


def apply():
    path=ROOT/'frontend/src/lib/atlas-studio-v2-preset.json'
    report=json.loads((ROOT/REPORT).read_text(encoding='utf8'))
    result=report['confirmation']
    if not result['accepted'] or not passes_robust_confirmation(result) or not result['leakage_safe']:
        raise RuntimeError('Independent preservation checks did not pass')
    if hashlib.sha256(path.read_bytes()).hexdigest()!=report['baseline_sha256']:
        raise RuntimeError('Production changed since the frozen experiment')
    development=set(report['selected_fit']['development_ids'])
    if development & {t['id'] for t in report['confirmation_manifest']['tracks']}:
        raise RuntimeError('Development/confirmation overlap')
    baseline=json.loads(path.read_text(encoding='utf8'))
    preset=copy.deepcopy(baseline)
    models=preset['models']
    for name,spec in REGISTRY.items():
        models.append({'model_type':'roformer','model_key':name,
            'estimate':'inst' if 'Instrumental' in name or 'Large Inst' in name else 'vocal'})
    weights=np.asarray(result['frozen_spec']['weights'])
    if weights.shape!=(len(models),len(result['frozen_spec']['anchors_hz'])):
        raise RuntimeError('Frozen expert order/shape mismatch')
    for model,weight in zip(models,weights.mean(axis=1)):
        model['weight']=float(weight)
    preset['frequency_weights']=copy.deepcopy(result['frozen_spec'])
    preset['calibration']={'report':REPORT,'accepted':True,
        'scope':'Frozen independent 16-excerpt confirmation: mean SDR +0.231 dB; both mean deficits/excess and projection crosstalk lower. No zero-loss or universal superiority guarantee.'}
    assets=json.loads((ROOT/'assets/models.json').read_text(encoding='utf8'))
    for index,(name,spec) in zip(range(12,16),REGISTRY.items()):
        assets[name]=[spec['checkpoint_url'],spec['config_url']]
        # Reuse verified experimental downloads on this machine; other installs
        # use the same pinned URLs and checksums via the production downloader.
        folder=ROOT/'models'/('roformer_custom_'+hashlib.sha256(name.encode()).hexdigest()[:12])
        folder.mkdir(parents=True,exist_ok=True)
        for local,checksum in [(spec['filename'],'checkpoint_sha256'),('publisher.py','source_sha256'),('publisher.yaml','publisher_config_sha256')]:
            cached=ROOT/f'cache/atlas_new_models/{index}'/local
            if cached.exists():
                verify(cached,spec[checksum])
                target=folder/local
                if not target.exists():shutil.copyfile(cached,target)
                verify(target,spec[checksum])
    report['acceptance_kind']='new_model_content_preservation'
    report['baseline_deployed_preset']=baseline
    report['recipe']=preset
    report['production_applied']=True
    report['completed_expert_outputs']=392
    report['completed_constrained_fits']=5
    report['publisher_models']=REGISTRY
    report['production_live_verified']=False
    for target,data in [(ROOT/REPORT,report),(ROOT/'assets/models.json',assets),(path,preset)]:
        temporary=target.with_suffix(target.suffix+'.tmp')
        temporary.write_text(json.dumps(data,indent=2,ensure_ascii=False)+'\n',encoding='utf8')
        temporary.replace(target)
    print('Applied frozen 13-expert Atlas Studio V2')


if __name__=='__main__':apply()
