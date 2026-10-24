"""Content-based build cache shared by startup and the live source watcher."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import uuid
import time
from contextlib import contextmanager

ROOT=Path(__file__).resolve().parent


@contextmanager
def build_lock(root=ROOT,name='source-build.lock'):
    folder=root/'.runtime';folder.mkdir(exist_ok=True)
    with (folder/name).open('a+b') as handle:
        handle.write(b'0');handle.flush();handle.seek(0)
        if os.name=='nt':
            import msvcrt
            deadline=time.monotonic()+1900
            while True:
                try:msvcrt.locking(handle.fileno(),msvcrt.LK_NBLCK,1);break
                except OSError:
                    if time.monotonic()>deadline:raise RuntimeError('Derleme kilidi zaman aşımı')
                    time.sleep(.5);handle.seek(0)
        else:
            import fcntl
            fcntl.flock(handle,fcntl.LOCK_EX)
        try:yield
        finally:
            handle.seek(0)
            if os.name=='nt':msvcrt.locking(handle.fileno(),msvcrt.LK_UNLCK,1)
            else:fcntl.flock(handle,fcntl.LOCK_UN)


def fingerprint(root=ROOT):
    files=set(root.glob('*.py'))
    for pattern in ('*.bat','*.ps1','requirements*.txt','pyproject.toml','frontend/.env*'):
        files.update(p for p in root.glob(pattern) if p.is_file())
    for folder in ('frontend/src','frontend/scripts','frontend/public'):
        directory=root/folder
        if directory.exists():files.update(p for p in directory.rglob('*') if p.is_file())
    for pattern in ('frontend/*.json','frontend/*.js','frontend/*.mjs','frontend/*.ts','assets/*.json'):
        files.update(root.glob(pattern))
    digest=hashlib.sha256()
    for path in sorted(files):
        if path.name in ('custom_settings.json','next-env.d.ts') or path.name.endswith('.tsbuildinfo'):continue
        content=path.read_bytes()
        if path.name=='tsconfig.json':
            config=json.loads(content)
            config['include']=[p for p in config.get('include',[]) if not p.startswith('.next')]
            content=json.dumps(config,sort_keys=True).encode()
        digest.update(path.relative_to(root).as_posix().encode()+b'\0'+content+b'\0')
    return digest.hexdigest()


def manifest(root=ROOT):
    try:return json.loads((root/'.runtime/frontend-build.json').read_text(encoding='utf8'))
    except (OSError,ValueError):return {}


def cached(root=ROOT):
    data=manifest(root)
    dist=data.get('dist','')
    if not dist.startswith('.next') or Path(dist).name!=dist:return None
    if data.get('digest')!=fingerprint(root):return None
    target=root/'frontend'/dist
    if not all((target/name).is_file() for name in ('BUILD_ID','prerender-manifest.json','routes-manifest.json')):return None
    return data


def record(environment,digest,root=ROOT):
    folder=root/'.runtime';folder.mkdir(exist_ok=True)
    temp=folder/('frontend-build-'+uuid.uuid4().hex+'.tmp')
    temp.write_text(json.dumps({'digest':digest,'dist':environment.get('UVR_NEXT_DIST','.next')},indent=2),encoding='utf8')
    os.replace(temp,folder/'frontend-build.json')


def ensure():
    if cached():
        print('Kodlar degismedi; build atlandi.',flush=True);return
    from studio_restart import build,update
    before=fingerprint()
    identifier='startup-'+uuid.uuid4().hex
    try:
        environment=build(identifier)
        if fingerprint()!=before:raise RuntimeError('Derleme sirasinda kod degisti. Dosyalari kaydedip yeniden baslatin.')
        record(environment,before)
        update(identifier,'completed','Güncel üretim derlemesi hazır.')
    except Exception as error:
        update(identifier,'failed',str(error));raise
    print('Yeni uretim derlemesi hazir.',flush=True)


def start_watcher():
    if os.environ.get('UVR_AUTO_REBUILD')=='0':return
    logs=ROOT/'logs';logs.mkdir(exist_ok=True)
    with (logs/'source-watch.log').open('ab') as output:
        subprocess.Popen([sys.executable,str(ROOT/'studio_watch.py')],cwd=ROOT,stdin=subprocess.DEVNULL,
            stdout=output,stderr=subprocess.STDOUT,
            creationflags=(subprocess.CREATE_NO_WINDOW|subprocess.DETACHED_PROCESS) if os.name=='nt' else 0,
            start_new_session=os.name!='nt')


if __name__=='__main__':
    try:
        if sys.argv[1:] == ['watch']:start_watcher()
        else:ensure()
    except Exception as error:
        print(str(error),file=sys.stderr);sys.exit(1)
