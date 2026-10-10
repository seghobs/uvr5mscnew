import unittest
from unittest.mock import patch
import tempfile
import json
from pathlib import Path
import numpy as np
from tools.atlas_benchmark import fit_weights, metrics, fit, passes_pilot


class AtlasBenchmarkTests(unittest.TestCase):
    def test_acceptance_rejects_improvement_that_increases_content_deficit(self):
        old={'sdr_db':10.,'si_sdr_db':10.,'spectral_deficit':.1,'spectral_excess':.1}
        new={**old,'sdr_db':11.,'si_sdr_db':11.,'spectral_deficit':.09,'spectral_excess':.09}
        report={'test_sdr_delta_bootstrap_95pct':[.1,2.],
                'summary':{'test':{'v1':{'vocal':old,'instrumental':old},
                                   'v2_fitted':{'vocal':new,'instrumental':new}}}}
        self.assertTrue(passes_pilot(report))
        report['summary']['test']['v2_fitted']['instrumental']={**new,'spectral_deficit':.11}
        self.assertFalse(passes_pilot(report))
    def test_simplex_fit_cancels_opposite_errors_and_excludes_bad_expert(self):
        rng=np.random.default_rng(71)
        reference=rng.normal(size=2000)
        error=rng.normal(size=2000)
        candidates=np.stack([reference+error,reference-error,reference+4*error])
        best,_=fit_weights(candidates@candidates.T,candidates@reference,reference@reference,max_models=2)
        weights=np.array(best['weights'])
        self.assertAlmostEqual(float(weights.sum()),1.)
        self.assertTrue((weights>=0).all())
        np.testing.assert_allclose(weights@candidates,reference,atol=1e-5)

    def test_metrics_distinguish_missing_and_added_magnitude(self):
        t=np.arange(4410)/44100
        reference=np.column_stack([np.sin(2*np.pi*440*t)]*2)
        missing=metrics(reference,reference*.5)
        added=metrics(reference,reference*1.5)
        self.assertGreater(missing['spectral_deficit'],0)
        self.assertEqual(missing['spectral_excess'],0)
        self.assertGreater(added['spectral_excess'],0)
        self.assertEqual(added['spectral_deficit'],0)
        # Gain errors matter to ordinary SDR even when SI-SDR ignores them.
        self.assertAlmostEqual(missing['sdr_db'],6.020599913,places=6)

    def test_fit_rejects_nonfinite_statistics(self):
        with self.assertRaises(ValueError):
            fit_weights(np.full((5,5),np.nan),np.zeros(5),0.)

    def test_fitting_never_reads_held_out_audio(self):
        t=np.arange(4410)/44100
        vocal=np.column_stack([np.sin(2*np.pi*440*t)]*2)
        instrumental=np.column_stack([np.sin(2*np.pi*700*t)]*2)
        reference={'vocal':vocal,'instrumental':instrumental,'source':vocal+instrumental}
        candidates=np.stack([vocal+.4*instrumental,vocal,vocal-.1*instrumental,
                             vocal+.2*instrumental,vocal+.3*instrumental])
        def guarded_load(track):
            self.assertEqual(track['split'],'train')
            return reference,candidates
        with tempfile.TemporaryDirectory() as folder, \
                patch('tools.atlas_benchmark.WORK',Path(folder)), \
                patch('tools.atlas_benchmark.tracks',return_value=[{'split':'train'},{'split':'test'}]), \
                patch('tools.atlas_benchmark.load',side_effect=guarded_load), \
                patch('builtins.print'):
            fit()
            result=json.loads((Path(folder)/'frozen_fit.json').read_text(encoding='utf8'))
            self.assertFalse(result['test_used_for_fitting'])
            self.assertLess(result['selected_development_loss'],result['v1_development_loss'])
