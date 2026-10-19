import ast
from pathlib import Path
import threading
from types import SimpleNamespace
from typing import List,Optional
import unittest
from unittest.mock import patch
from fastapi import BackgroundTasks,HTTPException
from pydantic import BaseModel,Field


class SuppliedApiTests(unittest.TestCase):
    def test_repeat_archive_survives_save_and_reload(self):
        archive=[{'row':{'id':'duplicate','text':'AYNI','start':0,'end':1,'words':[]},
                  'matched_row_id':'kept','bounds':[2,2.1],'reason':'duplicate_block_without_audio_gap'}]
        row=self.ns['LyricSegmentModel'](id='kept',text='AYNI',start=2.1,end=3,repeat_cleanup=archive)
        saved=row.model_dump()
        self.assertEqual(saved['repeat_cleanup'],archive)
        self.assertEqual(self.ns['LyricSegmentModel'](**saved).model_dump()['repeat_cleanup'],archive)

    def test_inferred_word_provenance_survives_save_model(self):
        reference={'row_ids':['earlier'],'anchor_words':5,'method':'matching_verse_tempo'}
        word=self.ns['WordModel'](word='SON',start=10,end=11,timing_source='repeat_inferred',timing_reference=reference)
        self.assertEqual(word.model_dump()['timing_reference'],reference)
        self.assertEqual(word.model_dump()['timing_source'],'repeat_inferred')
        self.assertIsNone(word.probability)

    def setUp(self):
        names={'WordModel','LyricSegmentModel','SaveLyricsRequest','SuppliedAlignmentRequest',
               'supplied_alignment_endpoint','run_supplied_alignment'}
        nodes=[n for n in ast.parse(Path('api_modern.py').read_text(encoding='utf8')).body if getattr(n,'name',None) in names]
        for node in nodes:node.decorator_list=[]
        self.tasks={};self.created=[]
        def create(extra):self.created.append(extra);self.tasks['test']={};return 'test'
        self.ns={**globals(),'_lyrics_inference_lock':threading.RLock(),'_lyrics_data_lock':threading.RLock(),
            'separation_tasks':SimpleNamespace(lock=threading.RLock(),records={}),
            '_find_audio_file':lambda _:Path('audio.wav'),'_lyrics_revision':lambda _: 'original',
            '_create_task':create,'_update_task':lambda task,**data:self.tasks[task].update(data),
            'tasks':self.tasks,'tasks_lock':threading.Lock(),'audio_jobs':SimpleNamespace(list=lambda:[])}
        exec(compile(ast.Module(nodes,type_ignores=[]),'api_modern.py','exec'),self.ns)

    def request(self,segments=None):
        return self.ns['SuppliedAlignmentRequest'](file_name='song.wav',language='tr',
            segments=segments if segments is not None else [{'text':'VERDİĞİM SÖZ','start':0,'end':.5}])

    def test_no_task_without_explicit_request_and_empty_input_rejected(self):
        self.assertEqual(self.created,[])

    def test_marker_persists_without_changing_legacy_serialization(self):
        row=self.ns['LyricSegmentModel'](text='SÖZ',start=0,end=1)
        self.assertNotIn('alignment_mode',row.model_dump())
        row.alignment_mode='supplied_ctc'
        self.assertEqual(row.model_dump()['alignment_mode'],'supplied_ctc')
        with self.assertRaises(HTTPException):self.ns['supplied_alignment_endpoint'](self.request([]),BackgroundTasks())
        self.assertEqual(self.created,[])

    def test_explicit_request_queues_only_supplied_alignment(self):
        background=BackgroundTasks()
        result=self.ns['supplied_alignment_endpoint'](self.request(),background)
        self.assertEqual(result,{'task_id':'test'})
        self.assertEqual(len(background.tasks),1)
        self.assertEqual(background.tasks[0].func,self.ns['run_supplied_alignment'])
        self.assertEqual(self.created[0]['model_type'],'supplied_alignment')

    def test_result_returns_without_saving_or_transcribing(self):
        self.tasks['test']={}
        rows=[{'text':'VERDİĞİM SÖZ','start':1,'end':3}]
        with patch('karaoke_supplied_alignment.align_supplied',return_value=(rows,{'linked_words':2})) as align:
            self.ns['run_supplied_alignment']('test',self.request(),'original')
        self.assertEqual(self.tasks['test']['status'],'completed')
        self.assertEqual(self.tasks['test']['result']['segments'],rows)
        self.assertEqual(align.call_args.args[1][0]['text'],'VERDİĞİM SÖZ')
        self.assertEqual(align.call_args.kwargs['language'],'tr')

    def test_kurmanji_is_accepted_and_forwarded_without_forcing_turkish(self):
        req=self.request();req.language='kmr'
        background=BackgroundTasks()
        self.ns['supplied_alignment_endpoint'](req,background)
        with patch('karaoke_supplied_alignment.align_supplied',return_value=([],{})) as align:
            self.ns['run_supplied_alignment']('test',req,'original')
        self.assertEqual(align.call_args.kwargs['language'],'kmr')
        self.assertEqual(self.tasks['test']['status'],'completed')

    def test_unsupported_language_creates_no_task(self):
        req=self.request();req.language='de'
        with self.assertRaises(HTTPException):self.ns['supplied_alignment_endpoint'](req,BackgroundTasks())
        self.assertEqual(self.created,[])

    def test_concurrent_edit_discards_result(self):
        self.tasks['test']={};self.ns['_lyrics_revision']=lambda _: 'edited'
        with patch('karaoke_supplied_alignment.align_supplied',return_value=([],{})):
            self.ns['run_supplied_alignment']('test',self.request(),'original')
        self.assertEqual(self.tasks['test']['status'],'failed')
        self.assertNotIn('result',self.tasks['test'])


if __name__=='__main__':unittest.main()
