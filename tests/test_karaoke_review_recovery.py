import unittest
import copy
from unittest.mock import patch
import math
import numpy as np
from karaoke_review_recovery import repeat_boundary_candidate,repeat_features,repeated_audio_support

class RepeatBoundaryTests(unittest.TestCase):
    def test_requires_distinct_channels_and_discriminating_acoustic_match(self):
        original={'word':'YÜCE','start':1,'end':2,'probability':.25,'needs_review':True}
        candidates=[{**original,'start':1.01,'end':2.01,'probability':.4,'recovery_channel':channel} for channel in ['mix','right']]
        result=repeat_boundary_candidate(original,candidates,0,3,.10,.20)
        self.assertFalse(result['needs_review']);self.assertEqual(result['probability'],.4)
        self.assertIs(repeat_boundary_candidate(original,candidates,0,3,.18,.20),original)
        self.assertIs(repeat_boundary_candidate(original,candidates[:1]*2,0,3,.10,.20),original)
        self.assertIs(repeat_boundary_candidate(original,candidates,0,1.9,.10,.20),original)

    def test_large_boundary_changes_are_rejected(self):
        original={'word':'GEL','start':1,'end':2,'needs_review':True}
        proposals=[{'start':1.4,'end':2,'probability':.8,'recovery_channel':channel} for channel in ['left','right']]
        self.assertIs(repeat_boundary_candidate(original,proposals,0,3,.01,.40),original)

    def test_invalid_comparisons_cannot_confirm_a_word(self):
        original={'word':'GEL','start':1,'end':2,'needs_review':True}
        candidates=[{**original,'probability':.4,'recovery_channel':c} for c in ['mix','left']]
        for same,other in [(math.inf,.4),(.1,math.inf),(math.nan,.4),(.1,math.nan),(-.1,.4)]:
            self.assertIs(repeat_boundary_candidate(original,candidates,0,3,same,other),original)


class RowRecoveryBoundsTests(unittest.TestCase):
    def recover(self,words,word,start,end,probability=.9):
        from karaoke_review_recovery import recover_row_reviews
        rows=[{'id':'row','text':' '.join(w['word'] for w in words),'start':249.4,'end':251.,'words':copy.deepcopy(words)}]
        def proposal(path,selected,language,**kwargs):
            result=copy.deepcopy(selected)
            for row in result:
                for w in row['words']:
                    if w['word']==word:w.update(start=start,end=end,probability=probability,needs_review=False)
            return result
        with patch('karaoke_ctc.refine_ctc',side_effect=proposal):
            count=recover_row_reviews('song.wav',rows,language='kmr_mms')
        return count,rows[0]['words']

    def test_zero_placeholders_cannot_allow_previous_word_to_be_reused(self):
        words=[dict(word='DÎLANA',start=249.4,end=249.64,probability=.8),
               dict(word='NAV',start=245.78,end=245.78,needs_review=True),
               dict(word='WA',start=249.96,end=250.04,probability=.2,needs_review=True),
               dict(word='WEYLO',start=250.08,end=250.2,probability=.8)]
        count,result=self.recover(words,'WA',248.06,248.14)
        self.assertEqual(count,0);self.assertEqual(result,words)

    def test_zero_placeholder_cannot_hide_a_later_anchor(self):
        words=[dict(word='WA',start=249.4,end=249.6,probability=.8),
               dict(word='WEYLO',start=249.7,end=249.9,probability=.2,needs_review=True),
               dict(word='DÎSA',start=0,end=0,needs_review=True),
               dict(word='DÎLAN',start=250.2,end=250.5,probability=.8)]
        count,result=self.recover(words,'WEYLO',250.3,250.6)
        self.assertEqual(count,0);self.assertEqual(result,words)
        count,result=self.recover(words,'WEYLO',249.7,250.1)
        self.assertEqual(count,1);self.assertFalse(result[1]['needs_review'])
        count,result=self.recover(words,'WEYLO',249.7,250.1,probability=.49)
        self.assertEqual(count,0);self.assertTrue(result[1]['needs_review'])


class RepeatEvidenceTests(unittest.TestCase):
    def wave(self):
        t=np.arange(16000)/16000
        return (.2*np.sin(2*np.pi*220*t)+.1*np.sin(2*np.pi*613*t)).astype('float32')

    def words(self):
        return [dict(word=w,start=i,end=i+.5,probability=.9,needs_review=i==0)
                for i,w in enumerate(['YA','YA','BANA','YA'])]

    def test_silence_corruption_and_long_internal_gap_are_not_evidence(self):
        wave=self.wave()
        for clip in [np.zeros(16000),wave*1e-7,np.full(16000,np.nan),
                     np.concatenate([wave[:4000],np.zeros(4000),wave[:4000]])]:
            self.assertIsNone(repeat_features(clip,16000))
        features=repeat_features(wave,16000)
        self.assertIsNotNone(features);self.assertTrue(np.isfinite(features).all())
        np.testing.assert_allclose(np.linalg.norm(features,axis=0),1,atol=1e-6)

    def test_silent_target_never_enters_dtw(self):
        with patch('librosa.sequence.dtw') as dtw:
            self.assertEqual(repeated_audio_support(np.zeros((64000,2)),16000,0,self.words(),0,{}),(math.inf,math.inf))
            dtw.assert_not_called()

    def test_zero_feature_vector_is_rejected_even_if_audio_is_not_silent(self):
        with patch('librosa.feature.mfcc',return_value=np.zeros((16,10))):
            self.assertIsNone(repeat_features(self.wave(),16000))

    def test_parameter_error_is_isolated_and_later_references_are_used(self):
        from librosa.util.exceptions import ParameterError
        audio=np.tile(self.wave(),4);cache={}
        result=lambda score:(np.array([[score]]),np.array([[0,0]]))
        with patch('librosa.sequence.dtw',side_effect=[ParameterError('DTW cost matrix C has NaN values.'),result(.4),result(.1)]) as dtw:
            self.assertEqual(repeated_audio_support(audio,16000,0,self.words(),0,cache),(.1,.4))
            self.assertEqual(dtw.call_count,3)

    def test_nonfinite_dtw_result_and_feature_errors_leave_uncertainty(self):
        from librosa.util.exceptions import ParameterError
        audio=np.tile(self.wave(),4)
        with patch('librosa.sequence.dtw',return_value=(np.array([[np.nan]]),np.array([[0,0]]))):
            self.assertEqual(repeated_audio_support(audio,16000,0,self.words(),0,{}),(math.inf,math.inf))
        with patch('karaoke_review_recovery.repeat_features',side_effect=ParameterError('invalid audio')):
            cache={}
            self.assertEqual(repeated_audio_support(audio,16000,0,self.words(),0,cache),(math.inf,math.inf))
            self.assertIsNone(cache[(0,.5)])

