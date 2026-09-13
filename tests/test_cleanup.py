"""Cleanup regression tests use temporary files only."""
import ast
import asyncio
from contextlib import closing
import json
import os
from pathlib import Path
import shutil
import sqlite3
import tempfile
import unittest
from fastapi import HTTPException
from audio_jobs import AudioJobs
from local_projects import ProjectStore

class CleanupTests(unittest.TestCase):
    def test_cache_cleanup_removes_history_persistently_and_keeps_pending_jobs(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); source=root/'source.wav'; source.write_bytes(b'audio')
            jobs=AudioJobs(root/'cache',None,start_worker=False)
            cancelled=jobs.submit(source,2); jobs.cancel(cancelled['id'])
            pending=jobs.submit(source,3)
            cached=root/'cache'/(jobs._key(source,4)+'.wav'); cached.write_bytes(b'preview')
            jobs.submit(source,4)
            result=jobs.clear_cache_and_history()
            self.assertEqual(result['removed_jobs'],2)
            self.assertFalse(cached.exists())
            self.assertEqual([j['id'] for j in jobs.list()],[pending['id']])
            self.assertEqual(list(jobs.queue),[pending['id']])
            restored=AudioJobs(root/'cache',None,start_worker=False)
            self.assertEqual(len(restored.list()),1)
            restored.clear_cache_and_history()
            self.assertEqual(AudioJobs(root/'cache',None,start_worker=False).list(),[])
            jobs.close()

    def run_cleanup(self,root,blocked=False):
        node=next(n for n in ast.parse(Path('api_modern.py').read_text(encoding='utf-8')).body if getattr(n,'name','')=='clear_karaoke_data_endpoint')
        routes=ast.get_source_segment(Path('api_modern.py').read_text(encoding='utf-8'),node.decorator_list[0])
        self.assertIn('/api/projects/clear',routes)
        node.decorator_list=[]
        def prepare():
            if blocked:raise HTTPException(409,'Active job')
        jobs=AudioJobs(root/'cache',None,start_worker=False)
        ns=dict(globals(),__file__=str(root/'api_modern.py'),FAVORITES_DB_PATH=root/'db.sqlite',
                OUTPUT_DIR=root/'outputs',YTL_DIR=root/'ytdl',UPLOAD_DIR=root/'uploads',
                project_store=ProjectStore(root/'projects'),audio_jobs=jobs,prepare_service_stop=prepare)
        exec(compile(ast.Module(body=[node],type_ignores=[]),'cleanup-test','exec'),ns)
        return asyncio.run(ns['clear_karaoke_data_endpoint']())

    def test_clear_all_removes_files_database_and_project_snapshots(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            for name in ('outputs','ytdl','uploads','ytdlp','ytdl_downloads'):
                (root/name).mkdir(); (root/name/'test.wav').write_bytes(b'test')
            with closing(sqlite3.connect(root/'db.sqlite')) as db:
                db.execute('CREATE TABLE lyrics (id INTEGER)');db.execute('INSERT INTO lyrics VALUES (1)')
                db.execute('CREATE TABLE lyrics_history (id INTEGER)')
                db.commit()
            store=ProjectStore(root/'projects')
            store.put('uvr_library',json.dumps([{'id':1,'stems':['test.wav']}]))
            for key in ('lyrics:test.wav','uvr-history:test.wav','uvr-passages-v3:test.wav:row','uvr-stem-settings:test.wav'):
                store.put(key,'saved')
            result=self.run_cleanup(root)
            self.assertEqual(result['deleted_files_count'],5)
            self.assertEqual(result['deleted_lyrics_count'],1)
            self.assertEqual(json.loads(store.get('uvr_library')),[])
            self.assertIsNone(store.get('lyrics:test.wav'))
            self.assertIsNone(store.get('project:1'))
            self.assertFalse(list((root/'outputs').iterdir()))
            self.assertEqual(self.run_cleanup(root)['deleted_files_count'],0)

    def test_active_job_rejects_cleanup_before_touching_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'outputs').mkdir();file=root/'outputs'/'keep.wav';file.write_bytes(b'keep')
            with self.assertRaises(HTTPException) as error:self.run_cleanup(root,blocked=True)
            self.assertEqual(error.exception.status_code,409)
            self.assertEqual(file.read_bytes(),b'keep')
