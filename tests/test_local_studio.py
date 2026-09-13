import json
from pathlib import Path
import tempfile
import threading
import time
import unittest
from local_projects import ProjectStore
from audio_jobs import AudioJobs,JobCancelled

class ProjectTests(unittest.TestCase):
    def test_migration_delete_and_recovery(self):
        with tempfile.TemporaryDirectory() as root:
            store=ProjectStore(root)
            key='uvr-passages-v2:song.wav:12:9.3'
            store.put(key,'old');store.put(key,'new')
            self.assertEqual(ProjectStore(root).get(key),'new')
            store.put(key,'legacy',only_missing=True)
            self.assertEqual(store.get(key),'new')
            store.path(key).write_text('{broken')
            self.assertEqual(store.get(key),'old')
            store.put(key,None);store.put(key,'legacy',only_missing=True)
            self.assertIn(key,store.all());self.assertIsNone(store.get(key))
            self.assertEqual(store.identity(key),'song.wav')
    def test_library_migration_merges_browsers_without_resurrecting_deleted_items(self):
        with tempfile.TemporaryDirectory() as root:
            store=ProjectStore(root)
            store.put('uvr_library',json.dumps([{'id':1,'stems':['song.wav']}]))
            store.migrate('uvr_library',json.dumps([{'id':2,'stems':['other.wav']}]))
            self.assertEqual(len(json.loads(store.get('uvr_library'))),2)
            store.put('uvr_library',json.dumps([{'id':2,'stems':['other.wav']}]))
            store.migrate('uvr_library',json.dumps([{'id':1,'stems':['song.wav']}]))
            self.assertEqual([item['id'] for item in json.loads(store.get('uvr_library'))],[2])
            self.assertEqual(store.get('project:2')['audio_files'][0]['file'],'other.wav')

    def test_stale_library_snapshot_cannot_delete_another_tabs_project(self):
        with tempfile.TemporaryDirectory() as root:
            store=ProjectStore(root)
            store.update_library(json.dumps([{'id':1,'stems':[]}]))
            store.update_library(json.dumps([{'id':2,'stems':[]}]))
            store.update_library('[]')
            self.assertEqual(len(json.loads(store.get('uvr_library'))),2)
            store.update_library('[]',[1])
            self.assertEqual([item['id'] for item in json.loads(store.get('uvr_library'))],[2])

    def test_parallel_entries_do_not_lose_data(self):
        with tempfile.TemporaryDirectory() as root:
            store=ProjectStore(root)
            threads=[threading.Thread(target=store.put,args=(f'uvr-stem-settings:song{i}.wav',str(i))) for i in range(20)]
            for t in threads:t.start()
            for t in threads:t.join()
            self.assertEqual(len(store.all()),20)

class JobTests(unittest.TestCase):
    def wait(self,jobs,identifier,status):
        deadline=time.monotonic()+5
        while time.monotonic()<deadline:
            current=jobs.get(identifier)
            if current['status']==status:return current
            time.sleep(.02)
        self.fail(str(jobs.get(identifier)))
    def test_cancel_queue_cache_and_source_invalidation(self):
        with tempfile.TemporaryDirectory() as root:
            source=Path(root)/'source.wav';source.write_bytes(b'first')
            entered=threading.Event();release=threading.Event();calls=[]
            def render(src,target,pitch,tempo,cancel_event,progress):
                calls.append(pitch);entered.set()
                while not release.wait(.01):
                    if cancel_event.is_set():raise JobCancelled()
                Path(target).write_bytes(b'audio'+Path(src).read_bytes())
            jobs=AudioJobs(Path(root)/'cache',render)
            first=jobs.submit(source,2,owner='player')
            self.assertTrue(entered.wait(2))
            queued=jobs.submit(source,3,owner='other')
            jobs.cancel(queued['id']);jobs.cancel(first['id'])
            self.wait(jobs,first['id'],'cancelled')
            self.assertEqual(jobs.get(queued['id'])['status'],'cancelled')
            self.assertEqual(calls,[2])
            release.set();second=jobs.submit(source,7)
            self.wait(jobs,second['id'],'completed')
            cached=jobs.submit(source,7)
            self.assertTrue(cached['cached']);self.assertEqual(calls,[2,7])
            self.assertEqual(jobs.result(cached['id']),b'audiofirst')
            source.write_bytes(b'new source')
            changed=jobs.submit(source,7);self.assertFalse(changed['cached'])
            self.wait(jobs,changed['id'],'completed')
            # Cleaning cache must never touch active working files.
            working=jobs.root/'abc.working-job.wav';working.write_bytes(b'partial')
            self.assertEqual(jobs.prune(clear=True)['files'],0);self.assertTrue(working.exists())
            jobs.close()
    def test_restart_reports_interrupted_job(self):
        with tempfile.TemporaryDirectory() as root:
            source=Path(root)/'source.wav';source.write_bytes(b'source')
            jobs=AudioJobs(Path(root)/'cache',None,start_worker=False)
            job=jobs.submit(source,2)
            recovered=AudioJobs(Path(root)/'cache',None,start_worker=False)
            self.assertEqual(recovered.get(job['id'])['status'],'interrupted')
            recovered.close();jobs.close()

if __name__=='__main__':unittest.main()

class ServiceTests(unittest.TestCase):
    def test_process_ownership_is_checkout_specific(self):
        import service_control as control
        class Process:
            def __init__(self,cwd,exe,args):self.directory=cwd;self.executable=exe;self.args=args
            def cwd(self):return str(self.directory)
            def exe(self):return str(self.executable)
            def cmdline(self):return self.args
        root=control.ROOT
        self.assertTrue(control.owns_backend(Process(root,root/'env/python.exe',['python','api_modern.py'])))
        self.assertFalse(control.owns_backend(Process(root.parent,root/'env/python.exe',['python','api_modern.py'])))
        self.assertFalse(control.owns_frontend(Process(root/'frontend','node.exe',['node','unrelated-next-task.js'])))
        self.assertTrue(control.owns_frontend(Process(root/'frontend','node.exe',['node','node_modules/next/dist/bin/next','dev'])))
