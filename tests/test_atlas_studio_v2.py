import unittest
import json
from pathlib import Path
import numpy as np
from atlas_studio import PRESET_V2, PRESET, combine, validate_models


class AtlasV2Tests(unittest.TestCase):
    def test_pair_preserves_source_with_disagreeing_experts(self):
        rng = np.random.default_rng(17)
        source = rng.normal(0, .2, (22050, 2))
        estimates = [rng.normal(0, .1, source.shape) for _ in range(4)]
        # Fixed arithmetic fixture remains independent of fitted production weights.
        fixture={**PRESET_V2,'models':[{**m,'weight':w,'estimate':kind}
            for m,w,kind in zip(PRESET_V2['models'],[.55,.15,.1,.2],['vocal','vocal','vocal','inst'])]}
        fixture.pop('frequency_weights',None)
        vocals, instrumental = combine(source, estimates, fixture)
        np.testing.assert_allclose(vocals + instrumental, source, atol=1e-15)
        expected = .55*estimates[0]+.15*estimates[1]+.1*estimates[2]+.2*(source-estimates[3])
        np.testing.assert_allclose(vocals, expected)

    def test_production_preset_has_valid_unique_experts(self):
        models=PRESET_V2['models']
        self.assertGreaterEqual(len(models),4)
        self.assertLessEqual(len(models),6)
        self.assertEqual(len({m['model_key'] for m in models}),len(models))
        source=np.ones((20,2))
        vocal,instrumental=combine(source,[source*.1]*len(models),PRESET_V2)
        np.testing.assert_allclose(vocal+instrumental,source)

    def test_production_weights_match_frozen_reference_experiment(self):
        if PRESET_V2.get('frequency_weights') is not None:
            report=json.loads((Path(__file__).resolve().parents[1]/PRESET_V2['calibration']['report']).read_text(encoding='utf8'))
            from tools.atlas_refinement import accepted
            self.assertTrue(accepted(report))
            self.assertTrue(report['accepted'])
            self.assertEqual(PRESET_V2,report['recipe'])
            self.assertFalse(report['fit']['evaluation_used_for_fitting'])
            development=set(report['fit']['development_ids'])
            self.assertFalse(development & {t['id'] for t in report['manifest']['evaluation']})
            return
        report=json.loads((Path(__file__).resolve().parents[1]/'docs/atlas-studio-v2-benchmark.json').read_text(encoding='utf8'))
        from tools.atlas_benchmark import passes_pilot
        self.assertTrue(passes_pilot(report))
        expected=[{**report['manifest']['models'][i],'weight':report['fit']['weights'][i]}
                  for i in report['fit']['indices']]
        identities=lambda models:[(m['model_type'],m['model_key'],m['estimate'],m['weight']) for m in models]
        self.assertEqual(identities(PRESET_V2['models']),identities(expected))

    def test_v1_and_v2_models_cannot_be_interchanged(self):
        validate_models(PRESET_V2['models'], PRESET_V2)
        with self.assertRaises(ValueError): validate_models(PRESET['models'], PRESET_V2)

    def test_invalid_weights_and_nan_are_rejected(self):
        x = np.zeros((20,2))
        estimates=[x]*len(PRESET_V2['models']);estimates[-1]=x+np.nan
        with self.assertRaises(ValueError): combine(x,estimates,PRESET_V2)
        bad = {**PRESET_V2, 'models':[{**m,'weight':0.5} for m in PRESET_V2['models']]}
        with self.assertRaises(ValueError): combine(x,[x]*len(bad['models']),bad)
