"""Exercise real API functions against an isolated DB, without GPU or user files."""
import ast
from contextlib import closing
import asyncio
import hashlib
import html
import json
import os
import re
import sqlite3
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch
from typing import Optional, List
from fastapi import BackgroundTasks, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from local_projects import ProjectStore
from karaoke_timing import repair_timing, timing_issues


class ApiTests(unittest.TestCase):
    def setUp(self):
        ai = patch('lyrics_ai.correct_rows', side_effect=lambda path,rows,*args:(rows,None))
        ai.start(); self.addCleanup(ai.stop)
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        source = ast.parse(Path('api_modern.py').read_text(encoding='utf8'))
        names = {'init_favorites_db', '_get_lyrics_key', 'get_saved_lyrics', 'save_lyrics_db',
                 '_save_lyrics_db', '_lyrics_revision', 'WordModel', 'LyricSegmentModel',
                 'LyricsRequest', 'SaveLyricsRequest', 'save_lyrics_endpoint',
                 'KaraokeVideoRequest', 'generate_karaoke_video_endpoint',
                 'run_lyrics_alignment', 'transcribe_lyrics_endpoint', 'ReferenceApplyRequest',
                 'reference_apply_endpoint', 'run_reference_alignment', 'get_output',
                 'run_pasted_sync', 'paste_lyrics_endpoint'}
        nodes = [n for n in source.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and n.name in names]
        for n in nodes:
            n.decorator_list = []
        self.tasks = {}
        def create_task(extra=None):
            key = str(len(self.tasks)); self.tasks[key] = {'status': 'processing', **(extra or {})}; return key
        self.ns = dict(globals(), project_store=ProjectStore(root/'projects'), FAVORITES_DB_PATH=root/'lyrics.db', OUTPUT_DIR=root,
                       _lyrics_data_lock=threading.RLock(), _lyrics_inference_lock=threading.RLock(),
                       _find_audio_file=lambda name: root/name, get_whisper_model=lambda name: object(),
                       get_precision_whisper_model=lambda name: object(),
                       _safe_join_and_check=lambda parent, name: parent/name, ALLOWED_EXTENSIONS={'.wav','.flac','.mp4'},
                       _create_task=create_task, _update_task=lambda tid, **kw: self.tasks[tid].update(kw),
                       run_karaoke_video_task=lambda *a: None,
                       refine_turkish=lambda path, segments, language, progress: segments)
        exec(compile(ast.Module(body=nodes, type_ignores=[]), 'api_under_test', 'exec'), self.ns)
        self.seg = {'start': 1., 'end': 3., 'text': 'Bir iki', 'words': [
            {'word': 'Bir', 'start': 1.2, 'end': 1.7, 'timing_source': 'manual'},
            {'word': 'iki', 'start': 2.1, 'end': 2.5, 'timing_source': 'manual'}]}
        anchored = patch('karaoke_anchored.recognize_anchored', side_effect=lambda *args:
            self.ns['refine_turkish'](args[0], self.ns['align_lyrics'](), 'tr', None))
        anchored.start()
        self.addCleanup(anchored.stop)

    def tearDown(self): self.tmp.cleanup()

    def test_save_roundtrip_preserves_word_times_and_metadata(self):
        req = self.ns['SaveLyricsRequest'](file_name='sample_Vocals.wav', language='tr', segments=[self.seg])
        result = asyncio.run(self.ns['save_lyrics_endpoint'](req))
        loaded = self.ns['get_saved_lyrics']('sample_Instrumental.wav')
        self.assertEqual(loaded['segments'], result['segments'])
        self.assertEqual(loaded['segments'][0]['words'][0]['start'], 1.2)
        self.assertEqual(loaded['segments'][0]['words'][0]['timing_source'], 'manual')

    def test_history_keeps_previous_edit(self):
        save = self.ns['save_lyrics_db']
        save('sample.wav', 'tr', [self.seg]); previous = json.dumps([self.seg], ensure_ascii=False)
        self.seg['words'][0]['start'] = 1.3
        save('sample.wav', 'tr', [self.seg])
        with closing(sqlite3.connect(self.ns['FAVORITES_DB_PATH'])) as conn:
            self.assertEqual(conn.execute('select segments_json from lyrics_history').fetchone()[0], previous)

    def test_render_rejects_overlap_before_creating_task(self):
        self.seg['words'][1]['start'] = 1.5
        req = self.ns['KaraokeVideoRequest'](inst_file='sample.wav', segments=[self.seg])
        with self.assertRaises(HTTPException) as err:
            asyncio.run(self.ns['generate_karaoke_video_endpoint'](req, BackgroundTasks()))
        self.assertEqual(err.exception.status_code, 422)
        self.assertFalse(self.tasks)

    def test_cached_lyrics_do_not_trigger_alignment(self):
        self.ns['save_lyrics_db']('sample.wav', 'tr', [self.seg])
        req = self.ns['LyricsRequest'](file_name='sample.wav')
        bg = BackgroundTasks()
        self.assertTrue(self.ns['transcribe_lyrics_endpoint'](req, bg)['cached'])
        self.assertFalse(bg.tasks)

    def test_render_accepts_confidence_warning(self):
        self.seg['words'][0]['needs_review'] = True
        req = self.ns['KaraokeVideoRequest'](inst_file='sample.wav', segments=[self.seg])
        bg = BackgroundTasks()
        result = asyncio.run(self.ns['generate_karaoke_video_endpoint'](req, bg))
        self.assertIn('task_id',result)
        self.assertEqual(len(bg.tasks),1)

    def test_background_alignment_publishes_complete_result(self):
        self.ns['align_lyrics'] = lambda *a: [self.seg]
        req = self.ns['LyricsRequest'](file_name='sample.wav', force=True, raw_lyrics_text='Bir iki', language='tr')
        bg = BackgroundTasks(); job = self.ns['transcribe_lyrics_endpoint'](req, bg)
        asyncio.run(bg())
        task = self.tasks[job['task_id']]
        self.assertEqual(task['status'], 'completed')
        self.assertEqual(task['result']['segments'][0]['words'][0]['start'], 1.2)

    def test_turkish_empty_four_pass_result_falls_back_to_direct_whisper(self):
        class Word:
            def __init__(self, word, start, end): self.word,self.start,self.end=word,start,end; self.probability=.42
        class Decoded:
            words=[Word('Merhaba',1.0,1.5),Word('dünya',1.6,2.2)]
        class Model:
            def transcribe(self, *args, **kwargs): return iter([Decoded()]), None
        self.ns['get_whisper_model'] = lambda name: Model()
        req=self.ns['LyricsRequest'](file_name='sample.wav',force=True,language='tr')
        bg=BackgroundTasks();job=self.ns['transcribe_lyrics_endpoint'](req,bg)
        with patch('karaoke_anchored.recognize_anchored',side_effect=ValueError('No reliable anchors')):
            asyncio.run(bg())
        task=self.tasks[job['task_id']]
        self.assertEqual(task['status'],'completed')
        word=task['result']['segments'][0]['words'][0]
        self.assertEqual(word['word'],'Merhaba')
        self.assertEqual(word['timing_source'],'whisper')
        self.assertTrue(word['needs_review'])

    def test_ai_review_failure_does_not_discard_whisper_lyrics(self):
        req=self.ns['LyricsRequest'](file_name='sample.wav',force=True,language='tr')
        bg=BackgroundTasks();job=self.ns['transcribe_lyrics_endpoint'](req,bg)
        with patch('karaoke_anchored.recognize_anchored',return_value=[self.seg]), \
             patch('lyrics_ai.correct_rows',side_effect=RuntimeError('Gemini HTTP 503')):
            asyncio.run(bg())
        task=self.tasks[job['task_id']]
        self.assertEqual(task['status'],'completed')
        self.assertEqual(task['result']['segments'][0]['text'],'Bir iki')
        self.assertEqual(task['result']['ai_report']['status'],'unavailable')

    def test_late_alignment_cannot_overwrite_new_manual_edit(self):
        self.ns['save_lyrics_db']('sample.wav', 'tr', [self.seg])
        req = self.ns['LyricsRequest'](file_name='sample.wav', force=True, raw_lyrics_text='Bir iki', language='tr')
        bg = BackgroundTasks(); job = self.ns['transcribe_lyrics_endpoint'](req, bg)
        self.ns['align_lyrics'] = lambda *a: [self.seg]
        newer = json.loads(json.dumps(self.seg)); newer['words'][0]['start'] = 1.4
        self.ns['save_lyrics_db']('sample.wav', 'tr', [newer])
        asyncio.run(bg())
        self.assertEqual(self.tasks[job['task_id']]['status'], 'failed')
        self.assertEqual(self.ns['get_saved_lyrics']('sample.wav')['segments'][0]['words'][0]['start'], 1.4)

    def test_bounded_paste_saves_after_four_unsuccessful_attempts(self):
        from karaoke_anchored import anchor_transcript_rows
        rows,report=anchor_transcript_rows('Bir\nİki',[])
        report['attempts']=4
        req=self.ns['LyricsRequest'](file_name='sample.wav',raw_lyrics_text='Bir\nİki')
        bg=BackgroundTasks();job=self.ns['paste_lyrics_endpoint'](req,bg)
        with patch('paste_sync.synchronize',return_value=(rows,report)):
            asyncio.run(bg())
        task=self.tasks[job['task_id']]
        self.assertEqual(task['status'],'completed')
        self.assertEqual(task['result']['paste_report']['attempts'],4)
        self.assertEqual([s['text'] for s in self.ns['get_saved_lyrics']('sample.wav')['segments']],['Bir','İki'])

    def test_pasted_missing_line_is_saved_as_pending_and_later_lines_continue(self):
        self.ns['align_lyrics']=lambda *args:[self.seg]
        req=self.ns['LyricsRequest'](file_name='sample.wav',force=True,raw_lyrics_text='Eksik\nBir iki',language='tr')
        bg=BackgroundTasks();job=self.ns['transcribe_lyrics_endpoint'](req,bg)
        asyncio.run(bg())
        task=self.tasks[job['task_id']]
        self.assertEqual(task['status'],'completed')
        self.assertEqual(task['result']['paste_report']['pending'],[1])
        saved=self.ns['get_saved_lyrics']('sample.wav')['segments']
        self.assertEqual([s['text'] for s in saved],['Eksik','Bir iki'])
        self.assertEqual(saved[1]['words'][0]['start'],1.2)
        self.assertEqual(saved[0]['start'],saved[0]['end'])

    def test_pasted_text_survives_recognizer_value_error(self):
        req=self.ns['LyricsRequest'](file_name='sample.wav',force=True,raw_lyrics_text='Bir\nİki',language='tr')
        bg=BackgroundTasks();job=self.ns['transcribe_lyrics_endpoint'](req,bg)
        with patch('karaoke_anchored.recognize_anchored',side_effect=ValueError('No reliable anchors')):
            asyncio.run(bg())
        task=self.tasks[job['task_id']]
        self.assertEqual(task['status'],'completed')
        self.assertEqual(task['result']['paste_report']['pending'],[1,2])

    def test_character_alignment_result_is_saved_instead_of_coarse_times(self):
        self.ns['align_lyrics'] = lambda *a: [self.seg]
        def refine(path, segments, language, progress):
            updated = json.loads(json.dumps(segments))
            updated[0]['words'][0].update(start=1.25, end=1.65, timing_source='ctc')
            return updated
        self.ns['refine_turkish'] = refine
        req = self.ns['LyricsRequest'](file_name='sample.wav', force=True, raw_lyrics_text='Bir iki', language='tr')
        bg = BackgroundTasks(); job = self.ns['transcribe_lyrics_endpoint'](req, bg)
        asyncio.run(bg())
        self.assertEqual(self.tasks[job['task_id']]['status'], 'completed')
        word = self.ns['get_saved_lyrics']('sample.wav')['segments'][0]['words'][0]
        self.assertEqual((word['start'],word['end'],word['timing_source']), (1.25,1.65,'ctc'))

    def test_alignment_failure_preserves_previous_lyrics(self):
        self.ns['save_lyrics_db']('sample.wav', 'tr', [self.seg])
        def fail(*a): raise RuntimeError('alignment failed')
        self.ns['align_lyrics'] = fail
        req = self.ns['LyricsRequest'](file_name='sample.wav', force=True, raw_lyrics_text='Bir iki', language='tr')
        bg = BackgroundTasks(); job = self.ns['transcribe_lyrics_endpoint'](req, bg)
        asyncio.run(bg())
        self.assertEqual(self.tasks[job['task_id']]['status'], 'failed')
        self.assertEqual(self.ns['get_saved_lyrics']('sample.wav')['segments'][0]['words'][0]['start'], 1.2)

    def test_reference_rejects_stale_snapshot(self):
        self.ns['save_lyrics_db']('sample.wav', 'tr', [self.seg])
        stale = json.loads(json.dumps(self.seg)); stale['text'] = 'Eski'
        req = self.ns['ReferenceApplyRequest'](file_name='sample.wav', segments=[stale], edits={0: 'Yeni'})
        with self.assertRaises(HTTPException) as ctx:
            self.ns['reference_apply_endpoint'](req, BackgroundTasks())
        self.assertEqual(ctx.exception.status_code, 409)

    def test_reference_job_preserves_intervening_edit(self):
        self.ns['save_lyrics_db']('sample.wav', 'tr', [self.seg])
        req = self.ns['ReferenceApplyRequest'](file_name='sample.wav', segments=[self.seg], edits={0: 'Yeni'})
        bg = BackgroundTasks(); job = self.ns['reference_apply_endpoint'](req, bg)
        newer = json.loads(json.dumps(self.seg)); newer['words'][0]['start'] = 1.4
        self.ns['save_lyrics_db']('sample.wav', 'tr', [newer])
        with patch('karaoke_reference.align_changed_rows', return_value=[self.seg]): asyncio.run(bg())
        self.assertEqual(self.tasks[job['task_id']]['status'], 'failed')
        self.assertEqual(self.ns['get_saved_lyrics']('sample.wav')['segments'][0]['words'][0]['start'], 1.4)

    def test_reference_job_saves_result(self):
        self.ns['save_lyrics_db']('sample.wav', 'tr', [self.seg])
        req = self.ns['ReferenceApplyRequest'](file_name='sample.wav', segments=[self.seg], edits={0: 'Bir iki'})
        bg = BackgroundTasks(); job = self.ns['reference_apply_endpoint'](req, bg)
        with patch('karaoke_reference.align_changed_rows', return_value=[self.seg]): asyncio.run(bg())
        self.assertEqual(self.tasks[job['task_id']]['status'], 'completed')

    def test_missing_audio_never_returns_similarly_named_track(self):
        (self.ns['OUTPUT_DIR']/'Karaoke_Sync_Test_Vocals.wav').write_bytes(b'test')
        with self.assertRaises(HTTPException) as ctx:
            asyncio.run(self.ns['get_output']('Karaoke_Sync_Test_Vocals_missing.wav'))
        self.assertEqual(ctx.exception.status_code, 404)

    def test_unicode_equivalent_audio_name_is_supported(self):
        import unicodedata
        name = 'şarkı.wav'
        (self.ns['OUTPUT_DIR']/name).write_bytes(b'test')
        result = asyncio.run(self.ns['get_output'](unicodedata.normalize('NFD',name)))
        self.assertEqual(Path(result.path).name, name)


if __name__ == '__main__': unittest.main()
