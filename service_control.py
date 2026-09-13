"""Manage only the backend/frontend belonging to this checkout."""
import hashlib
from contextlib import contextmanager
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import urllib.request
from urllib.error import HTTPError
import psutil

ROOT=Path(__file__).resolve().parent

@contextmanager
def management_lock():
    folder=ROOT/'.runtime';folder.mkdir(exist_ok=True)
    with (folder/'service.lock').open('a+b') as handle:
        handle.seek(0);handle.write(b'0');handle.flush();handle.seek(0)
        deadline=time.monotonic()+100
        while True:
            try:
                if os.name=='nt':
                    import msvcrt
                    msvcrt.locking(handle.fileno(),msvcrt.LK_NBLCK,1)
                else:
                    import fcntl
                    fcntl.flock(handle,fcntl.LOCK_EX|fcntl.LOCK_NB)
                break
            except OSError:
                if time.monotonic()>deadline:raise RuntimeError('Başka bir servis işlemi sürüyor.')
                time.sleep(.2)
        try:yield
        finally:
            handle.seek(0)
            if os.name=='nt':msvcrt.locking(handle.fileno(),msvcrt.LK_UNLCK,1)
            else:fcntl.flock(handle,fcntl.LOCK_UN)

def revision():
    digest=hashlib.sha256()
    for path in sorted([*ROOT.glob('*.py'), *(ROOT/'lyric_sources').glob('*.py')]):
        digest.update(path.relative_to(ROOT).as_posix().encode());digest.update(path.read_bytes())
    return digest.hexdigest()

def service_info():
    try:
        with urllib.request.urlopen('http://127.0.0.1:8000/api/service',timeout=2) as response:return json.load(response)
    except Exception:return None

def owns_backend(process):
    try:
        command=process.cmdline()
        return Path(process.cwd()).resolve()==ROOT and any(Path(arg).name=='api_modern.py' for arg in command) and Path(process.exe()).resolve().is_relative_to(ROOT/'env')
    except (psutil.Error,OSError):return False

def owns_frontend(process):
    try:
        command=' '.join(process.cmdline()).lower().replace('\\','/')
        return Path(process.cwd()).resolve()==ROOT/'frontend' and ('/next/dist/' in command or 'node_modules/next/' in command) and Path(process.exe()).name.lower() in ('node.exe','node')
    except (psutil.Error,OSError):return False

def terminate_tree(process):
    # A management helper spawned by the backend must survive its parent's shutdown.
    children=[p for p in process.children(recursive=True) if p.pid!=os.getpid()]
    for child in reversed(children):
        try:child.terminate()
        except psutil.Error:pass
    try:process.terminate()
    except psutil.Error:pass
    _,alive=psutil.wait_procs(children+[process],timeout=3)
    for child in alive:
        try:child.kill()
        except psutil.Error:pass

class ServiceBusy(RuntimeError):
    pass


def prepare():
    info=service_info()
    if info and Path(info.get('root','')).resolve()==ROOT:
        request=urllib.request.Request('http://127.0.0.1:8000/api/service/prepare',data=b'{}',headers={'Content-Type':'application/json'},method='POST')
        try:
            with urllib.request.urlopen(request,timeout=5):pass
        except HTTPError as exc:
            if exc.code==409:raise ServiceBusy('Çalışan işlemler var. Önce tamamlayın veya iptal edin.') from exc
            raise RuntimeError('Sunucunun yeniden başlatılmaya hazır olduğu doğrulanamadı.') from exc
        except Exception as exc:raise RuntimeError('Sunucu durumuna ulaşılamadı; çalışan işlemler korunuyor.') from exc

def stop(frontend=False):
    prepare()
    for process in psutil.process_iter():
        if process.pid!=os.getpid() and (owns_backend(process) or (frontend and owns_frontend(process))):terminate_tree(process)

def start(reuse_busy=False):
    current=service_info()
    if current and Path(current.get('root','')).resolve()!=ROOT:raise RuntimeError('8000 portunda başka bir proje çalışıyor.')
    if current and current.get('revision')==revision():return
    existing=[p for p in psutil.process_iter() if owns_backend(p)]
    if existing:
        try:stop()
        except ServiceBusy:
            if not reuse_busy or not current:raise
            print('Çalışan işlem korunuyor; arayüz mevcut sunucuyla açılacak. Yeni değişiklikler için işlem bittikten sonra sunucuyu yeniden başlatın.')
            return
    for connection in psutil.net_connections(kind='tcp'):
        if connection.status=='LISTEN' and connection.laddr.port==8000:raise RuntimeError('8000 portu başka bir işlem tarafından kullanılıyor.')
    logs=ROOT/'logs';logs.mkdir(exist_ok=True)
    with (logs/'backend.log').open('ab') as output:
        subprocess.Popen([str(ROOT/'env'/'python.exe' if os.name=='nt' else ROOT/'env'/'bin'/'python'),str(ROOT/'api_modern.py')],cwd=ROOT,stdin=subprocess.DEVNULL,stdout=output,stderr=subprocess.STDOUT,
            creationflags=(subprocess.CREATE_NO_WINDOW|subprocess.DETACHED_PROCESS|subprocess.CREATE_NEW_PROCESS_GROUP) if os.name=='nt' else 0,start_new_session=os.name!='nt')
    for _ in range(90):
        current=service_info()
        if current and current.get('revision')==revision():return
        time.sleep(1)
    raise RuntimeError('Sunucu başlatılamadı. logs/backend.log dosyasını kontrol edin.')

if __name__=='__main__':
    try:
        action=sys.argv[1] if len(sys.argv)>1 else 'ensure'
        with management_lock():
            if action=='stop':stop(True)
            elif action=='restart':stop();start()
            elif action=='ensure':start()
            elif action=='launch':start(reuse_busy=True)
            else:raise ValueError('Unknown service action')
        print('UVR5: '+action+' tamamlandı.')
    except Exception as exc:print(str(exc),file=sys.stderr);sys.exit(1)
