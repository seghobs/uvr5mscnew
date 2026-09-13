"""Keep application caches and temporary files inside this installation."""
import os
from pathlib import Path
import tempfile


def configure_local_runtime(root=None):
    root = Path(root or Path(__file__).resolve().parent)
    cache = root/'cache'
    folders = {
        'HF_HOME': cache/'huggingface',
        'HF_HUB_CACHE': cache/'huggingface/hub',
        'HF_ASSETS_CACHE': cache/'huggingface/assets',
        'TORCH_HOME': cache/'torch',
        'XDG_CACHE_HOME': cache/'xdg',
        'NUMBA_CACHE_DIR': cache/'numba',
        'MPLCONFIGDIR': cache/'matplotlib',
        'PIP_CACHE_DIR': cache/'pip',
        'npm_config_cache': cache/'npm',
        'TEMP': cache/'tmp',
        'TMP': cache/'tmp',
        'TMPDIR': cache/'tmp',
    }
    for key, path in folders.items():
        path.mkdir(parents=True, exist_ok=True)
        os.environ[key] = str(path)
    tempfile.tempdir = str(cache/'tmp')
