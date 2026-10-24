import ast
from contextlib import closing
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch

from fastapi import FastAPI, BackgroundTasks
from fastapi.testclient import TestClient
from task_cancellation import TaskCancellation


class CancellationTests(unittest.TestCase):
    def test_cancelled_queued_task_never_starts(self):
        cancel=TaskCancellation();work=Mock()
        cancel.register('queued');cancel.cancel(['queued'])
        cancel.task(work)('queued')
        work.assert_not_called()
        self.assertEqual(cancel.running,set())

    def test_running_task_unwinds_finally_and_skips_fallback_and_save(self):
        cancel=TaskCancellation();started=threading.Event();release=threading.Event();events=[]
        @cancel.task
        def work(identifier):
            try:
                started.set();release.wait(5)
                cancel.checkpoint()
                events.append('saved')
            except Exception:
                events.append('fallback')
            finally:events.append('released')
        worker=threading.Thread(target=work,args=('running',));worker.start()
        try:
            self.assertTrue(started.wait(2));cancel.cancel(['running'])
        finally:release.set();worker.join(3)
        self.assertFalse(worker.is_alive());self.assertEqual(events,['released'])

    def test_only_cancelled_jobs_subprocess_is_killed(self):
        cancel=TaskCancellation();started=threading.Event();done=threading.Event();children=[]
        popen=cancel.popen_class(subprocess.Popen)
        @cancel.task
        def work(identifier):
            with popen([sys.executable,'-c','import time;time.sleep(30)']) as child:
                children.append(child);started.set();child.wait()
            cancel.checkpoint();done.set()
        with subprocess.Popen([sys.executable,'-c','import time;time.sleep(30)']) as unrelated:
            worker=threading.Thread(target=work,args=('render',));worker.start()
            try:
                self.assertTrue(started.wait(3));cancel.cancel(['render']);worker.join(5)
                self.assertFalse(worker.is_alive());self.assertIsNotNone(children[0].poll())
                self.assertIsNone(unrelated.poll());self.assertFalse(done.is_set())
            finally:
                unrelated.kill()
                for child in children:
                    if child.poll() is None:child.kill()
                worker.join(3)

    def test_cancel_before_spawn_prevents_process_creation(self):
        cancel=TaskCancellation()
        popen=cancel.popen_class(subprocess.Popen)
        @cancel.task
        def work(identifier):
            cancel.cancel([identifier])
            with popen([sys.executable,'-c',"raise RuntimeError('must not run')"]):
                self.fail('cancelled spawn succeeded')
        work('queued')

    def test_real_torch_forward_stops_and_releases_gpu_operation(self):
        import api_modern as api
        import torch
        started=threading.Event();release=threading.Event();finished=[]
        model=torch.nn.Linear(2,2)
        @api.cancellable_task
        @api.gpu_operation
        def work(identifier):
            started.set();release.wait(5)
            model(torch.ones(1,2));finished.append(True)
        with patch.object(api,'_release_all_gpu_resources') as cleanup:
            worker=threading.Thread(target=work,args=('test-forward-cancel',));worker.start()
            try:
                self.assertTrue(started.wait(2))
                api.task_cancellation.cancel(['test-forward-cancel'])
            finally:release.set();worker.join(3)
            self.assertFalse(worker.is_alive());self.assertEqual(finished,[])
            cleanup.assert_called_once()

    def test_cancel_all_http_keeps_same_service_and_prevents_late_results(self):
        cancel=TaskCancellation();started=threading.Event();release=threading.Event();saved=[]
        @cancel.task
        def work(identifier):
            started.set();release.wait(5)
            with cancel.commit():saved.append('late result')
        cancel.register('active')
        worker=threading.Thread(target=work,args=('active',));worker.start()
        self.assertTrue(started.wait(2))
        source=ast.parse(Path('api_modern.py').read_text(encoding='utf8'))
        endpoint=next(n for n in source.body if isinstance(n,ast.FunctionDef) and n.name=='cancel_and_delete_all_tasks')
        endpoint.decorator_list=[]
        with tempfile.TemporaryDirectory() as directory:
            db=Path(directory)/'jobs.db'
            with closing(sqlite3.connect(db)) as conn:
                conn.execute('CREATE TABLE lyrics_jobs (task_id TEXT,status TEXT)')
            audio=Mock();audio.list.return_value=[]
            namespace=dict(BackgroundTasks=BackgroundTasks,tasks={'active':{'status':'processing'}},tasks_lock=threading.Lock(),
                sqlite3=sqlite3,closing=closing,FAVORITES_DB_PATH=db,task_cancellation=cancel,audio_jobs=audio,separation_tasks=Mock())
            exec(compile(ast.Module(body=[endpoint],type_ignores=[]),'cancel-endpoint','exec'),namespace)
            app=FastAPI();app.post('/api/tasks/cancel-all')(namespace['cancel_and_delete_all_tasks'])
            app.get('/api/service')(lambda:{'pid':os.getpid()})
            try:
                with TestClient(app) as client:
                    before=client.get('/api/service').json()['pid']
                    response=client.post('/api/tasks/cancel-all')
                    self.assertEqual(response.status_code,200)
                    for _ in range(5):self.assertEqual(client.get('/api/service').json()['pid'],before)
                    release.set();worker.join(3)
                    self.assertFalse(worker.is_alive());self.assertEqual(saved,[])
            finally:release.set();worker.join(3)


if __name__=='__main__':unittest.main()
