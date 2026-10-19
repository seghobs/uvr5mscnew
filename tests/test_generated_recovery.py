import copy
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from karaoke_generated_recovery import recover_music_repeat_prefixes
from karaoke_tail_recovery import infer_tail_from_repeats


class GeneratedRecoveryTests(unittest.TestCase):
    def test_only_corroborated_generated_suffix_is_archived(self):
        row={'id':'auto-repeat:x','text':'A A A B','start':10.,'end':25.,'words':[
            dict(word=t,start=a,end=b,probability=p,needs_review=p<.5,timing_source='ctc')
            for t,a,b,p in [('A',10,10.4,.9),('A',10.6,11,.9),('A',22,22.4,.3),('B',24,25,.3)]]}
        def infer(path,rows,*args,**kwargs):
            item=copy.deepcopy(rows[0]);count=len(item['words'])
            for i,w in enumerate(item['words']):
                w.update(start=10+i*.5,end=10.4+i*.5,probability=.8 if count<=3 else .2,needs_review=False)
            return [item]
        for locked,generated,good in [(False,True,True),(True,True,True),(False,False,True),(False,True,False)]:
            rows=[copy.deepcopy(row)];rows[0]['locked']=locked
            if not generated:rows[0]['id']='user-row'
            before=copy.deepcopy(rows)
            with tempfile.TemporaryDirectory() as folder:
                original=Path(folder)/'original.wav';original.touch()
                with patch('soundfile.info',return_value=SimpleNamespace(duration=30)),patch('karaoke_ctc.refine_ctc',side_effect=infer):
                    n=recover_music_repeat_prefixes('vocals.wav',original,rows,[[9,12]] if good else [[9,26]],[[0,30]])
            expected=not locked and generated and good
            self.assertEqual(n,int(expected))
            if expected:
                self.assertEqual(rows[0]['text'],'A A A')
                self.assertEqual(rows[0]['repeat_cleanup'][0]['row']['text'],before[0]['text'])
                self.assertTrue(all(w['probability']>=.5 for w in rows[0]['words']))
            else:self.assertEqual(rows,before)

    def test_tail_borrows_lengths_not_donor_offsets_or_gaps(self):
        def w(t,a,b,p=.9):return dict(word=t,start=a,end=b,probability=p,needs_review=p<.5,timing_source='ctc')
        for donor_start in (1.,40.):
            rows=[dict(id='ref',text='A B C D E',start=donor_start,end=donor_start+9,
                       words=[w('A',donor_start,donor_start+.3),w('B',donor_start+1,donor_start+1.3),
                              w('C',donor_start+2,donor_start+2.3),w('D',donor_start+5,donor_start+5.2),w('E',donor_start+8,donor_start+8.4)]),
                  dict(id='tail',text='A B C D E',start=100.,end=104.,words=[w('A',100,100.3),w('B',101,101.3),
                       w('C',102,102.3),w('D',102.6,102.9,.2),w('E',103.4,103.9,.2)])]
            self.assertEqual(infer_tail_from_repeats(rows,105,duration_only=True),2)
            for item,length in zip(rows[-1]['words'][3:],[.2,.4]):
                self.assertAlmostEqual(item['end']-item['start'],length)
                self.assertTrue(102.3<=item['start']<item['end']<=105)
                self.assertTrue(item['timing_reference']['duration_only'])
                self.assertIsNone(item['probability'])
            self.assertAlmostEqual(rows[-1]['words'][3]['start'],102.65)
            self.assertAlmostEqual(rows[-1]['words'][4]['start'],103.45)
