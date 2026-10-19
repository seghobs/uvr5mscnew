import copy
import math
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace

from karaoke_model_crosscheck import apply_crosscheck, original_for_stem, recover_model_reviews


class CrosscheckTests(unittest.TestCase):
    def test_kurdish_crosscheck_uses_kurdish_models_and_preserves_failed_words(self):
        with tempfile.TemporaryDirectory() as folder:
            original=Path(folder)/'original.wav';original.touch();rows=self.rows();before=copy.deepcopy(rows)
            with patch('soundfile.info',return_value=SimpleNamespace(duration=110)),patch('karaoke_ctc.refine_ctc',side_effect=RuntimeError('unavailable')) as model:
                report=recover_model_reviews('vocals.wav',original,rows,language='kmr')
            self.assertEqual([call.args[2] for call in model.call_args_list],['kmr_mms','kmr'])
            self.assertEqual(rows,before)
            self.assertEqual(report['dual_audio_repaired_words'],0)

    def test_optional_model_failure_preserves_timings_and_warnings(self):
        with tempfile.TemporaryDirectory() as folder:
            original=Path(folder)/'original.wav';original.touch();rows=self.rows();before=copy.deepcopy(rows)
            with patch('soundfile.info',return_value=SimpleNamespace(duration=110)),patch('karaoke_ctc.refine_ctc',side_effect=RuntimeError('model unavailable')) as model:
                report=recover_model_reviews('vocals.wav',original,rows)
            self.assertEqual(model.call_count,2)
            self.assertEqual(rows,before)
            self.assertEqual(len(report['model_crosscheck_errors']),2)
            self.assertEqual(report['dual_audio_repaired_words'],0)

    def rows(self):
        return [{'id':'r','text':'BEN BUGÜN GELDİM','start':100.,'end':103.,'words':[
            {'word':'BEN','start':100.,'end':100.4,'timing_source':'ctc','probability':.9},
            {'word':'BUGÜN','start':100.8,'end':101.2,'timing_source':'ctc','probability':.3,'needs_review':True},
            {'word':'GELDİM','start':101.6,'end':103.,'timing_source':'ctc','probability':.9}]}]

    def evidence(self):
        return {('r',1):[{'word':'BUGÜN','start':100.75,'end':101.25,'probability':.8,'audio_source':'vocals','model':'second'},
                         {'word':'BUGÜN','start':100.77,'end':101.27,'probability':.9,'audio_source':'original','model':'second'}]}

    def test_distinct_recordings_agree_and_only_target_is_changed(self):
        rows=self.rows();before=copy.deepcopy(rows)
        self.assertEqual(apply_crosscheck(rows,self.evidence(),110),[('r',1)])
        w=rows[0]['words'][1]
        self.assertAlmostEqual(w['start'],100.76);self.assertAlmostEqual(w['end'],101.26)
        self.assertEqual(w['probability'],.8)
        self.assertFalse(w['needs_review'])
        self.assertTrue(w['timing_reference']['acoustically_verified'])
        for i in (0,2):self.assertEqual(rows[0]['words'][i],before[0]['words'][i])

    def test_low_score_same_recording_disagreement_or_wrong_text_cannot_clear_review(self):
        for kind in ('low','same_audio','disagree','wrong_word','nan','failed_alignment'):
            rows=self.rows();before=copy.deepcopy(rows);e=self.evidence();w=e[('r',1)][1]
            if kind=='low':w['probability']=.499999
            if kind=='same_audio':w['audio_source']='vocals'
            if kind=='disagree':w['start']+=.2
            if kind=='wrong_word':w['word']='YARIN'
            if kind=='nan':w['probability']=math.nan
            if kind=='failed_alignment':w['needs_review']=True
            self.assertEqual(apply_crosscheck(rows,e,110),[],kind)
            self.assertEqual(rows,before,kind)

    def test_word_and_row_neighbours_are_hard_limits(self):
        for kind in ('word','row'):
            rows=self.rows();e=self.evidence()
            if kind=='word':rows[0]['words'][0]['end']=100.9
            else:rows.insert(0,{'id':'previous','text':'ÖNCE','start':99,'end':100.9,'words':[]})
            before=copy.deepcopy(rows)
            self.assertEqual(apply_crosscheck(rows,e,110),[])
            self.assertEqual(rows,before)

    def test_manual_requires_explicit_targeted_recheck_and_locked_always_stays(self):
        rows=self.rows();rows[0]['words'][1]['timing_source']='manual';before=copy.deepcopy(rows)
        self.assertEqual(apply_crosscheck(rows,self.evidence(),110),[])
        self.assertEqual(rows,before)
        self.assertEqual(apply_crosscheck(rows,self.evidence(),110,targets={('r',0)},allow_manual=True),[])
        self.assertEqual(apply_crosscheck(rows,self.evidence(),110,targets={('r',1)},allow_manual=True),[('r',1)])
        rows=self.rows();rows[0]['locked']=True;before=copy.deepcopy(rows)
        self.assertEqual(apply_crosscheck(rows,self.evidence(),110,allow_manual=True),[])
        self.assertEqual(rows,before)

    def test_original_mapping_is_exact_and_ambiguous_sources_are_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            a,b=Path(folder)/'a.wav',Path(folder)/'b.wav';a.touch();b.touch()
            records={'a':{'stems':['vocal.wav'],'separation_request':{'audio_path':str(a)}}}
            self.assertEqual(original_for_stem('vocal.wav',records),a.resolve())
            self.assertIsNone(original_for_stem('other-vocal.wav',records))
            records['b']={'stems':['vocal.wav'],'separation_request':{'kind':'single','request':{'audio_path':str(b)}}}
            self.assertIsNone(original_for_stem('vocal.wav',records))

    def test_different_original_edit_is_not_used(self):
        with tempfile.TemporaryDirectory() as folder:
            original=Path(folder)/'original.wav';original.touch();rows=self.rows();before=copy.deepcopy(rows)
            with patch('soundfile.info',side_effect=[SimpleNamespace(duration=110),SimpleNamespace(duration=111)]),patch('karaoke_ctc.refine_ctc') as model:
                report=recover_model_reviews('vocals.wav',original,rows)
            model.assert_not_called()
            self.assertEqual(rows,before)
            self.assertEqual(report['original_audio_crosscheck_skipped'],'different_audio_duration')

    def test_no_original_keeps_existing_timings_without_model_download(self):
        rows=self.rows();before=copy.deepcopy(rows)
        with patch('karaoke_ctc.refine_ctc') as model:report=recover_model_reviews('vocal.wav',None,rows)
        model.assert_not_called();self.assertEqual(rows,before)
        self.assertEqual(report['dual_audio_repaired_words'],0)
