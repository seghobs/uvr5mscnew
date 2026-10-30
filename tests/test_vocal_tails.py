import copy
from pathlib import Path
import tempfile
import unittest

import numpy as np

from karaoke_vocal_tails import vocal_endpoint,recover_sustained_endings


class VocalTailTests(unittest.TestCase):
    def test_sustained_vowel_extends_to_real_quiet_gap(self):
        levels=np.zeros(200);levels[10:160]=.2
        self.assertAlmostEqual(vocal_endpoint(levels,0,.02,.2,2),3.2)

    def test_trailing_silence_is_not_part_of_a_held_word(self):
        levels=np.zeros(250);levels[10:100]=.2
        self.assertAlmostEqual(vocal_endpoint(levels,0,.02,.2,4),2)

    def test_unvoiced_consonant_cannot_truncate_later_syllables(self):
        levels=np.zeros(220);levels[10:60]=.2;levels[75:150]=.2
        self.assertIsNone(vocal_endpoint(levels,0,.02,.2,3))

    def test_no_quiet_boundary_no_extension(self):
        self.assertIsNone(vocal_endpoint(np.ones(200)*.2,0,.02,.2,2))
        self.assertIsNone(vocal_endpoint(np.zeros(200),0,.02,.2,2))

    def test_stereo_agreement_and_manual_protection(self):
        import soundfile as sf
        rate=8000;t=np.arange(rate*5)/rate
        wave=.2*np.sin(t*2*np.pi*220);wave[(t<.2)|(t>=3.2)]=0
        original=[{'id':'a','text':'SON','start':.2,'end':2.,'words':[
            {'word':'SON','start':.2,'end':2.,'timing_source':'ctc','needs_review':True}]},
            {'id':'b','text':'DEVAM','start':4.,'end':4.5,'words':[]}]
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'test.wav';sf.write(path,np.column_stack([wave,wave]),rate)
            evidence={('a',0):[{'word':'SON','start':.2,'end':3.2,'probability':.8,'model':model} for model in ('first','second')]}
            rows=copy.deepcopy(original);report=recover_sustained_endings(path,rows,endpoint_evidence=evidence)
            self.assertEqual(len(report['vocal_tail_repairs']),1)
            self.assertAlmostEqual(rows[0]['end'],3.2)
            self.assertTrue(rows[0]['words'][0]['needs_review'],'endpoint evidence does not certify lyrics')
            for kind in ('locked','manual','disagree'):
                rows=copy.deepcopy(original)
                if kind=='locked':rows[0]['locked']=True
                if kind=='manual':rows[0]['words'][0]['timing_source']='manual'
                if kind=='disagree':
                    other=wave.copy();other[t>=2.8]=0;sf.write(path,np.column_stack([wave,other]),rate)
                before=copy.deepcopy(rows)
                self.assertEqual(recover_sustained_endings(path,rows)['vocal_tail_repairs'],[])
                self.assertEqual(rows,before)

    def test_stereo_reverb_without_independent_phonetic_support_cannot_retime(self):
        import soundfile as sf
        rate=8000;t=np.arange(rate*5)/rate
        envelope=np.where(t<2.,.2,.2*np.exp(-(t-2.)*2))
        wave=envelope*np.sin(t*2*np.pi*220);wave[(t<.2)|(t>=3.4)]=0
        row={'id':'a','text':'SON','start':.2,'end':2.,'words':[{'word':'SON','start':.2,'end':2.,'timing_source':'ctc'}]}
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'reverb.wav';sf.write(path,np.column_stack([wave,wave]),rate)
            report=recover_sustained_endings(path,[row])
        self.assertEqual(row['words'][0]['end'],2.)
        self.assertEqual(report['vocal_tail_repairs'],[])
        self.assertTrue(report['vocal_tail_review_candidates'])
        self.assertTrue(row['words'][0]['needs_review'])

    def test_reverb_does_not_downgrade_corroborated_endpoint_or_clear_prior_review(self):
        import soundfile as sf
        rate=8000;t=np.arange(rate*5)/rate
        wave=np.where(t<2.,.2,.2*np.exp(-(t-2.)*2))*np.sin(t*2*np.pi*220)
        wave[(t<.2)|(t>=3.4)]=0
        evidence=[{'word':'SON','start':.2,'end':2.,'probability':.8,'model':model} for model in ('first','second')]
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'reverb.wav';sf.write(path,np.column_stack([wave,wave]),rate)
            for pending in (False,True):
                word={'word':'SON','start':.2,'end':2.,'timing_source':'ctc','needs_review':pending,
                      'timing_reference':{'method':'bounded_multimodel_ctc','acoustically_verified':True,'evidence':evidence}}
                row={'id':'a','text':'SON','start':.2,'end':2.,'words':[word]}
                report=recover_sustained_endings(path,[row])
                self.assertEqual(word['end'],2.)
                self.assertEqual(word['needs_review'],pending)
                self.assertEqual(report['vocal_tail_repairs'],[])
                self.assertEqual(report['vocal_tail_review_candidates'][0]['reason'],
                                 'phonetic_endpoint_preserved_unconfirmed_energy_tail')


if __name__=='__main__':unittest.main()
