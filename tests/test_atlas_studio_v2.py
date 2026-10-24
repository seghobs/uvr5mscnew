import unittest
import json
from pathlib import Path
import numpy as np
from atlas_studio import PRESET_V2, PRESET, combine, validate_models, inference_passes, transform_audio, run_atlas_studio
from atlas_band_ensemble import validate_frequency_weights
import tempfile
from types import SimpleNamespace
import soundfile as sf


class AtlasV2Tests(unittest.TestCase):
    def test_pair_preserves_source_with_disagreeing_experts(self):
        rng = np.random.default_rng(17)
        source = rng.normal(0, .2, (22050, 2))
        estimates = [rng.normal(0, .1, source.shape) for _ in range(4)]
        # Fixed arithmetic fixture remains independent of fitted production weights.
        fixture={**PRESET_V2,'models':[{**m,'weight':w,'estimate':kind}
            for m,w,kind in zip([*PRESET_V2['models'],PRESET_V2['models'][0]],[.55,.15,.1,.2],['vocal','vocal','vocal','inst'])]}
        fixture.pop('frequency_weights',None)
        vocals, instrumental = combine(source, estimates, fixture)
        np.testing.assert_allclose(vocals + instrumental, source, atol=1e-15)
        expected = .55*estimates[0]+.15*estimates[1]+.1*estimates[2]+.2*(source-estimates[3])
        np.testing.assert_allclose(vocals, expected)

    def test_production_preset_has_valid_unique_experts(self):
        models=PRESET_V2['models']
        self.assertEqual(len(models),3)
        self.assertEqual([m['model_key'] for m in models],[m['model_key'] for m in PRESET['models']])
        validate_frequency_weights(PRESET_V2['frequency_weights'],len(models))
        self.assertNotIn('frequency_weights',PRESET)
        self.assertEqual(len({m['model_key'] for m in models}),len(models))
        source=np.ones((20,2))
        vocal,instrumental=combine(source,[source*.1]*len(models),PRESET_V2)
        np.testing.assert_allclose(vocal+instrumental,source)

    def test_fallback_blend_retains_atlas_studio_as_its_anchor(self):
        self.assertEqual([m['weight'] for m in PRESET['models']],[.5,.25,.25])
        self.assertEqual([m['weight'] for m in PRESET_V2['models']],[.55,.25,.2])
        self.assertEqual(PRESET_V2['target'],'instrumental')
        self.assertTrue(all(abs(a['weight']-b['weight'])<=.050000001 for a,b in zip(PRESET['models'],PRESET_V2['models'])))
        self.assertEqual(inference_passes(PRESET_V2),[{'transform':'identity','weight':1.}])
        self.assertNotIn('residual_cleanup',PRESET)
        self.assertNotIn('residual_cleanup',PRESET_V2)

    def test_reference_report_describes_current_recipe_without_universal_claims(self):
        report=json.loads((Path(__file__).resolve().parents[1]/PRESET_V2['validation']['report']).read_text(encoding='utf8'))
        self.assertEqual(report['selected_preset'],PRESET_V2)
        self.assertFalse(report['isolated_reference_stems_available'])
        self.assertFalse(report['zero_leakage_verified'])
        self.assertIsNone(report['true_instrumental_sdr_db'])
        self.assertEqual(report['distinct_separation_models'],3)
        self.assertEqual(report['full_inference_passes'],3)
        self.assertFalse(report['secondary_vocal_subtraction'])
        self.assertFalse(report['true_music_fidelity_improvement_verified'])
        self.assertTrue(report['accepted'])
        self.assertTrue(all(report['checks'].values()))

    def test_v1_and_v2_share_models_but_reject_old_thirteen_model_requests(self):
        validate_models(PRESET['models'],PRESET_V2)
        with self.assertRaises(ValueError):validate_models(PRESET['models']*4+[PRESET['models'][0]],PRESET_V2)

    def test_transforms_are_exactly_self_inverse_and_do_not_shift_samples(self):
        wave=np.random.default_rng(5).normal(size=(321,2))
        for name in ('identity','swap_channels','invert_polarity'):
            np.testing.assert_array_equal(transform_audio(transform_audio(wave,name),name),wave)
        self.assertEqual(inference_passes(PRESET),[{'transform':'identity','weight':1.}])

    def test_invalid_transform_recipes_are_rejected(self):
        for passes in ([],[{'transform':'reverse','weight':1.}],
                       [{'transform':'identity','weight':.5}],
                       [{'transform':'identity','weight':1.},{'transform':'identity','weight':1.}]):
            with self.assertRaises(ValueError):inference_passes({**PRESET_V2,'inference_passes':passes})

    def test_transform_pipeline_keeps_time_stereo_and_source_sum(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);source=root/'input.wav'
            wave=np.random.default_rng(7).normal(0,.03,(1200,2))
            sf.write(source,wave,44100,subtype='FLOAT')
            calls=[]
            def separate(audio,key,*args,**kwargs):
                data,rate=sf.read(audio,always_2d=True)
                calls.append((key,Path(audio).stem))
                # A reversible separator must give the exact V1 result even
                # after polarity/channel augmentation and inverse transforms.
                paths=[]
                for kind,fraction in [('Vocals',.4),('Instrumental',.6)]:
                    path=Path(kwargs['work_dir'])/f'({kind}).wav'
                    sf.write(path,data*fraction,rate,subtype='FLOAT');paths.append(path)
                return paths
            core=SimpleNamespace(roformer_separator=separate,clear_gpu_and_ram_cache=lambda:None)
            fixture={**PRESET_V2,'inference_passes':[{'transform':'identity','weight':.5},
                     {'transform':'swap_channels','weight':.25},{'transform':'invert_polarity','weight':.25}]}
            fixture.pop('residual_cleanup',None)
            files=run_atlas_studio(core,source,fixture['models'],'wav',root,lambda p,m:None,preset=fixture)
            vocal,rate=sf.read(files[0],always_2d=True);inst,_=sf.read(files[1],always_2d=True)
            self.assertEqual(len(calls),9)
            self.assertEqual(len({key for key,_ in calls}),3)
            self.assertEqual(rate,44100);self.assertEqual(vocal.shape,wave.shape)
            np.testing.assert_allclose(vocal,wave*.4,atol=1e-8)
            np.testing.assert_allclose(vocal+inst,wave,atol=1e-8)
            self.assertFalse(list(root.glob('atlas_*')))

    def test_current_music_pipeline_has_no_secondary_subtraction(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);source=root/'input.wav'
            wave=np.random.default_rng(9).normal(0,.03,(1200,2))
            sf.write(source,wave,44100,subtype='FLOAT');calls=[]
            def separate(audio,key,*args,**kwargs):
                data,rate=sf.read(audio,always_2d=True);calls.append(key);paths=[]
                for label,fraction in [('Vocals',.4),('Instrumental',.6)]:
                    path=Path(kwargs['work_dir'])/f'({label}).wav'
                    sf.write(path,data*fraction,rate,subtype='FLOAT');paths.append(path)
                return paths
            core=SimpleNamespace(roformer_separator=separate,clear_gpu_and_ram_cache=lambda:None)
            outputs=run_atlas_studio(core,source,PRESET_V2['models'],'wav',root,lambda p,m:None,preset=PRESET_V2)
            instrumental,_=sf.read(outputs[1],always_2d=True)
            self.assertEqual(calls,[m['model_key'] for m in PRESET_V2['models']])
            np.testing.assert_allclose(instrumental,wave*.6,atol=1e-8)

    def test_invalid_weights_and_nan_are_rejected(self):
        x = np.zeros((20,2))
        estimates=[x]*len(PRESET_V2['models']);estimates[-1]=x+np.nan
        with self.assertRaises(ValueError): combine(x,estimates,PRESET_V2)
        bad = {**PRESET_V2, 'models':[{**m,'weight':0.5} for m in PRESET_V2['models']]}
        with self.assertRaises(ValueError): combine(x,[x]*len(bad['models']),bad)
