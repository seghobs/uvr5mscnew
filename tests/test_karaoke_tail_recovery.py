import copy
import unittest
import numpy as np
from karaoke_tail_recovery import infer_tail_from_repeats
from karaoke_ctc import normalize_fading_audio


class TailRecoveryTests(unittest.TestCase):
    def rows(self):
        text='DÖRT YANA SAVURSUN DİYE KOKUNU RÜZGARA VERDİM'
        words=[dict(word=w,start=10+i,end=10+i+.6,timing_source='ctc',needs_review=False,probability=.9)
               for i,w in enumerate(text.split())]
        source=dict(id='earlier',text=text,start=10,end=16.6,words=words)
        target=copy.deepcopy(source);target.update(id='ending',start=100,end=104.6)
        for i,w in enumerate(target['words']):
            if i<5:w.update(start=w['start']+90,end=w['end']+90)
            else:w.update(start=0,end=0,timing_source='estimated',needs_review=True,probability=None)
        return [source,target]

    def test_estimates_have_provenance_no_fake_confidence_and_preserve_text(self):
        rows=self.rows();before=copy.deepcopy(rows)
        self.assertEqual(infer_tail_from_repeats(rows,108),2)
        self.assertEqual(rows[0],before[0]);self.assertEqual(rows[1]['text'],before[1]['text'])
        self.assertEqual(rows[1]['words'][:5],before[1]['words'][:5])
        for i,w in enumerate(rows[1]['words'][5:],5):
            self.assertAlmostEqual(w['start'],100+i)
            self.assertIsNone(w['probability']);self.assertEqual(w['timing_source'],'repeat_inferred')
            self.assertEqual(w['timing_reference']['row_ids'],['earlier'])

    def test_locked_manual_internal_gap_and_no_matching_repeat_are_not_changed(self):
        for scenario in ('locked','manual','internal','different','no_reference','far_from_end'):
            rows=self.rows();duration=108
            if scenario=='locked':rows[-1]['locked']=True
            if scenario=='manual':rows[-1]['words'][-1].update(start=106,end=106.6,timing_source='manual',needs_review=False)
            if scenario=='internal':rows[-1]['words'][-1].update(start=106,end=106.6,timing_source='ctc',needs_review=False)
            if scenario=='different':rows[0]['text']='BAŞKA SÖZLER'
            if scenario=='no_reference':rows=rows[1:]
            if scenario=='far_from_end':duration=150
            before=copy.deepcopy(rows);self.assertEqual(infer_tail_from_repeats(rows,duration),0,scenario)
            self.assertEqual(rows,before)

    def test_conflicting_repetitions_and_beyond_file_times_are_rejected(self):
        rows=self.rows();alternative=copy.deepcopy(rows[0]);alternative['words'][-1]['start']+=1;alternative['words'][-1]['end']+=1
        rows.insert(1,alternative);before=copy.deepcopy(rows)
        self.assertEqual(infer_tail_from_repeats(rows,108),0);self.assertEqual(rows,before)
        rows=self.rows();before=copy.deepcopy(rows)
        self.assertEqual(infer_tail_from_repeats(rows,105),0);self.assertEqual(rows,before)

    def test_quiet_audio_analysis_gain_is_bounded_and_silence_remains_silent(self):
        wave=np.sin(np.arange(16000)*2*np.pi*200/16000).astype('float32')*.0001
        original=wave.copy();boosted=normalize_fading_audio(wave,16000)
        self.assertGreater(np.max(np.abs(boosted)),np.max(np.abs(wave)))
        self.assertLessEqual(np.max(np.abs(boosted)),50*np.max(np.abs(wave))+1e-7)
        np.testing.assert_array_equal(wave,original)
        np.testing.assert_array_equal(normalize_fading_audio(np.zeros(16000),16000),0)
