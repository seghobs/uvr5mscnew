"""Bounded, cancellable audio jobs and a versioned LRU preview cache."""
from collections import deque
import hashlib
import json
import re
from pathlib import Path
import threading
import time
import uuid


class JobCancelled(Exception): pass


class AudioJobs:
    def __init__(self, root, render, max_bytes=2*1024**3, max_entries=32, start_worker=True):
        self.root=Path(root);self.root.mkdir(parents=True,exist_ok=True)
        self.render=render;self.max_bytes=max_bytes;self.max_entries=max_entries
        self.lock=threading.RLock();self.condition=threading.Condition(self.lock)
        self.jobs={};self.queue=deque();self.stopping=False
        self.state_file=self.root/'jobs.json'
        try:
            for job in json.loads(self.state_file.read_text(encoding='utf-8')):
                if job['status'] in ('queued','processing','cancelling'):
                    job.update(status='interrupted',message='Uygulama kapandı; yeniden başlatılabilir.')
                self.jobs[job['id']]=job
        except (OSError,ValueError):pass
        self.prune()
        if start_worker:
            threading.Thread(target=self._worker,daemon=True,name='uvr-audio-queue').start()

    def _persist(self):
        records=[{k:v for k,v in job.items() if k not in ('event',)} for job in list(self.jobs.values())[-100:]]
        temporary=self.state_file.with_suffix('.tmp')
        temporary.write_text(json.dumps(records,ensure_ascii=False),encoding='utf-8');temporary.replace(self.state_file)

    def _key(self, source, pitch):
        digest=hashlib.sha256()
        with Path(source).open('rb') as handle:
            for block in iter(lambda:handle.read(1024*1024),b''):digest.update(block)
        digest.update(f'r3-v2-formant-centre-float:{float(pitch):.12g}'.encode())
        return digest.hexdigest()

    def submit(self, source, pitch, tempo=1, kind='preview', owner='', output=None):
        source=Path(source).resolve()
        if kind not in ('preview','export'):raise ValueError('Invalid job type')
        key=self._key(source,pitch) if kind=='preview' else uuid.uuid4().hex
        with self.condition:
            # A changed selection replaces only this player's obsolete preview.
            for job in list(self.jobs.values()):
                if owner and kind=='preview' and job.get('owner')==owner and job['kind']=='preview' and job['status'] in ('queued','processing'):
                    self.cancel(job['id'])
            active=sum(j['status'] in ('queued','processing','cancelling') for j in self.jobs.values())
            if active>=24:raise ValueError('İşlem kuyruğu dolu. Önce bekleyen işlemleri tamamlayın veya iptal edin.')
            target=self.root/(key+'.wav') if kind=='preview' else Path(output).resolve()
            cached=kind=='preview' and target.is_file()
            now=time.time();job={'id':uuid.uuid4().hex,'kind':kind,'source':str(source),'pitch':pitch,'tempo':tempo,
                'owner':owner,'target':str(target),'status':'completed' if cached else 'queued','progress':1 if cached else 0,
                'message':'Önbellekten hazır' if cached else 'Sırada bekliyor','cached':cached,'created_at':now,'updated_at':now}
            self.jobs[job['id']]=job
            if cached:target.touch()
            else:job['event']=threading.Event();self.queue.append(job['id'])
            self._persist();self.condition.notify();return self.public(job)

    @staticmethod
    def public(job):
        return {k:v for k,v in job.items() if k not in ('event','target','source','owner')} | {'file_name':Path(job['source']).name,'output_file':Path(job['target']).name if job['kind']=='export' and job['status']=='completed' else None}

    def list(self):
        with self.lock:return [self.public(j) for j in reversed(list(self.jobs.values())[-100:])]

    def get(self, identifier):
        with self.lock:return self.public(self.jobs[identifier])

    def cancel(self, identifier):
        with self.condition:
            job=self.jobs[identifier]
            if job['status'] not in ('queued','processing','cancelling'):return self.public(job)
            job['event'].set();job['status']='cancelled' if job['status']=='queued' else 'cancelling'
            job['message']='İptal edildi' if job['status']=='cancelled' else 'İşlem durduruluyor'
            job['updated_at']=time.time();self._persist();self.condition.notify();return self.public(job)

    def retry(self, identifier):
        with self.lock:
            job=dict(self.jobs[identifier])
            if job['status'] in ('queued','processing','cancelling'):raise ValueError('İşlem zaten çalışıyor.')
        return self.submit(job['source'],job['pitch'],job['tempo'],job['kind'],job.get('owner',''),job['target'])

    def result(self, identifier):
        with self.lock:
            job=self.jobs[identifier]
            if job['status']!='completed' or job['kind']!='preview':raise ValueError('Önizleme hazır değil.')
            path=Path(job['target']);content=path.read_bytes();path.touch();return content

    def prune(self, clear=False):
        with self.lock:
            protected={j['target'] for j in self.jobs.values() if j['status'] in ('processing','cancelling')}
            files=sorted((p for p in self.root.glob('*.wav') if re.fullmatch(r'[0-9a-f]{64}\.wav',p.name)),key=lambda p:p.stat().st_mtime,reverse=True)
            size=0;count=0
            for path in files:
                size+=path.stat().st_size;count+=1
                if str(path) in protected:continue
                if clear or size>self.max_bytes or count>self.max_entries or time.time()-path.stat().st_mtime>7*86400:
                    path.unlink(missing_ok=True)
            remaining=[p for p in self.root.glob('*.wav') if re.fullmatch(r'[0-9a-f]{64}\.wav',p.name)]
            return {'bytes':sum(p.stat().st_size for p in remaining),'files':len(remaining),'limit_bytes':self.max_bytes}

    def close(self):
        with self.condition:
            self.stopping=True
            for job in list(self.jobs.values()):
                if job['status'] in ('queued','processing'):self.cancel(job['id'])
            self.condition.notify_all()

    def clear_cache_and_history(self):
        with self.lock:
            result=self.prune(clear=True)
            removed=[key for key,job in self.jobs.items() if job['status'] not in ('queued','processing','cancelling')]
            for key in removed:del self.jobs[key]
            self.queue=deque(key for key in self.queue if key in self.jobs)
            self._persist()
            return {**result,'removed_jobs':len(removed)}

    def _worker(self):
        while True:
            with self.condition:
                self.condition.wait_for(lambda:self.queue or self.stopping)
                if self.stopping:return
                job=self.jobs[self.queue.popleft()]
                if job['status']!='queued':continue
                job.update(status='processing',message='Ses hazırlanıyor',updated_at=time.time());self._persist()
            target=Path(job['target']);temporary=target.with_name(target.stem+'.working-'+job['id']+target.suffix)
            def progress(fraction,message):
                with self.lock:job.update(progress=fraction,message=message,updated_at=time.time())
            try:
                self.render(job['source'],temporary,job['pitch'],job['tempo'],cancel_event=job['event'],progress=progress)
                with self.lock:
                    if job['event'].is_set():raise JobCancelled()
                    temporary.replace(target)
                    job.update(status='completed',progress=1,message='Hazır',updated_at=time.time())
                    self.prune()
            except Exception as error:
                with self.lock:
                    cancelled=job['event'].is_set() or isinstance(error,JobCancelled)
                    job.update(status='cancelled' if cancelled else 'failed',message='İptal edildi' if cancelled else str(error),updated_at=time.time())
            finally:
                temporary.unlink(missing_ok=True)
                with self.lock:self._persist()
