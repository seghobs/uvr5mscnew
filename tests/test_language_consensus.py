import copy
import unittest
from unittest.mock import patch
import numpy as np
from karaoke_language_consensus import merge_language_alignment,corroborate_recovered_repeats


def word(text,start,end,p=.9,review=False,source='ctc'):
    return dict(word=text,start=start,end=end,probability=p,needs_review=review,timing_source=source)


class ConsensusTests(unittest.TestCase):
    def test_supplement_cannot_replace_primary_repetition_order(self):
        native=[dict(id='verse',text='EZ JI BO',start=48,end=48.7,
                     words=[word('EZ',48,48.2),word('JI',48.3,48.4),word('BO',48.5,48.7)]),
                dict(id='native-repeat',text='EZ JI BO',start=56,end=56.7,
                     words=[word('EZ',56,56.2),word('JI',56.3,56.4),word('BO',56.5,56.7)])]
        fallback=[dict(id='verse',text='EZ JI BO',start=40,end=51,
                       words=[word('EZ',40,40.2),word('JI',41.3,41.4),word('BO',44.5,44.7)]),
                  dict(id='false-repeat',text='YAR RADIZE LI',start=56,end=59,
                       words=[word('YAR',56,56.2),word('RADIZE',56.3,58.4),word('LI',58.5,58.7)])]
        result,n=merge_language_alignment(native,fallback,'fallback-model')
        self.assertEqual(n,0)
        self.assertEqual(result,native)

    def rows(self):
        return [dict(id='r',text='A B C',start=1,end=4,words=[word('A',1,2),word('B',0,0,None,True,'estimated'),word('C',3,4)])]

    def test_high_confidence_model_fills_gap_without_moving_confirmed_words(self):
        original=self.rows();other=copy.deepcopy(original)
        other[0]['words']=[word('A',.9,1.8),word('B',2.2,2.5),word('C',3.1,4.2)]
        result,n=merge_language_alignment(original,other,'kmr-model')
        self.assertEqual(n,1)
        self.assertEqual(result[0]['words'][0],original[0]['words'][0])
        self.assertEqual(result[0]['words'][2],original[0]['words'][2])
        self.assertFalse(result[0]['words'][1]['needs_review'])
        self.assertEqual(result[0]['words'][1]['timing_reference']['model'],'kmr-model')
        self.assertEqual(original,self.rows())

    def test_low_confidence_keeps_warning_and_cutoff_is_not_lowered(self):
        for p in [.0001,.09,.1,.49]:
            original=self.rows();other=copy.deepcopy(original)
            other[0]['words'][1]=word('B',2.2,2.5,p,True)
            result,n=merge_language_alignment(original,other,'kmr-model')
            self.assertEqual(n,int(p>=.1))
            self.assertTrue(result[0]['words'][1]['needs_review'])

    def test_invalid_overlapping_and_different_words_rejected(self):
        for candidate in [word('B',1.9,2.5),word('B',2.5,3.1),word('B',2.2,float('nan')),
                          word('B',2.2,22),word('X',2.2,2.5)]:
            original=self.rows();other=copy.deepcopy(original);other[0]['words'][1]=candidate
            self.assertEqual(merge_language_alignment(original,other,'kmr-model'),(original,0))

    def test_manual_locked_and_measured_weak_words_are_preserved(self):
        for mode in ['locked','manual','weak']:
            original=self.rows();other=copy.deepcopy(original)
            if mode=='locked':original[0]['locked']=True
            if mode=='manual':original[0]['words'][1]=word('B',2.1,2.4,.9,False,'manual')
            if mode=='weak':original[0]['words'][1]=word('B',2.1,2.4,.3,True)
            other[0]['words'][1]=word('B',2.2,2.5,.4,True)
            self.assertEqual(merge_language_alignment(original,other,'kmr-model'),(original,0))

    def test_repeat_audit_rejects_silence_and_preserves_uncertainty(self):
        rows=[]
        for i,text in enumerate(['JI','JI','JI','TU']):
            w=word(text,1+i*2,1.1+i*2)
            if i==0:w.update(needs_review=True,timing_reference={'method':'language_model_alignment'})
            rows.append(dict(id=str(i),text=text,start=w['start'],end=w['end'],words=[w]))
        original=copy.deepcopy(rows)
        for wave in [np.zeros((128000,2),dtype='float32'),np.full((128000,2),np.nan)]:
            with patch('soundfile.read',return_value=(wave,16000)),patch('librosa.sequence.dtw') as dtw:
                self.assertEqual(corroborate_recovered_repeats('fixture.wav',rows),0)
                dtw.assert_not_called()
            self.assertEqual(rows,original)

    def test_identical_wrong_word_audio_cannot_corroborate_a_repeat(self):
        t=np.arange(128000)/16000;wave=np.stack([.1*np.sin(2*np.pi*200*t)]*2,axis=1).astype('float32')
        rows=[]
        for i,text in enumerate(['JI','JI','JI','TU']):
            w=word(text,1+i*2,1.1+i*2)
            if i==0:w.update(needs_review=True,timing_reference={'method':'language_model_alignment'})
            rows.append(dict(id=str(i),text=text,start=w['start'],end=w['end'],words=[w]))
        with patch('soundfile.read',return_value=(wave,16000)):
            self.assertEqual(corroborate_recovered_repeats('fixture.wav',rows),0)
        self.assertTrue(rows[0]['words'][0]['needs_review'])


if __name__=='__main__':unittest.main()
