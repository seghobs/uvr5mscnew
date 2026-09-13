import copy
import unittest
from karaoke_anchored import verified_candidates, word_groups
from karaoke_timing import solo_windows


class VerificationTests(unittest.TestCase):
    def passes(self):
        return [{'run_id':run,'words':[{'word':'ŞARKI!','start':5+run*.03,'end':5.7+run*.03,'probability':.9}]} for run in range(4)]

    def test_four_agree_preserve_original_anchor(self):
        candidates=self.passes();before=copy.deepcopy(candidates)
        self.assertEqual(verified_candidates(candidates),candidates[0]['words'])
        self.assertEqual(candidates,before)

    def test_one_hallucination_and_three_agreements_are_not_four(self):
        candidates=self.passes();candidates[3]['words']=[]
        self.assertEqual(verified_candidates(candidates),[])
        self.assertEqual(verified_candidates(candidates[:3]),[])
        candidates=self.passes();candidates[3]['words'][0]['word']='MÜZİK'
        self.assertEqual(verified_candidates(candidates),[])

    def test_same_words_at_another_chorus_do_not_confirm(self):
        candidates=self.passes();candidates[3]['words'][0].update(start=25,end=25.7)
        self.assertEqual(verified_candidates(candidates),[])

    def test_duplicate_pass_and_low_confidence_do_not_confirm(self):
        candidates=self.passes();candidates[3]['run_id']=2
        self.assertEqual(verified_candidates(candidates),[])
        candidates=self.passes();candidates[3]['words'][0]['probability']=.2
        self.assertEqual(verified_candidates(candidates),[])

    def test_repeated_words_need_separate_acoustic_occurrences(self):
        candidates=self.passes()
        for candidate in candidates:
            candidate['words'].append({**candidate['words'][0],'start':7,'end':7.5})
        self.assertEqual(len(verified_candidates(candidates)),2)

    def test_solo_intro_middle_outro_without_changing_lyrics(self):
        rows=[{'start':5,'end':10,'text':'Bir'},{'start':20,'end':25,'text':'İki'}]
        before=copy.deepcopy(rows)
        self.assertEqual(solo_windows(rows,35),[(0,5),(10.35,20),(27,35)])
        self.assertEqual(rows,before)
        self.assertEqual(solo_windows([{'start':1,'end':10,'text':'Bir'}],12),[])

    def test_rows_do_not_span_instrumental_break(self):
        words=[{'word':'Bir','start':1,'end':2},{'word':'İki','start':20,'end':21}]
        self.assertEqual(list(word_groups(words)),[[words[0]],[words[1]]])

    def test_synthetic_tone_does_not_load_whisper_or_invent_lyrics(self):
        import tempfile
        from pathlib import Path
        from unittest.mock import Mock
        import numpy as np
        import soundfile as sf
        from karaoke_deep_words import deep_words
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'instrumental.wav'
            t=np.arange(16000*3)/16000
            sf.write(path,.1*np.sin(2*np.pi*440*t),16000)
            loader=Mock(side_effect=AssertionError('No voice: Whisper must not run'))
            result=deep_words(path,0,3,loader,strict=True)
            self.assertEqual(result['candidates'],[])
            loader.assert_not_called()


if __name__=='__main__':unittest.main()
