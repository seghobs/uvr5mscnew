"""Verified publisher architectures for the calibrated Atlas experts.

All model construction is serialized: audio-separator chooses BSRoformer via a
module global. The override is restored before inference, including on errors.
"""
from contextlib import contextmanager
import hashlib
import importlib.util
import json
from pathlib import Path
import threading

REGISTRY = json.loads((Path(__file__).parent/'assets/atlas-publisher-models.json').read_text(encoding='utf8'))
LOAD_LOCK = threading.RLock()
_verified = {}


def verify(path, expected):
    path = Path(path)
    stat = path.stat()
    key = (str(path.resolve()), stat.st_size, stat.st_mtime_ns, expected)
    if key not in _verified:
        with path.open('rb') as handle:
            hasher = hashlib.sha256()
            for chunk in iter(lambda: handle.read(1024*1024), b''):
                hasher.update(chunk)
            digest = hasher.hexdigest()
        if digest != expected:
            raise ValueError(f'Publisher file checksum mismatch: {path.name}')
        _verified[key] = True


def normalize_config(config):
    # Retain custom architecture kwargs; stock compatibility filtering is wrong.
    config['inference']['batch_size'] = 1
    config['audio']['hop_length'] = config['model']['stft_hop_length']
    target = config['training']['target_instrument']
    ordered = [target]+[s for s in config['training']['instruments'] if s != target]
    config['training']['instruments'] = ['instrumental' if s == 'instrument' else s for s in ordered]
    config['training']['target_instrument'] = 'instrumental' if target == 'instrument' else target
    return config


def find_model(filename):
    return next(((name, spec) for name, spec in REGISTRY.items()
                 if filename in (name, spec['filename'])), None)


def download_custom(separator, filename):
    item = find_model(filename)
    if item is None:
        return None
    import yaml
    name, spec = item
    folder = Path(separator.model_file_dir)/('roformer_custom_'+hashlib.sha256(name.encode()).hexdigest()[:12])
    folder.mkdir(parents=True, exist_ok=True)
    files = [('checkpoint_url',spec['filename'],'checkpoint_sha256'),
             ('config_url','publisher.yaml','publisher_config_sha256'),
             ('source_url','publisher.py','source_sha256')]
    for url, local, checksum in files:
        separator.download_file_if_not_exists(spec[url],str(folder/local))
        verify(folder/local,spec[checksum])
    config = normalize_config(yaml.load((folder/'publisher.yaml').read_text(encoding='utf8'),Loader=yaml.FullLoader))
    path = folder/'config_bs_roformer.yaml'
    path.write_text(yaml.dump(config),encoding='utf8')
    return spec['filename'],'MDXC',name,str(folder/spec['filename']),str(path)


def publisher_class(folder, spec):
    source = Path(folder)/'publisher.py'
    verify(source,spec['source_sha256'])
    translated = Path(folder)/'publisher_architecture.py'
    translated.write_text(source.read_text(encoding='utf8').replace(
        'from models.bs_roformer.attend import Attend',
        'from audio_separator.separator.uvr_lib_v5.roformer.attend import Attend'),encoding='utf8')
    module_spec = importlib.util.spec_from_file_location('atlas_publisher_'+spec['source_sha256'][:16],translated)
    module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(module)
    return module.BSRoformer


@contextmanager
def architecture_scope(separator, filename):
    with LOAD_LOCK:
        item = find_model(filename)
        if item is None:
            yield
            return
        import audio_separator.separator.architectures.mdxc_separator as runner
        files = separator.download_model_files(filename)
        cls = publisher_class(Path(files[3]).parent,item[1])
        original = runner.BSRoformer
        runner.BSRoformer = cls
        try:
            yield
        finally:
            runner.BSRoformer = original
