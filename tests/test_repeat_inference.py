import copy
import math
import tempfile
import unittest
from pathlib import Path

from karaoke_repeat_inference import infer_repeated_words, infer_repeated_runs, recover_from_song_repeats, token_key, measured
from karaoke_timing import timing_issues, render_timing_issues


def row(identity, start, text='BEN SENİ ÇOK SEVDİM'):
    words=[dict(word=t,start=start+i*.8,end=start+i*.8+.35,timing_source='ctc',probability=.9,needs_review=False)
           for i,t in enumerate(text.split())]
    return dict(id=identity,text=text,start=start,end=words[-1]['end'],words=words)


def missing(word):
    word.update(start=0,end=0,timing_source='estimated',probability=None,needs_review=True)


class RepeatInferenceTests(unittest.TestCase):
    def test_unbound_single_word_uses_agreeing_phrase_donors_and_ignores_outlier(self):
        rows=[row('a',1,'AYRILIK KOLAY MI SENİN YANINDA'),row('b',10,'AYRILIK KOLAY MI SENİN YANINDA'),
              row('outlier',20,'AYRILIK KOLAY MI SENİN YANINDA'),row('target',30,'AYRILIK KOLAY MI SENİN YANINDA')]
        rows[2]['words'][2]['end']+=.3
        missing(rows[-1]['words'][2])
        self.assertEqual(infer_repeated_runs(rows,40,lambda a,b:.1),1)
        result=rows[-1]['words'][2]
        self.assertEqual(result['timing_source'],'repeat_inferred')
        self.assertFalse(result['timing_reference']['acoustically_verified'])
        self.assertEqual(set(result['timing_reference']['row_ids']),{'a','b'})
        self.assertFalse(timing_issues(rows))

    def test_independent_recognition_proof_remains_measured_after_endpoint_repair(self):
        w=row('a',1)['words'][0];w['probability']=.35
        self.assertFalse(measured(w))
        proof={'method':'recognition_supported_ctc_consensus','acoustically_verified':True,
               'phonetic_evidence':[{},{}],'lexical_evidence':[{}]}
        w['timing_reference']={'method':'vocal_sustain_endpoint','previous_reference':proof}
        self.assertTrue(measured(w))
        w['timing_source']='repeat_inferred'
        self.assertFalse(measured(w),'estimated timings cannot become measured donors')

    def test_adjacent_run_requires_two_measured_agreeing_donors(self):
        rows=[row('a',1,'BEN SENİ ÇOK AMA ÇOK SEVDİM'),row('b',10,'BEN SENİ ÇOK AMA ÇOK SEVDİM'),
              row('target',20,'BEN SENİ ÇOK AMA ÇOK SEVDİM')]
        for w in rows[-1]['words'][2:4]:missing(w)
        before=copy.deepcopy(rows)
        self.assertEqual(infer_repeated_runs(rows,30,lambda a,b:.1),2)
        self.assertEqual(rows[:2],before[:2])
        for w in rows[-1]['words'][2:4]:
            self.assertEqual(w['timing_source'],'repeat_inferred')
            self.assertIsNone(w['probability'])
            self.assertFalse(w['timing_reference']['acoustically_verified'])
        self.assertFalse(timing_issues(rows))
        for variant in ('one_donor','silence','locked','manual','disagree'):
            trial=copy.deepcopy(before)
            if variant=='one_donor':trial.pop(0)
            if variant=='locked':trial[-1]['locked']=True
            if variant=='manual':trial[-1]['words'][2]['timing_source']='manual'
            if variant=='disagree':trial[0]['words'][2]['end']+=.3
            snapshot=copy.deepcopy(trial)
            self.assertEqual(infer_repeated_runs(trial,30,lambda a,b:0 if variant=='silence' else .1),0,variant)
            self.assertEqual(trial,snapshot)

    def test_duration_only_keeps_reference_length_when_target_tempo_changes(self):
        rows=[row('reference',1),row('target',20)]
        for w in rows[1]['words']:
            w['start']=20+(w['start']-20)*1.15;w['end']=20+(w['end']-20)*1.15
        rows[1]['end']=rows[1]['words'][-1]['end']
        rows[1]['words'][1].update(needs_review=True,probability=.3)
        self.assertEqual(infer_repeated_words(rows,30,lambda a,b:.1,duration_only=True),1)
        self.assertAlmostEqual(rows[1]['words'][1]['end']-rows[1]['words'][1]['start'],.35)

    def test_long_sung_word_can_fit_own_gap_without_copying_reference_clock(self):
        rows=[]
        for identity,spans in [('reference',[(1,1.6),(1.7,2.98),(3.16,3.56)]),
                               ('target',[(100,100.6),(100.8,101.9),(102.26,102.66)])]:
            words=[{'word':t,'start':a,'end':b,'probability':.9,'timing_source':'ctc','needs_review':False}
                   for t,(a,b) in zip(['AYRILIK','TRENİ','GELİP'],spans)]
            rows.append({'id':identity,'text':'AYRILIK TRENİ GELİP','start':spans[0][0],'end':spans[-1][1],'words':words})
        rows[1]['words'][1].update(probability=.3,needs_review=True)
        self.assertEqual(infer_repeated_words(rows,110,lambda a,b:.1,duration_only=True),1)
        w=rows[1]['words'][1]
        self.assertAlmostEqual(w['end']-w['start'],1.28)
        self.assertTrue(100.6<=w['start']<w['end']<=102.26)
        self.assertFalse(timing_issues(rows))

    def test_duration_only_does_not_copy_reference_placement_in_phrase(self):
        results=[]
        for shift in (0,.2):
            rows=[row('reference',1),row('target',20)]
            rows[0]['words'][1]['start']+=shift;rows[0]['words'][1]['end']+=shift
            rows[1]['words'][1].update(start=20.9,end=21.1,needs_review=True,probability=.3)
            self.assertEqual(infer_repeated_words(rows,30,lambda a,b:.1,duration_only=True),1)
            w=rows[1]['words'][1]
            self.assertAlmostEqual(w['end']-w['start'],.35)
            self.assertTrue(w['timing_reference']['duration_only'])
            results.append((w['start'],w['end']))
        self.assertEqual(results[0],results[1])

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
