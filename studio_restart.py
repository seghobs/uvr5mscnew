"""Build beside the running frontend, then restart this checkout's services."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import threading
import time
import uuid

ROOT = Path(__file__).resolve().parent
REQUEST_LOCK = threading.Lock()


def status():
    try:
        return json.loads((ROOT/'.runtime/studio-restart.json').read_text(encoding='utf8'))
    except (OSError, ValueError):
        return {'phase': 'idle'}


def update(identifier, phase, message):
    folder = ROOT/'.runtime'
    folder.mkdir(exist_ok=True)
    temporary = folder/('studio-restart-'+uuid.uuid4().hex+'.tmp')
    temporary.write_text(json.dumps({'id': identifier, 'phase': phase, 'message': message,
                                     'automatic':(folder/('auto-restart-'+identifier)).exists(),
                                     'updated_at': time.time()}, ensure_ascii=False), encoding='utf8')
    os.replace(temporary, folder/'studio-restart.json')


def detached(command, output, env=None):
    return subprocess.Popen(command, cwd=ROOT/'frontend', env=env,
        stdin=subprocess.DEVNULL, stdout=output, stderr=subprocess.STDOUT,
        creationflags=(subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS |
                       subprocess.CREATE_NEW_PROCESS_GROUP) if os.name == 'nt' else 0,
        start_new_session=os.name != 'nt')


def request(automatic=False):
    from studio_build import build_lock
    with REQUEST_LOCK, build_lock(ROOT,'restart-request.lock'):
        current = status()
        if current['phase'] not in ('idle', 'completed', 'failed'):
            if time.time()-current.get('updated_at', 0) < 1800:
                return current
        identifier = uuid.uuid4().hex
        update(identifier, 'queued', 'Yeniden başlatma hazırlanıyor…')
        if automatic:
            marker=ROOT/'.runtime'/('auto-restart-'+identifier)
            marker.touch()
        try:
            logs = ROOT/'logs'
            logs.mkdir(exist_ok=True)
            with (logs/'studio-restart.log').open('ab') as output:
                detached([sys.executable, str(Path(__file__).resolve()), identifier], output)
        except Exception as error:
            update(identifier, 'failed', str(error))
            raise
        return status()


def wait_idle(identifier):
    import service_control as service
    deadline = time.monotonic()+86400
    while True:
        try:
            service.prepare()
            return
        except service.ServiceBusy:
            if time.monotonic() > deadline:
                raise RuntimeError('Çalışan işlemler tamamlanmadı; yeniden başlatma uygulanmadı.')
            update(identifier, 'waiting', 'Çalışan işlemlerin tamamlanması bekleniyor…')
            time.sleep(2)


def build(identifier):
    from studio_build import build_lock
    import ast
    with build_lock(ROOT):
        for path in ROOT.glob('*.py'):ast.parse(path.read_bytes(),filename=str(path))
        return _build(identifier)


def _build(identifier):
    dist = '.next-restart-'+identifier
    environment = dict(os.environ, UVR_NEXT_DIST=dist)
    npm = shutil.which('npm.cmd' if os.name == 'nt' else 'npm')
    if not npm:
        raise RuntimeError('npm bulunamadı; mevcut servisler korundu.')
    update(identifier, 'building', 'npm run build çalışıyor; mevcut uygulama açık…')
    command = [os.environ.get('COMSPEC', 'cmd.exe'), '/d', '/c', npm, 'run', 'build'] if os.name == 'nt' else [npm, 'run', 'build']
    # Next generates type paths for distDir. Keep those transient paths out of source files.
    generated = {path:path.read_bytes() for path in (ROOT/'frontend/tsconfig.json', ROOT/'frontend/next-env.d.ts') if path.exists()}
    try:
        (ROOT/'logs').mkdir(exist_ok=True)
        with (ROOT/'logs/studio-restart.log').open('ab') as output:
            result = subprocess.run(command, cwd=ROOT/'frontend', env=environment,
                stdout=output, stderr=subprocess.STDOUT, timeout=1800,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
    finally:
        for path, content in generated.items():
            if path.name=='tsconfig.json':
                # Preserve edits made by the user while Next adds generated includes.
                current=json.loads(path.read_text(encoding='utf8'))
                current['include']=[p for p in current.get('include',[]) if not p.startswith(dist+'/')]
                original=json.loads(content)
                if current==original:path.write_bytes(content)
                else:path.write_text(json.dumps(current,indent=2)+'\n',encoding='utf8')
            else:path.write_bytes(content)
    if result.returncode:
        raise RuntimeError('Derleme başarısız; mevcut servisler korundu. logs/studio-restart.log dosyasını kontrol edin.')
    if not (ROOT/'frontend'/dist/'BUILD_ID').is_file():
        raise RuntimeError('Yeni derleme doğrulanamadı; mevcut servisler korundu.')
    return environment


def frontend_environment():
    import service_control as service
    for process in service.psutil.process_iter():
        if service.owns_frontend(process):
            try:
                return dict(os.environ, UVR_NEXT_DIST=process.environ().get('UVR_NEXT_DIST', '.next'))
            except service.psutil.Error:
                pass
    return dict(os.environ, UVR_NEXT_DIST='.next')


def start_frontend(environment):
    import urllib.request
    node = shutil.which('node')
    if not node:
        raise RuntimeError('Node.js bulunamadı.')
    with (ROOT/'logs/frontend.log').open('ab') as output:
        worker = detached([node, str(ROOT/'frontend/node_modules/next/dist/bin/next'), 'start', '-p', '3000'], output, environment)
    for _ in range(90):
        if worker.poll() is not None:
            raise RuntimeError('Frontend başlatılamadı; logs/frontend.log dosyasını kontrol edin.')
        try:
            with urllib.request.urlopen('http://127.0.0.1:3000/', timeout=2) as response:
                if response.status == 200:
                    return worker
        except Exception:
            pass
        time.sleep(1)
    worker.terminate()
    raise RuntimeError('Frontend zamanında yanıt vermedi.')


def run(identifier):
    import service_control as service
    from studio_build import fingerprint,record
    try:
        wait_idle(identifier)
        digest=fingerprint(ROOT)
        environment = build(identifier)
        wait_idle(identifier)
        if fingerprint(ROOT)!=digest:
            raise RuntimeError('Derleme sırasında kod değişti; mevcut sürüm korundu. Son düzenleme yeniden derlenecek.')
        with service.management_lock():
            old_environment = frontend_environment()
            update(identifier, 'restarting', 'Backend ve frontend yeniden başlatılıyor…')
            service.stop()
            service.start()
            for process in service.psutil.process_iter():
                if service.owns_frontend(process):
                    service.terminate_tree(process)
            try:
                start_frontend(environment)
            except Exception:
                start_frontend(old_environment)
                raise
            record(environment,digest,ROOT)
            update(identifier, 'completed', 'Uygulama hazır; çalışma alanı geri yükleniyor…')
            from studio_build import start_watcher
            start_watcher()
    except Exception as error:
        update(identifier, 'failed', str(error))


if __name__ == '__main__':
    run(sys.argv[1])
