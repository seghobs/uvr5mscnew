import tempfile
from pathlib import Path
from types import SimpleNamespace
import unittest
import numpy as np
import soundfile as sf
from atlas_studio import PRESET,run_atlas_studio,validate_models
from karaoke_residual import correction_activity,corrected_instrumental


class ResidualTests(unittest.TestCase):
    def test_instrument_only_and_silence_are_preserved_exactly(self):
        source=np.random.default_rng(1).normal(0,.1,(10000,2))
        residual=np.ones_like(source)*.3
        for voice in (np.zeros_like(source),source*.001):
            result=corrected_instrumental(source,residual,source,voice,44100)
            np.testing.assert_array_equal(result,source)
        zeros=np.zeros_like(source)
        np.testing.assert_array_equal(corrected_instrumental(zeros,residual,zeros,zeros,44100),zeros)

    def test_correction_changes_no_stereo_timing_or_independent_gain(self):
        source=np.random.default_rng(3).normal(0,.1,(8000,2));residual=source*.02
        result=corrected_instrumental(source,residual,source,source*.5,44100)
        np.testing.assert_allclose(result,source-residual,atol=1e-16)

    def test_activity_is_smooth_and_bounded(self):
        source=np.ones((44100,2));voice=np.zeros_like(source);voice[18000:25000]=.5
        activity=correction_activity(source,voice,44100)
        self.assertTrue(np.all((activity>=0)&(activity<=1)))
        self.assertLess(float(np.max(np.abs(np.diff(activity)))),.001)

    def test_invalid_cleanup_fails_before_model_work(self):
        for config in ({'model_key':'unlisted fourth model','strength':1},
                       {'model_key':PRESET['models'][1]['model_key'],'strength':2},
                       {'model_key':PRESET['models'][1]['model_key'],'strength':1,'activity_floor_db':-5,'activity_full_db':-20}):
            with self.assertRaises(ValueError):validate_models(PRESET['models'],{**PRESET,'residual_cleanup':config})

    def test_reuses_one_existing_model_and_keeps_complementary_export(self):
        preset={**PRESET,'id':'atlas_studio_v2','residual_cleanup':{'model_key':PRESET['models'][1]['model_key'],
                'voice_reference_model_key':PRESET['models'][0]['model_key'],'strength':1.}}
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);wave=np.random.default_rng(4).normal(0,.03,(1200,2))
            source=root/'source.wav';sf.write(source,wave,44100,subtype='FLOAT');calls=[]
            def separate(path,key,*args,**kwargs):
                data,rate=sf.read(path,always_2d=True);calls.append(key);files=[]
                for name,fraction in [('Vocals',.4),('Instrumental',.6)]:
                    target=Path(kwargs['work_dir'])/f'({name}).wav'
                    sf.write(target,data*fraction,rate,subtype='FLOAT');files.append(target)
                return files
            core=SimpleNamespace(roformer_separator=separate,clear_gpu_and_ram_cache=lambda:None)
            files=run_atlas_studio(core,source,preset['models'],'wav',root,lambda p,m:None,preset=preset)
            v,rate=sf.read(files[0],always_2d=True);inst,_=sf.read(files[1],always_2d=True)
            self.assertEqual(len(calls),4);self.assertEqual(len(set(calls)),3)
            np.testing.assert_allclose(inst,wave*.36,atol=1e-8)
            np.testing.assert_allclose(v+inst,wave,atol=1e-8)
            self.assertFalse(list(root.glob('atlas_*')))


if __name__=='__main__':unittest.main()
