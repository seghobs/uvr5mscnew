import copy,unittest
from karaoke_alignment_benchmark import score_alignment


class BenchmarkTests(unittest.TestCase):
    def fixture(self):
        return {'reference_kind':'human_verified','audio_sha256':'recording-one','segments':[
            {'id':'first','words':[{'word':'AYNI','start':1.,'end':2.}]},
            {'id':'repeat','words':[{'word':'AYNI','start':10.,'end':12.}]}]}

    def test_repeated_words_are_scored_by_occurrence_not_text(self):
        gold=self.fixture();prediction=copy.deepcopy(gold);prediction['segments'][1]['words'][0].update(start=1,end=2)
        result=score_alignment(gold,prediction)
        self.assertEqual(result['onset_mae_seconds'],4.5);self.assertEqual(result['within_tolerance_fraction'],.5)

    def test_missing_wrong_and_extra_words_cannot_inflate_accuracy(self):
        gold=self.fixture();prediction=copy.deepcopy(gold);prediction['segments'][0]['words']=[]
        prediction['segments'][1]['words'][0]['word']='FARKLI'
        result=score_alignment(gold,prediction)
        self.assertEqual(result['within_tolerance_fraction'],0);self.assertEqual(len(result['missing_words']),1)
        self.assertEqual(len(result['wrong_words']),1)

    def test_exact_fixture_success_is_not_a_universal_accuracy_guarantee(self):
        gold=self.fixture();result=score_alignment(gold,gold)
        self.assertEqual(result['within_tolerance_fraction'],1);self.assertFalse(result['accuracy_guaranteed'])
        gold['reference_kind']='acoustic_consensus'
        self.assertFalse(score_alignment(gold,gold)['human_accuracy_measured'])

    def test_wrong_recording_unknown_provenance_and_invalid_reference_are_rejected(self):
        for kind in ('hash','missing_hash','provenance','nan'):
            gold=self.fixture();prediction=copy.deepcopy(gold)
            if kind=='hash':prediction['audio_sha256']='other-version'
            if kind=='missing_hash':gold.pop('audio_sha256');prediction.pop('audio_sha256')
            if kind=='provenance':gold.pop('reference_kind')
            if kind=='nan':gold['segments'][0]['words'][0]['start']=float('nan')
            with self.assertRaises(ValueError):score_alignment(gold,prediction)
