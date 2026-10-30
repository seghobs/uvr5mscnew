import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
import soundfile as sf

from karaoke_automatic_recovery import (strict_vote,alignment_input,collect_pass,targets,
    proven,recover_automatic_alignment,contrast,phrase_repair,consistent_warps)
from karaoke_quality import checked_refinement
from karaoke_syllable_timing import syllable_fill,syllable_pieces
from task_cancellation import TaskCancelled


def word(text='SON',start=1.,end=2.,pending=True):
    return {'word':text,'start':start,'end':end,'probability':.4 if pending else .8,
            'needs_review':pending,'timing_source':'ctc'}


def observation(model='one',source='vocals',**kwargs):
    return {**word(pending=False),'model':model,'source':source,'channel':'mix',**kwargs}


class AutomaticRecoveryTests(unittest.TestCase):
    def test_auxiliary_language_pass_does_not_run_the_expensive_final_stage_twice(self):
        from karaoke_supplied_alignment import align_supplied
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'song.wav';sf.write(path,np.zeros(48000),16000)
            rows=[{'id':'manual','text':'SON','start':1.,'end':2.,'words':[
                {**word(pending=False),'timing_source':'manual'}]}]
            with patch('karaoke_interludes.music_evidence',return_value=([],[],False)),patch(
                    'karaoke_automatic_recovery.recover_automatic_alignment',return_value={
                        'automatic_recovery_enabled':True}) as stage:
                _,report=align_supplied(path,rows,language='kmr',repeat_estimation=False)
        stage.assert_called_once()
        self.assertEqual(stage.call_args.kwargs['language'],'kmr')
        self.assertTrue(report['automatic_recovery_enabled'])

    def test_repeat_warp_uses_majority_instead_of_two_conflicting_nearest_clips(self):
        observations=[{'row_id':str(i),'start':a,'end':b,'cost':cost} for i,(a,b,cost) in enumerate([
            (1.,2.,.05),(1.2,2.2,.06),(1.01,2.01,.08),(.99,2.02,.09)])]
        selected=consistent_warps(observations)
        self.assertEqual(len(selected),3)
        self.assertNotIn('1',[m['row_id'] for m in selected])
        self.assertEqual(consistent_warps(observations[:2]),[],'equal opposing transfers must remain uncertain')
        self.assertEqual(len(consistent_warps(observations+[dict(observations[0])])),3,'repeated evidence cannot vote twice')

    def test_normal_supplied_alignment_runs_the_permanent_recovery_stage(self):
        from karaoke_supplied_alignment import align_supplied
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'song.wav';sf.write(path,np.zeros(48000),16000)
            rows=[{'id':'manual','text':'SON','start':1.,'end':2.,'words':[
                {**word(pending=False),'timing_source':'manual'}]}]
            with patch('karaoke_interludes.music_evidence',return_value=([],[],False)),patch(
                    'karaoke_automatic_recovery.recover_automatic_alignment',return_value={
                        'automatic_recovery_enabled':True,'automatic_recovery_remaining_words':0}) as stage:
                actual,report=align_supplied(path,rows,language='tr',repeat_estimation=False)
        stage.assert_called_once()
        self.assertTrue(report['automatic_recovery_enabled'])
        self.assertEqual(actual[0]['words'][0]['timing_source'],'manual')

    def test_contexts_and_audio_views_of_same_model_are_not_two_models(self):
        self.assertIsNone(strict_vote([observation(),observation(source='original'),
            observation(channel='right')],word(),0,10))
        self.assertIsNotNone(strict_vote([observation(),observation('two')],word(),0,10))

    def test_equal_conflicting_placements_and_neighbor_overlap_stay_unverified(self):
        proposals=[observation(),observation('two'),observation(start=5.,end=6.),
                   observation('two',start=5.,end=6.)]
        self.assertIsNone(strict_vote(proposals,word(),0,10))
        self.assertIsNone(strict_vote([observation(),observation('two')],word(),1.5,10))

    def test_internal_punctuation_keeps_editor_text_and_rebuilds_measured_pieces(self):
        row={'id':'source','text':'GEL,BANA','start':1.,'end':4.,'words':[word('GEL,BANA',1.,4.)]}
        before=copy.deepcopy(row);request=alignment_input(row)
        self.assertEqual(row,before);self.assertEqual([w['word'] for w in request['words']],['GEL,','BANA'])
        def refine(_path,selected,_model,**kwargs):
            kwargs['progress'](0.,'row-progress')
            result=copy.deepcopy(selected)
            result[0]['words']=[word('GEL,',1.,1.5,False),word('BANA',3.,4.,False)]
            return result
        evidence={};messages=[]
        with patch('karaoke_ctc.refine_ctc',side_effect=refine):
            collect_pass('unused','vocals',[row],[0],'tr',.35,'mix',None,evidence,lambda _p,m:messages.append(m))
        self.assertEqual(messages,['row-progress'])
        proposal=evidence[('source',0)][0]
        second={**proposal,'model':'different'}
        chosen=strict_vote([proposal,second],row['words'][0],0,5)
        self.assertEqual(chosen['word'],'GEL,BANA')
        self.assertEqual(len(chosen['timing_parts']),2)
        self.assertEqual(syllable_fill(chosen,2.),syllable_fill(chosen,2.9))
        from karaoke_timing import ass_word_tags
        self.assertIn(r'{\k150}\h',ass_word_tags({'text':'GEL,BANA','start':1.,'end':4.,'words':[chosen]}))
        stale={**chosen,'end':5.};self.assertEqual(syllable_pieces(stale),[])

    def test_complete_existing_review_uses_supplied_evidence_without_model_download(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'audio.wav';sf.write(path,np.sin(np.arange(48000)*.04)*.05,16000)
            rows=[{'id':'a','text':'SON','start':1.,'end':2.,'words':[word()]}]
            with patch('karaoke_automatic_recovery.installed',return_value=False),patch(
                    'karaoke_automatic_recovery.collect_pass') as infer:
                report=recover_automatic_alignment(path,None,rows,evidence={('a',0):[
                    observation(),observation('two')]})
            infer.assert_not_called()
        self.assertEqual(report['automatic_recovery_strict_words'],1)
        self.assertEqual(report['automatic_recovery_remaining_words'],0)
        self.assertFalse(rows[0]['words'][0]['needs_review'])

    def test_agreeing_forced_models_cannot_certify_digital_silence(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'silent.wav';sf.write(path,np.zeros(48000),16000)
            rows=[{'id':'a','text':'SON','start':1.,'end':2.,'words':[word()]}]
            with patch('karaoke_automatic_recovery.installed',return_value=False):
                report=recover_automatic_alignment(path,None,rows,evidence={('a',0):[
                    observation(),observation('two')]})
        self.assertTrue(rows[0]['words'][0]['needs_review'])
        self.assertEqual(report['automatic_recovery_remaining_words'],1)

    def test_manual_locked_and_already_verified_data_are_untouched(self):
        rows=[{'id':'manual','text':'SON','start':1.,'end':2.,'words':[{**word(),'timing_source':'manual'}]},
              {'id':'locked','text':'SON','start':3.,'end':4.,'locked':True,'words':[word(start=3.,end=4.)]}]
        before=copy.deepcopy(rows)
        self.assertEqual(targets(rows),[])
        report=recover_automatic_alignment('missing.wav',None,rows)
        self.assertEqual(rows,before);self.assertEqual(report['automatic_recovery_initial_words'],0)

    def test_manual_row_padding_and_audit_coverage_survive_other_row_repair(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'audio.wav';sf.write(path,np.sin(np.arange(96000)*.04)*.05,16000)
            manual={'id':'manual','text':'SON','start':.5,'end':2.5,'words':[
                {**word(pending=False),'timing_source':'manual'}]}
            rows=[copy.deepcopy(manual),{'id':'auto','text':'SON','start':3.,'end':4.,'words':[
                word(start=3.,end=4.)]}]
            with patch('karaoke_automatic_recovery.installed',return_value=False):
                report=recover_automatic_alignment(path,None,rows,evidence={('auto',0):[
                    observation(start=3.,end=4.),observation('two',start=3.,end=4.)]})
        self.assertEqual(rows[0],manual)
        self.assertEqual(report['automatic_recovery_verified_keys'],[['auto',0]])

    def test_repeat_estimate_or_old_repeat_proof_is_not_a_fresh_reference(self):
        for kind in ('estimated','repeat_inferred','ctc'):
            w=word(pending=False);w['timing_source']=kind
            w['timing_reference']={'method':'acoustic_repeat_supported_ctc','acoustically_verified':True}
            self.assertFalse(proven(w,[]))
        self.assertTrue(proven({**word(pending=False),'timing_source':'manual'},[]))

    def test_missing_models_keep_the_warning_and_never_invent_a_span(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'audio.wav';sf.write(path,np.zeros(48000),16000)
            w=word(start=0.,end=0.);row={'id':'a','text':'SON','start':1.,'end':2.,'words':[w]}
            with patch('karaoke_automatic_recovery.installed',return_value=False):
                report=recover_automatic_alignment(path,None,[row])
        self.assertTrue(w['needs_review']);self.assertEqual(row['words'][0]['start'],0.)
        self.assertEqual(report['automatic_recovery_remaining_words'],1)

    def test_cancellation_propagates_without_partial_commit(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'audio.wav';sf.write(path,np.zeros(48000),16000)
            rows=[{'id':'a','text':'SON','start':1.,'end':2.,'words':[word()]}];before=copy.deepcopy(rows)
            with patch('karaoke_automatic_recovery.installed',return_value=True),patch(
                    'karaoke_automatic_recovery.collect_pass',side_effect=TaskCancelled('stop')):
                with self.assertRaises(TaskCancelled):checked_refinement(rows,3,'automatic',lambda c:
                    recover_automatic_alignment(path,None,c),{})
        self.assertEqual(rows,before)

    def test_budget_exhaustion_and_absent_negatives_cannot_confirm_a_match(self):
        class Matcher:
            calls=0;budget=1
            def distance(self,*_args):self.calls+=1;return .01
        target={'label':'son','start':1.,'end':2.}
        references=[{'label':'son','start':3.,'end':4.},{'label':'other','start':5.,'end':6.}]
        self.assertIsNone(contrast(Matcher(),target,references))

    def test_phrase_transfer_requires_ctc_witness_and_real_negative_comparison(self):
        class Matcher:
            calls=0;budget=1000
            def distance(self,a,b,phrase=False,path=False):
                self.calls+=1;score=.05 if a['label']==b['label'] else .4
                if not path:return score
                alignment=np.column_stack((np.arange(305),np.arange(305)))
                return score,alignment,a['start']-.15,b['start']-.15
        def row(identity,start,text,pending=False):
            return {'id':identity,'text':text,'start':start,'end':start+2.,'words':[
                word(t,start+j,start+j+1,pending) for j,t in enumerate(text.split())]}
        rows=[row('target',1.,'GEL BANA',True),row('reference',10.,'GEL BANA'),row('negative',20.,'YAR BENIM')]
        verified={(1,0),(1,1),(2,0),(2,1)}
        proposals=[observation('one',word='BANA',start=2.,end=3.,probability=.4),
                   observation('two',word='BANA',start=2.,end=3.,probability=.4)]
        chosen=phrase_repair(rows,0,1,verified,Matcher(),proposals,2.,5.)
        self.assertIsNotNone(chosen);self.assertEqual((chosen['start'],chosen['end']),(2.,3.))
        self.assertFalse(chosen['needs_review'])
        self.assertIsNone(phrase_repair(rows,0,1,{(1,0),(1,1)},Matcher(),proposals,2.,5.))
