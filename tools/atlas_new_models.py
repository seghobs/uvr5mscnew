"""Pinned publisher architectures, isolated from production, for Atlas research."""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import requests
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools import atlas_alternative_screen as a, atlas_extended as e
from tools.atlas_benchmark import write_json

WORK = ROOT / 'cache/atlas_new_models'
EXPERTS = [
    (12, 'BS-Roformer-HyperACE', '5b1f8283125d5e4a3614d0e3635a636e09c84059', 'v2_voc/bs_roformer_voc_hyperacev2.ckpt', 'v2_voc/config.yaml', 'v2_voc/bs_roformer.py', 'vocal', '54cf516f621f2f460bf660ed137e244b8931bf7a2ce85ddceecff816dbc4d668'),
    (13, 'BS-Roformer-HyperACE', '5b1f8283125d5e4a3614d0e3635a636e09c84059', 'v2_inst/bs_roformer_inst_hyperacev2.ckpt', 'v2_inst/config.yaml', 'v2_inst/bs_roformer.py', 'inst', '4d61178ef966d2b4e9ad456ffbbc6fd5b2828df07a7af32931142c1a5ff1fe6f'),
    (14, 'BS-Roformer-Large-Inst', '94ea5d723ef7aceeeb211472a7bb42ad6ce4ee0d', 'bs_large_v2_inst.ckpt', 'config.yaml', 'bs_roformer.py', 'inst', '09251ab8b5bb892414a6ab8aa80a1be30c17852d5e7f4e76943610de049e4bc4'),
    (15, 'BS-EXP-SiameseRoformer', '2042531f6f98ff5070124fec89dffbdd185877f9', 'bs_exp_siameseroformer.ckpt', 'config.yaml', 'bs_roformer.py', 'vocal', 'cf5456f703931bdc5415c167453b4d88630c3adb1f2d4de462423faa52b30b79'),
]

def download(repo, revision, remote, target):
    if not target.exists():
        print('DOWNLOAD', repo, remote, flush=True)
        with requests.get(f'https://huggingface.co/pcunwa/{repo}/resolve/{revision}/{remote}', stream=True, timeout=(30,120)) as response:
            response.raise_for_status()
            with target.with_suffix('.tmp').open('wb') as output:
                for chunk in response.iter_content(1024*1024):
                    output.write(chunk)
        target.with_suffix('.tmp').replace(target)
    return target

def assert_idle_backend():
    # A second local service can bind 127.0.0.1 while UVR listens on 0.0.0.0.
    session=requests.Session();session.trust_env=False
    for host in ('127.0.0.1','127.0.0.2'):
        try:response=session.get(f'http://{host}:8000/api/audio/jobs',timeout=10)
        except requests.ConnectionError:continue
        if response.status_code==404:continue
        response.raise_for_status();jobs=response.json()['jobs']
        if any(j.get('status') in ('running','queued','processing') for j in jobs):
            raise RuntimeError('User audio jobs are active')
        return

def infer(selected=None, record_development=True):
    import core
    import audio_separator.separator.architectures.mdxc_separator as runner
    assert_idle_backend()
    tracks = selected or a.tracks()
    WORK.mkdir(parents=True,exist_ok=True)
    if record_development:write_json(WORK/'plan.json', {'development':tracks, 'experts':EXPERTS,
        'baseline_sha256':hashlib.sha256((ROOT/'frontend/src/lib/atlas-studio-v2-preset.json').read_bytes()).hexdigest(),
        'acceptance':'Freeze on development, then fresh paired 97.5% SDR interval positive, both SI-SDR no worse, both deficits >=1% lower and both excess proxies no higher.',
        'production_changed':False})
    for index,repo,revision,checkpoint_name,config_name,source_name,stem,expected in EXPERTS:
        folder=WORK/str(index);folder.mkdir(exist_ok=True)
        checkpoint=download(repo,revision,checkpoint_name,folder/Path(checkpoint_name).name)
        digest=hashlib.sha256(checkpoint.read_bytes()).hexdigest()
        if digest!=expected:
            raise RuntimeError('Checkpoint hash mismatch')
        source=download(repo,revision,source_name,folder/'publisher.py')
        published=download(repo,revision,config_name,folder/'publisher.yaml')
        # Only import-path translation: retain every architecture parameter.
        translated=folder/'architecture.py'
        translated.write_text(source.read_text(encoding='utf8').replace('from models.bs_roformer.attend import Attend',
            'from audio_separator.separator.uvr_lib_v5.roformer.attend import Attend'),encoding='utf8')
        module_spec=importlib.util.spec_from_file_location(f'atlas_research_{index}',translated)
        module=importlib.util.module_from_spec(module_spec);module_spec.loader.exec_module(module)
        config=yaml.load(published.read_text(encoding='utf8'),Loader=yaml.FullLoader)
        config['inference']['batch_size']=1
        config['audio']['hop_length']=config['model']['stft_hop_length']
        target=config['training']['target_instrument']
        config['training']['instruments']=[target]+[s for s in config['training']['instruments'] if s!=target]
        config['training']['instruments']=['instrumental' if s=='instrument' else s for s in config['training']['instruments']]
        config['training']['target_instrument']='instrumental' if target=='instrument' else target
        path=folder/'config_bs_roformer.yaml';path.write_text(yaml.dump(config),encoding='utf8')
        write_json(folder/'provenance.json',{'repo':repo,'revision':revision,'checkpoint_sha256':digest,
            'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'publisher_config_sha256':hashlib.sha256(published.read_bytes()).hexdigest(),
            'translation':'Only Attend import location, batch 1, hop metadata and output label order. Strict state_dict loading.'})
        old_download=core.Separator.download_model_files;old_class=runner.BSRoformer
        name=f'Experimental pinned {repo} {index}'
        def model_files(self,filename,*args,**kwargs):
            if filename==checkpoint.name:
                return filename,'MDXC',name,str(checkpoint),str(path)
            return old_download(self,filename,*args,**kwargs)
        core.Separator.download_model_files=model_files;runner.BSRoformer=module.BSRoformer
        core.roformer_models[name]=checkpoint.name
        try:
            for track in tracks:
                print('NEW EXPERT',index,track['name'],flush=True)
                assert_idle_backend()
                e.infer_one(e.prepare_reference(track),index,{'model_key':name,'estimate':stem})
        finally:
            core.Separator.download_model_files=old_download;runner.BSRoformer=old_class
            core.roformer_models.pop(name,None)

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--expanded',action='store_true')
    args=parser.parse_args()
    selected=a.tracks()
    if args.expanded:
        selected+=a.read(a.WORK/'validation_manifest.json')['tracks']
    infer(selected)
