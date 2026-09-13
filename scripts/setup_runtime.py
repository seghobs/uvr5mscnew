"""Install the tested Windows audio stack without starting the application."""
import argparse
import hashlib
import importlib
import importlib.metadata as metadata
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import urllib.parse
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from local_runtime import configure_local_runtime
os.environ['PYTHONNOUSERSITE'] = '1'
DLL_HANDLES = []


def configure_paths():
    directories = [ROOT/'tools/setup-runtime/ffmpeg/bin', ROOT/'env', ROOT/'env/Scripts', ROOT/'env/Library/bin']
    torch_lib = ROOT/'env/Lib/site-packages/torch/lib'
    directories.append(torch_lib)
    os.environ['PATH'] = os.pathsep.join(str(p) for p in directories if p.is_dir()) + os.pathsep + os.environ.get('PATH', '')
    if os.name == 'nt':
        for path in directories:
            if path.is_dir():
                DLL_HANDLES.append(os.add_dll_directory(str(path)))


def choose_torch_channel(smi_output):
    """CUDA 12.8 needs a recent driver; an unsupported driver uses CPU."""
    versions = re.findall(r'(?m)^\s*(\d+)\.\d+', smi_output)
    return 'cu128' if versions and min(map(int, versions)) >= 570 else 'cpu'


def command(args):
    subprocess.run([str(a) for a in args], check=True, cwd=ROOT)


def pip(*args):
    command([sys.executable, '-m', 'pip', '--isolated', '--cache-dir', ROOT/'cache/pip', 'install', '--retries', '3', '--timeout', '120', *args])


def install_dependencies(package, excluded, constraints):
    from packaging.requirements import Requirement
    wanted = []
    for value in metadata.requires(package) or []:
        requirement = Requirement(value)
        if requirement.name.lower().replace('_', '-') in excluded:
            continue
        if requirement.marker and not requirement.marker.evaluate():
            continue
        wanted.append(value)
    if wanted:
        pip('-c', constraints, *wanted)


def install():
    if sys.version_info[:2] != (3, 10):
        raise RuntimeError('Python 3.10 gerekli.')
    try:
        smi = subprocess.run(['nvidia-smi', '--query-gpu=driver_version', '--format=csv,noheader'], capture_output=True, text=True, timeout=15)
        channel = choose_torch_channel(smi.stdout) if smi.returncode == 0 else 'cpu'
    except (OSError, subprocess.TimeoutExpired):
        channel = 'cpu'
    print('Hizlandirma:', 'NVIDIA CUDA 12.8' if channel == 'cu128' else 'CPU (uygun NVIDIA surucusu bulunamadi)', flush=True)
    pip('--upgrade', 'pip', 'setuptools', 'wheel', 'packaging')
    # Install a matched stack before the remaining packages so pip cannot mix releases.
    pip(f'torch==2.7.0+{channel}', f'torchaudio==2.7.0+{channel}', f'torchvision==0.22.0+{channel}',
        '--index-url', f'https://download.pytorch.org/whl/{channel}')
    with tempfile.TemporaryDirectory(prefix='uvr_setup_') as directory:
        constraints = Path(directory)/'constraints.txt'
        constraints.write_text('torch==2.7.0\ntorchaudio==2.7.0\ntorchvision==0.22.0\nnumpy==2.2.6\nlibrosa==0.11.0\n', encoding='utf-8')
        lines = (ROOT/'requirements.txt').read_text().splitlines()
        # faster-whisper declares the CPU distribution even when GPU ONNX provides
        # the same import. Installing both ONNX wheels overwrites shared DLL files.
        lines = [line for line in lines if not line.startswith('faster-whisper')]
        if channel == 'cpu':
            lines = [line.replace('audio-separator[gpu]', 'audio-separator[cpu]') for line in lines]
        requirements = Path(directory)/'requirements.txt'
        requirements.write_text('\n'.join(lines)+'\n', encoding='utf-8')
        wrong_onnx = 'onnxruntime' if channel == 'cu128' else 'onnxruntime-gpu'
        try:
            metadata.version(wrong_onnx)
        except metadata.PackageNotFoundError:
            pass
        else:
            command([sys.executable, '-m', 'pip', '--isolated', 'uninstall', '-y', wrong_onnx])
        pip('-c', constraints, '-r', requirements)
        # Restore shared files if an old installation had both ONNX distributions.
        pip('--force-reinstall', '--no-deps', ('onnxruntime-gpu' if channel == 'cu128' else 'onnxruntime')+'==1.23.2')
        pip('--no-deps', 'faster-whisper==1.2.1', 'audiosr==0.0.7')
        install_dependencies('faster-whisper', {'onnxruntime'}, constraints)
        # AudioSR's old metadata pins conflict with audio-separator. The modern
        # versions below are the combination tested by this application.
        install_dependencies('audiosr', {'numpy', 'librosa', 'transformers'}, constraints)
        pip('-c', constraints, 'numpy==2.2.6', 'librosa==0.11.0', 'hf-transfer', 'pillow')


def download_file(url, destination, sha256=None):
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.is_file() and destination.stat().st_size > 0 and (not sha256 or file_hash(destination) == sha256):
        return
    temporary = destination.with_suffix(destination.suffix+'.part')
    print('Indiriliyor:', destination.name, flush=True)
    request = urllib.request.Request(url, headers={'User-Agent': 'UVR5-Setup'})
    with urllib.request.urlopen(request, timeout=120) as response, temporary.open('wb') as output:
        count = 0
        while True:
            block = response.read(1024*1024)
            if not block:
                break
            output.write(block)
            count += len(block)
        expected = response.headers.get('Content-Length')
        if not count or (expected and count != int(expected)):
            raise RuntimeError('Eksik model indirmesi: '+destination.name)
    if sha256 and file_hash(temporary) != sha256:
        raise RuntimeError('SHA256 dogrulamasi basarisiz: '+destination.name)
    temporary.replace(destination)


def file_hash(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as handle:
        for block in iter(lambda: handle.read(1024*1024), b''):
            digest.update(block)
    return digest.hexdigest()


def tools():
    archive = ROOT/'tools/setup-runtime/downloads/ffmpeg-9.0.1.zip'
    download_file('https://www.gyan.dev/ffmpeg/builds/packages/ffmpeg-9.0.1-essentials_build.zip', archive,
                  'fec81ae03971d9dd4be3ebe02e263bd2ec1d789483f931bdba5f5715e65da2e9')
    target = ROOT/'tools/setup-runtime/ffmpeg'
    with zipfile.ZipFile(archive) as contents:
        for entry in contents.infolist():
            relative = Path(*Path(entry.filename).parts[1:])
            destination = (target/relative).resolve()
            if not destination.is_relative_to(target.resolve()):
                raise RuntimeError('Gecersiz arsiv yolu')
            if entry.is_dir():
                destination.mkdir(parents=True, exist_ok=True)
            else:
                destination.parent.mkdir(parents=True, exist_ok=True)
                with contents.open(entry) as source, destination.open('wb') as output:
                    import shutil
                    shutil.copyfileobj(source, output)
    command([target/'bin/ffmpeg.exe', '-version'])
    command([target/'bin/ffprobe.exe', '-version'])


def models():
    from huggingface_hub import snapshot_download
    from karaoke_ctc import MODEL_ID, MODEL_REVISION, MODEL_DIR
    config = json.loads((ROOT/'assets/models.json').read_text(encoding='utf-8'))
    for url in config['BS-Roformer-Viperx-1297']:
        name = Path(urllib.parse.urlparse(url).path).name
        if not name:
            raise ValueError('Gecersiz model adresi')
        download_file(url, ROOT/'models'/name)
    for name, repository in [('large-v3', 'Systran/faster-whisper-large-v3'),
                             ('large-v3-turbo', 'deepdml/faster-whisper-large-v3-turbo-ct2')]:
        print('Whisper modeli:', name, flush=True)
        snapshot_download(repository, local_dir=str(ROOT/'models/whisper'/name))
    print('Turkce hizalama modeli hazirlaniyor...', flush=True)
    snapshot_download(MODEL_ID, revision=MODEL_REVISION, local_dir=str(MODEL_DIR),
                      allow_patterns=['config.json', 'preprocessor_config.json', 'vocab.json', 'pytorch_model.bin', 'README.md'])


def verify():
    import torch
    import torchaudio
    if torch.__version__.split('+')[0] != torchaudio.__version__.split('+')[0]:
        raise RuntimeError('Torch ve Torchaudio surumleri uyusmuyor.')
    # Exercise a tensor operation instead of relying only on package metadata.
    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    assert torch.ones(4, device=device).sum().item() == 4
    print('Torch:', torch.__version__, '/', device, flush=True)
    for name in ('fastapi', 'uvicorn', 'multipart', 'soundfile', 'numpy', 'librosa',
                 'audio_separator.separator', 'faster_whisper', 'stable_whisper',
                 'transformers', 'onnxruntime', 'psutil', 'PIL', 'audiosr'):
        importlib.import_module(name)
        print('OK:', name, flush=True)
    import numpy as np
    import soundfile as sf
    from audio_pitch import render_pitch_audio
    with tempfile.TemporaryDirectory(prefix='uvr_setup_verify_') as directory:
        source = Path(directory)/'source.wav'
        target = Path(directory)/'transpose.wav'
        sf.write(source, .1*np.sin(np.arange(16000)*2*np.pi*440/16000), 16000)
        render_pitch_audio(source, target, 2, 1)
        assert sf.info(target).frames == 16000
    print('OK: FFmpeg + Rubber Band, transpoze suresi korundu.', flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['install', 'models', 'tools', 'verify'])
    args = parser.parse_args()
    os.chdir(ROOT)
    configure_local_runtime(ROOT)
    configure_paths()
    {'install': install, 'models': models, 'tools': tools, 'verify': verify}[args.action]()


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print('KURULUM HATASI:', error, file=sys.stderr, flush=True)
        sys.exit(1)
