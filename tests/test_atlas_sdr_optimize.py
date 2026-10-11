import unittest
from tools.atlas_sdr_optimize import eligible,summary
from tools.atlas_sdr_validate import passes_validation


class OptimizationAcceptanceTests(unittest.TestCase):
    def test_sdr_gain_cannot_hide_stem_content_regression(self):
        metrics={'sdr_db':12.,'si_sdr_db':11.,'spectral_deficit':.04,'spectral_excess':.01}
        baseline={s:dict(metrics) for s in ('vocal','instrumental')}
        candidate={s:{**metrics,'sdr_db':12.2,'si_sdr_db':11.1} for s in baseline}
        self.assertTrue(eligible(candidate,baseline))
        for stem in baseline:
            for key in ('spectral_deficit','spectral_excess'):
                bad={s:dict(candidate[s]) for s in candidate};bad[stem][key]+=.001
                self.assertFalse(eligible(bad,baseline))
            bad={s:dict(candidate[s]) for s in candidate};bad[stem]['si_sdr_db']=10.
            self.assertFalse(eligible(bad,baseline))

    def test_unchanged_or_invalid_score_cannot_pass(self):
        baseline={s:{'sdr_db':12.,'si_sdr_db':11.,'spectral_deficit':.04,'spectral_excess':.01} for s in ('vocal','instrumental')}
        self.assertFalse(eligible(baseline,baseline))
        bad={s:{**baseline[s],'sdr_db':float('nan')} for s in baseline}
        self.assertFalse(eligible(bad,baseline))

    def test_summaries_keep_stems_separate(self):
        result=summary([{'vocal':{'sdr_db':10.},'instrumental':{'sdr_db':20.}},
                        {'vocal':{'sdr_db':14.},'instrumental':{'sdr_db':22.}}])
        self.assertEqual(result['vocal']['sdr_db'],12.)
        self.assertEqual(result['instrumental']['sdr_db'],21.)

    def test_validation_requires_positive_confidence_interval(self):
        baseline={s:{'sdr_db':12.,'si_sdr_db':11.,'spectral_deficit':.04,'spectral_excess':.01} for s in ('vocal','instrumental')}
        candidate={s:{**baseline[s],'sdr_db':12.1} for s in baseline}
        scores={'current':baseline,'candidate':candidate}
        self.assertFalse(passes_validation(scores,[-.01,.2]))
        self.assertTrue(passes_validation(scores,[.01,.2]))
