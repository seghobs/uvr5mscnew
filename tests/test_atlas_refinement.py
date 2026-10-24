import unittest
import numpy as np
from tools.atlas_refinement import accepted,waveform_statistics
from atlas_studio import PRESET_V2,combine,validate_models
from atlas_band_ensemble import combine_frequency


class RefinementTests(unittest.TestCase):
    def test_exact_waveform_error_matches_real_inverse_transform(self):
        rng=np.random.default_rng(18);target=rng.normal(0,.1,(4097,2))
        candidates=[rng.normal(0,.1,target.shape) for _ in range(3)]
        anchors=[0,1000,22050]
        weights=rng.uniform(size=(3,3));weights/=weights.sum(axis=0,keepdims=True)
        gram,linear,constant=waveform_statistics(candidates,target,anchors)
        vocal,_=combine_frequency(target,candidates,{'anchors_hz':anchors,'weights':weights.tolist()})
        expected=np.sum((vocal-target)**2)/np.sum(target**2)
        w=weights.ravel()
        self.assertAlmostEqual(float(w@gram@w-2*linear@w+constant),float(expected),places=12)

    def report(self):
        good={'sdr_db':11.,'si_sdr_db':10.,'spectral_deficit':.1,'spectral_excess':.1}
        better={'sdr_db':11.3,'si_sdr_db':10.2,'spectral_deficit':.09,'spectral_excess':.09}
        return {'comparisons':{'v1':{'mean_sdr_delta_db':.3,'bootstrap_95pct':[.1,.5]},
            'current':{'mean_sdr_delta_db':.2,'bootstrap_95pct':[.05,.3]}},
            'summary':{'v1':{s:dict(good) for s in ('vocal','instrumental')},
                'current':{s:dict(good) for s in ('vocal','instrumental')},
                'refined':{s:dict(better) for s in ('vocal','instrumental')}}}

    def test_acceptance_requires_both_baselines_and_all_content_metrics(self):
        self.assertTrue(accepted(self.report()))
        for baseline in ('v1','current'):
            bad=self.report();bad['comparisons'][baseline]['mean_sdr_delta_db']=0
            self.assertFalse(accepted(bad))
            bad=self.report();bad['comparisons'][baseline]['bootstrap_95pct'][0]=-.01
            self.assertFalse(accepted(bad))
            for stem in ('vocal','instrumental'):
                for metric in ('spectral_deficit','spectral_excess'):
                    bad=self.report();bad['summary'][baseline][stem][metric]=.08
                    self.assertFalse(accepted(bad))
                bad=self.report();bad['summary'][baseline][stem]['si_sdr_db']=10.4
                self.assertFalse(accepted(bad))

    def test_positive_supported_dominance_is_separate_from_aspirational_gain_target(self):
        report=self.report()
        report['comparisons']['v1']={'mean_sdr_delta_db':.15,'bootstrap_95pct':[.05,.25]}
        report['comparisons']['current']={'mean_sdr_delta_db':.1,'bootstrap_95pct':[.02,.2]}
        self.assertTrue(accepted(report))

    def test_production_combiner_converts_instrumental_expert_before_frequency_mix(self):
        rng=np.random.default_rng(41);source=rng.normal(0,.1,(4103,2))
        estimates=[rng.normal(0,.1,source.shape) for _ in range(4)]
        spec={'anchors_hz':[0,1000,22050],'weights':[[.1,.2,.4],[.2,.3,.1],[.3,.2,.3],[.4,.3,.2]]}
        fixture={**PRESET_V2,'models':[{**m,'weight':.25} for m in [*PRESET_V2['models'],PRESET_V2['models'][0]]],'frequency_weights':spec}
        vocal,inst=combine(source,estimates,fixture)
        candidates=[source-e if m['estimate']=='inst' else e for e,m in zip(estimates,fixture['models'])]
        expected=combine_frequency(source,candidates,spec)
        np.testing.assert_allclose(vocal,expected[0],atol=1e-15)
        np.testing.assert_allclose(inst,expected[1],atol=1e-15)
        np.testing.assert_allclose(vocal+inst,source,atol=1e-15)

    def test_invalid_frequency_recipe_rejected_before_model_work(self):
        bad={**PRESET_V2,'frequency_weights':{'anchors_hz':[0,22050],'weights':[[1,1]]}}
        with self.assertRaises(ValueError):validate_models(PRESET_V2['models'],bad)

    def test_short_inputs_preserve_source(self):
        source=np.ones((20,2))*.1
        spec={'anchors_hz':[0,22050],'weights':[[1,1]]}
        vocal,inst=combine_frequency(source,[source*.2],spec)
        np.testing.assert_allclose(vocal,source*.2,atol=1e-15)
        np.testing.assert_allclose(vocal+inst,source,atol=1e-15)
