import copy
import math
import tempfile
import unittest
from pathlib import Path

from karaoke_repeat_inference import infer_repeated_words, recover_from_song_repeats, token_key
from karaoke_timing import timing_issues, render_timing_issues


def row(identity, start, text='BEN SENİ ÇOK SEVDİM'):
    words=[dict(word=t,start=start+i*.8,end=start+i*.8+.35,timing_source='ctc',probability=.9,needs_review=False)
           for i,t in enumerate(text.split())]
    return dict(id=identity,text=text,start=start,end=words[-1]['end'],words=words)


def missing(word):
    word.update(start=0,end=0,timing_source='estimated',probability=None,needs_review=True)


class RepeatInferenceTests(unittest.TestCase):
    def test_reference_clock_is_not_copied_only_relative_duration(self):
        results=[]
        for reference_start in (1,100):
            rows=[row('reference',reference_start),row('target',200)]
            missing(rows[1]['words'][1])
            before=copy.deepcopy(rows)
            self.assertEqual(infer_repeated_words(rows,220,lambda a,b:.1),1)
            word=rows[1]['words'][1]
            self.assertAlmostEqual(word['end']-word['start'],.35)
            self.assertGreaterEqual(word['start'],rows[1]['words'][0]['end'])
            self.assertLessEqual(word['end'],rows[1]['words'][2]['start'])
            self.assertEqual(rows[0],before[0])
            results.append((word['start'],word['end']))
        self.assertAlmostEqual(results[0][0],results[1][0])
        self.assertAlmostEqual(results[0][1],results[1][1])

    def test_duration_cannot_be_squeezed_or_overlap_another_row(self):
        for case in ('tiny_gap','next_row'):
            rows=[row('reference',1,'BEN SENİ ÇOK SEVDİM'),row('target',20,'HEP SENİ ÇOK BEKLEDİM')]
            missing(rows[1]['words'][1])
            if case=='tiny_gap':rows[1]['words'][2]['start']=rows[1]['words'][0]['end']+.03
            else:rows.append(row('overlapping',20.3,'BAŞKA BİR SATIR'))
            before=copy.deepcopy(rows)
            self.assertEqual(infer_repeated_words(rows,30,lambda a,b:.1),0)
            self.assertEqual(rows,before)

    def test_matching_phrase_maps_local_tempo_without_changing_confirmed_words(self):
        rows=[row('reference',1),row('target',20)]
        for w in rows[1]['words']:
            w['start']=20+(w['start']-20)*1.1
            w['end']=20+(w['end']-20)*1.1
        rows[1]['end']=rows[1]['words'][-1]['end']
        missing(rows[1]['words'][1]);before=copy.deepcopy(rows)
        self.assertEqual(infer_repeated_words(rows,30,lambda a,b:.1),1)
        w=rows[1]['words'][1]
        self.assertAlmostEqual(w['start'],20.88)
        self.assertAlmostEqual(w['end'],21.265)
        self.assertEqual(w['timing_source'],'repeat_inferred')
        self.assertEqual(w['timing_reference']['method'],'matching_phrase_anchors')
        self.assertFalse(w['timing_reference']['acoustically_verified'])
        self.assertIsNone(w['probability'])
        self.assertEqual(rows[0],before[0])
        for j in (0,2,3):self.assertEqual(rows[1]['words'][j],before[1]['words'][j])
        self.assertFalse(timing_issues(rows));self.assertFalse(render_timing_issues(rows))
        saved=copy.deepcopy(rows)
        self.assertEqual(infer_repeated_words(rows,30,lambda a,b:.1),0)
        self.assertEqual(saved,rows)

    def test_same_word_in_different_phrase_is_bounded_and_marked_estimated(self):
        rows=[row('reference',1,'TU ZANÎBÎ ZALİM'),row('target',10,'TU KOR BİBÎ')]
        missing(rows[1]['words'][0])
        rows[1]['start']=rows[1]['words'][1]['start']
        self.assertEqual(infer_repeated_words(rows,20,lambda a,b:.1),1)
        w=rows[1]['words'][0]
        self.assertLess(w['start'],10.8)
        self.assertLessEqual(w['end'],10.8)
        self.assertEqual(rows[1]['start'],w['start'])
        self.assertEqual(w['timing_reference']['method'],'same_word_local_tempo')
        self.assertEqual(w['timing_reference']['row_ids'],['reference'])

    def test_lock_manual_silence_invalid_audio_and_no_references_preserved(self):
        for case in ('locked','manual','silence','nan','no_reference','inferred_reference','weak_reference'):
            rows=[row('reference',1),row('target',20)]
            missing(rows[1]['words'][1])
            if case=='locked':rows[1]['locked']=True
            if case=='manual':rows[1]['words'][1]['timing_source']='manual'
            if case=='no_reference':rows=rows[1:]
            if case=='inferred_reference':rows[0]['words'][1]['timing_source']='repeat_inferred'
            if case=='weak_reference':rows[0]['words'][1]['probability']=.4
            before=copy.deepcopy(rows)
            self.assertEqual(infer_repeated_words(rows,30,lambda a,b:0 if case=='silence' else math.nan if case=='nan' else .1),0,case)
            self.assertEqual(rows,before,case)

    def test_does_not_bridge_long_break_or_consecutive_missing_words(self):
        for case in ('break','consecutive'):
            rows=[row('reference',1),row('target',20)]
            missing(rows[1]['words'][1])
            if case=='break':rows[1]['words'][2]['start']+=3
            else:missing(rows[1]['words'][2])
            before=copy.deepcopy(rows)
            self.assertEqual(infer_repeated_words(rows,30,lambda a,b:.1),0)
            self.assertEqual(rows,before)

    def test_conflicting_phrase_references_are_not_averaged(self):
        rows=[row('first',1),row('second',10),row('target',20)]
        rows[1]['words'][1].update(start=10.4,end=10.6)
        missing(rows[2]['words'][1]);before=copy.deepcopy(rows)
        self.assertEqual(infer_repeated_words(rows,30,lambda a,b:.1),0)
        self.assertEqual(rows,before)

    def test_silent_reference_is_rejected_even_with_high_model_confidence(self):
        rows=[row('reference',1),row('target',20)]
        missing(rows[1]['words'][1]);before=copy.deepcopy(rows)
        self.assertEqual(infer_repeated_words(rows,30,lambda a,b:0. if b<10 else .1),0)
        self.assertEqual(rows,before)

    def test_audio_energy_gate_handles_silence_and_opposite_phase_stereo(self):
        import numpy as np
        import soundfile as sf
        rate=8000
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'test.wav'
            signal=np.sin(np.arange(rate*30)*2*np.pi*220/rate)*.1
            for sound,expected in [(np.zeros((rate*30,2)),0),(np.column_stack((signal,-signal)),1)]:
                sf.write(path,sound,rate)
                rows=[row('reference',1),row('target',20)];missing(rows[1]['words'][1])
                self.assertEqual(recover_from_song_repeats(path,rows),expected)

    def test_unicode_normalization_does_not_merge_distinct_letters(self):
        self.assertEqual(token_key('VÊ,'),token_key('ve\u0302'))
        self.assertEqual(token_key('Lİ'),token_key('li'))
        self.assertNotEqual(token_key('VÊ'),token_key('VE'))
        self.assertNotEqual(token_key('SIR'),token_key('SİR'))
