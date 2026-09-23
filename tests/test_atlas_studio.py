import ast
import asyncio
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
import numpy as np
import soundfile as sf
from atlas_studio import PRESET, combine, run_atlas_studio, validate_models, roformer_step_seconds


class AtlasStudioTests(unittest.TestCase):
    def test_overlap_uses_eighth_of_each_models_native_window(self):
        for hop, dim in [(441, 801), (441, 1101), (512, 1025)]:
            config = SimpleNamespace(audio=SimpleNamespace(hop_length=hop, sample_rate=44100),
                                     inference=SimpleNamespace(dim_t=dim))
            step = roformer_step_seconds(config, 8) * 44100
            self.assertAlmostEqual(step, hop*(dim-1)//8)
            self.assertAlmostEqual(1-step/(hop*(dim-1)), .875, places=5)

    def test_complementary_pair_preserves_source_even_when_models_disagree(self):
        rng = np.random.default_rng(42)
        source = rng.normal(0, .1, (12000, 2))
        estimates = [rng.normal(0, .05, source.shape) for _ in range(3)]
        v, i = combine(source, estimates)
        np.testing.assert_allclose(v + i, source, atol=1e-15)
        np.testing.assert_allclose(v, .5*estimates[0]+.25*estimates[1]+.25*(source-estimates[2]))

    def test_invalid_predictions_and_models_are_rejected(self):
        x = np.zeros((20, 2))
        for bad in ([x], [x, x, x[:2]], [x, x, x + np.nan]):
            with self.assertRaises(ValueError): combine(x, bad)
        for bad in ([], PRESET['models'][::-1], [None]):
            with self.assertRaises(ValueError): validate_models(bad)

    def test_pipeline_round_trip_duration_stereo_and_cleanup(self):
        for format in ('wav', 'flac'):
            with self.subTest(format=format), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                source = root/'input.wav'
                t = np.arange(4410)/44100
                wave = np.column_stack((.2*np.sin(2*np.pi*220*t), .1*np.cos(2*np.pi*440*t)))
                sf.write(source, wave, 44100, subtype='FLOAT')
                calls = []
                def separate(*args, **kwargs):
                    calls.append(args)
                    audio, rate = sf.read(args[0], always_2d=True)
                    files = []
                    for name, fraction in [('Vocals', .4), ('Instrumental', .6)]:
                        path = Path(kwargs['work_dir'])/f'sample_({name}).flac'
                        sf.write(path, audio*fraction, rate, subtype='PCM_24')
                        files.append(path)
                    return files
                core = SimpleNamespace(roformer_separator=separate, clear_gpu_and_ram_cache=lambda:None)
                files = run_atlas_studio(core, source, PRESET['models'], format, root, lambda p,m:None)
                v, rate = sf.read(files[0], always_2d=True)
                i, _ = sf.read(files[1], always_2d=True)
                self.assertEqual(v.shape, wave.shape)
                self.assertEqual(rate, 44100)
                np.testing.assert_allclose(v+i, wave, atol=3e-7)
                self.assertEqual(len(calls), 3)
                self.assertEqual(calls[0][2:10], ('wav',256,False,8,1,1.,0.,''))
                self.assertFalse(list(root.glob('atlas_*')))

    def test_failed_model_leaves_no_partial_exports(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); source = root/'input.wav'
            sf.write(source, np.zeros((100,2)), 44100)
            core = SimpleNamespace(roformer_separator=lambda *a,**k:[], clear_gpu_and_ram_cache=lambda:None)
            with self.assertRaisesRegex(ValueError, 'birlikte'):
                run_atlas_studio(core, source, PRESET['models'], 'wav', root, lambda p,m:None)
            self.assertEqual([p.name for p in root.iterdir()], ['input.wav'])

    def test_api_validates_profile_models_and_lossless_format_before_scheduling(self):
        from fastapi import BackgroundTasks, HTTPException
        tree = ast.parse(Path('api_modern.py').read_text(encoding='utf8'))
        node = next(n for n in tree.body if isinstance(n, ast.AsyncFunctionDef) and n.name == 'start_ensemble')
        node.decorator_list = []
        ns = dict(BackgroundTasks=BackgroundTasks, HTTPException=HTTPException,
            core=SimpleNamespace(output_format=['wav','flac','mp3']), _validate_audio_path=lambda p:None,
            _create_task=lambda p:'test', run_ensemble_task=lambda *a:None)
        exec(compile(ast.Module(body=[node], type_ignores=[]), '<endpoint>', 'exec'), ns)
        payload = dict(audio_path='input.wav', models=PRESET['models'], out_format='wav', params={'ensemble_profile':'atlas_studio'})
        bg = BackgroundTasks()
        asyncio.run(ns['start_ensemble'](payload, bg))
        self.assertEqual(bg.tasks[0].args[-1], 'atlas_studio')
        payload['out_format'] = 'mp3'
        with self.assertRaises(HTTPException): asyncio.run(ns['start_ensemble'](payload, BackgroundTasks()))


if __name__ == '__main__': unittest.main()
