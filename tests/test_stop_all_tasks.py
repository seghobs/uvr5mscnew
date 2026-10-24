import ast
from contextlib import closing
from pathlib import Path
import os
import sqlite3
import tempfile
import threading
import unittest
from unittest.mock import Mock
from task_cancellation import TaskCancellation

class StopAllTests(unittest.TestCase):
    def test_stops_all_unfinished_kinds_and_preserves_saved_data(self):
        source=ast.parse(Path('api_modern.py').read_text(encoding='utf8'))
        function=next(n for n in source.body if isinstance(n,ast.FunctionDef) and n.name=='cancel_and_delete_all_tasks')
        function.decorator_list=[]
        with tempfile.TemporaryDirectory() as directory:
            database=Path(directory)/'records.db'
            with closing(sqlite3.connect(database)) as conn:
                conn.execute('CREATE TABLE lyrics_jobs (task_id TEXT,status TEXT)')
                conn.executemany('INSERT INTO lyrics_jobs VALUES (?,?)',[('sync','processing'),('queued','queued'),('done','completed')])
                conn.execute('CREATE TABLE saved_lyrics (text TEXT)')
                conn.execute("INSERT INTO saved_lyrics VALUES ('keep me')")
                conn.commit()
            tasks={'sync':{'status':'processing'},'render':{'status':'processing'},'done':{'status':'completed'}}
            audio=Mock();audio.list.return_value=[{'id':'pitch','status':'processing'},{'id':'export','status':'queued'},{'id':'finished','status':'completed'}]
            separation=Mock();background=Mock();launch=Mock()
            cancellation=TaskCancellation()
            namespace=dict(tasks=tasks,tasks_lock=threading.Lock(),sqlite3=sqlite3,closing=closing,FAVORITES_DB_PATH=database,audio_jobs=audio,separation_tasks=separation,BackgroundTasks=object,_launch_service_control=launch,os=os,task_cancellation=cancellation)
            exec(compile(ast.Module(body=[function],type_ignores=[]),'stop-test','exec'),namespace)
            result=namespace['cancel_and_delete_all_tasks'](background)
            self.assertEqual(list(tasks),['done'])
            self.assertEqual(result['deleted_tasks'],5)
            self.assertNotIn('previous_pid',result)
            self.assertTrue(all(cancellation.events[key].is_set() for key in ('sync','render','queued')))
            self.assertEqual([call.args[0] for call in audio.cancel.call_args_list],['pitch','export'])
            separation.cancel_all.assert_called_once()
            background.add_task.assert_not_called()
            launch.assert_not_called()
            with closing(sqlite3.connect(database)) as conn:
                self.assertEqual(conn.execute('SELECT task_id FROM lyrics_jobs').fetchall(),[('done',)])
                self.assertEqual(conn.execute('SELECT text FROM saved_lyrics').fetchone()[0],'keep me')

if __name__=='__main__':unittest.main()
