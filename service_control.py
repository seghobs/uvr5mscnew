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
    model_registry=ROOT/'assets/models.json'
    configurations=[*(ROOT/'frontend/src/lib').glob('*preset.json')]
    if model_registry.exists():configurations.append(model_registry)
    for path in sorted([*ROOT.glob('*.py'), *(ROOT/'lyric_sources').glob('*.py'), *configurations]):
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

def frontend_running():
    """Reuse this checkout's listener; never stop an unrelated port owner."""
    listeners=[c for c in psutil.net_connections(kind='tcp') if c.status=='LISTEN' and c.laddr.port==3000]
    if not listeners:return False
    for connection in listeners:
        try:owned=connection.pid is not None and owns_frontend(psutil.Process(connection.pid))
        except psutil.Error:owned=False
        if not owned:raise RuntimeError('3000 portunda başka bir uygulama çalışıyor. UVR5 ikinci bir sunucu açmadı.')
    return True

def focus_frontend_console():
    if os.name!='nt' or not frontend_running():return
    import ctypes
    kernel=ctypes.windll.kernel32;user=ctypes.windll.user32
    kernel.GetConsoleWindow.restype=ctypes.c_void_p
    for connection in psutil.net_connections(kind='tcp'):
        if connection.status=='LISTEN' and connection.laddr.port==3000 and connection.pid:
            kernel.FreeConsole()
            if kernel.AttachConsole(connection.pid):
                window=kernel.GetConsoleWindow()
                if window and user.IsWindowVisible(ctypes.c_void_p(window)):
                    user.ShowWindow(ctypes.c_void_p(window),9)
                    user.SetForegroundWindow(ctypes.c_void_p(window))
                kernel.FreeConsole()
            return


def frontend_generation():
    if not frontend_running():return None
    for connection in psutil.net_connections(kind='tcp'):
        if connection.status=='LISTEN' and connection.laddr.port==3000 and connection.pid:
            process=psutil.Process(connection.pid)
            if owns_frontend(process):return f'{process.pid}:{process.create_time():.6f}'
    return None


def launch_frontend():
    """Serialize complete batch launches, including the build, in one console."""
    import msvcrt
    print('UVR5: Başlatma durumu kontrol ediliyor…',flush=True)
    folder=ROOT/'.runtime';folder.mkdir(exist_ok=True)
    with (folder/'frontend-launch.lock').open('a+b') as handle:
        handle.write(b'0');handle.flush()
        deadline=time.monotonic()+600
        announced_wait=False
        while True:
            if frontend_running():
                print('UVR5 zaten açık: http://localhost:3000 · Mevcut sunucuya bağlanılıyor.',flush=True)
                backend_status=subprocess.call(['node',str(ROOT/'frontend/scripts/ensure-backend.js'),'--no-browser','--quiet'],cwd=ROOT/'frontend')
                if backend_status:return backend_status
                focus_frontend_console()
                subprocess.call(['node',str(ROOT/'frontend/scripts/open-browser.js')],cwd=ROOT/'frontend')
                return 0
            try:
                handle.seek(0);msvcrt.locking(handle.fileno(),msvcrt.LK_NBLCK,1)
                break
            except OSError:
                if not announced_wait:
                    print('Başka bir başlatma devam ediyor; derleme ve sunucu bekleniyor…',flush=True)
                    announced_wait=True
                if time.monotonic()>deadline:raise RuntimeError('Önceki başlatma tamamlanamadı.')
                time.sleep(.5)
        try:
            print('UVR5: Backend hazırlanacak, ardından derleme ve uygulama başlatılacak.',flush=True)
            # CALL avoids CMD's outer-quote stripping when invoking a batch file.
            process=subprocess.Popen(['cmd.exe','/d','/c','call',str(ROOT/'start.bat'),'--owned'],cwd=ROOT,
                                     stdin=sys.stdin,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
            # Relay every child line explicitly; inherited console handles can be
            # redirected by a Windows terminal host or an invoking launcher.
            for line in iter(process.stdout.readline,b''):
                sys.stdout.buffer.write(line);sys.stdout.buffer.flush()
            return process.wait()
        finally:
            handle.seek(0);msvcrt.locking(handle.fileno(),msvcrt.LK_UNLCK,1)

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
    # Stop callers before their API, so the UI cannot keep polling a dead backend.
    if frontend:
        for process in psutil.process_iter():
            if process.pid!=os.getpid() and owns_frontend(process):terminate_tree(process)
    for process in psutil.process_iter():
        if process.pid!=os.getpid() and owns_backend(process):terminate_tree(process)

def stop_generation(expected_pid):
    current=service_info()
    if not current or current.get('pid')!=expected_pid:return
    stop(True)

def force_restart():
    """Used only after the API has explicitly cancelled and deleted every job."""
    for process in psutil.process_iter():
        if process.pid!=os.getpid() and owns_backend(process):terminate_tree(process)
    start()

def start(reuse_busy=False):
    current=service_info()
    if current and Path(current.get('root','')).resolve()!=ROOT:raise RuntimeError('8000 portunda başka bir proje çalışıyor.')
    if current and current.get('revision')==revision():return
    # Opening the UI must never briefly tear down an otherwise healthy backend.
    # A source revision can change while the development frontend remains open;
    # explicit restart actions still apply that revision when the user chooses.
    if current and reuse_busy:
        print('Çalışan yerel servis korunuyor; arayüz mevcut sunucuyla açılacak.')
        return
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
        if action=='frontend-launch':sys.exit(launch_frontend())
        with management_lock():
            if action=='frontend-check':
                if frontend_running():
                    print('UVR5 zaten çalışıyor: http://localhost:3000')
                    sys.exit(10)
            elif action=='frontend-token':
                token=frontend_generation()
                if not token:sys.exit(1)
                print(token);sys.exit(0)
            elif action=='frontend-focus':focus_frontend_console()
            elif action=='stop':
                if len(sys.argv)>2:stop_generation(int(sys.argv[2]))
                else:stop(True)
            elif action=='restart':stop();start()
            elif action=='force-restart':force_restart()
            elif action=='ensure':start()
            elif action=='launch':start(reuse_busy=True)
            else:raise ValueError('Unknown service action')
        print('UVR5: '+action+' tamamlandı.')
    except Exception as exc:print(str(exc),file=sys.stderr);sys.exit(1)
