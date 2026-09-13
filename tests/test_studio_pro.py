import sys
import unittest
import tempfile
import subprocess
from pathlib import Path
import numpy as np
import soundfile as sf
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from studio_pro import PRESET, validate_models, classify_stem, merge_command, run_studio_pro


class StudioProTests(unittest.TestCase):
    def test_api_routes_only_explicit_profile_to_new_pipeline(self):
        import ast, asyncio
        from fastapi import HTTPException, BackgroundTasks
        from types import SimpleNamespace
        tree=ast.parse(Path('api_modern.py').read_text(encoding='utf8'))
        node=next(n for n in tree.body if isinstance(n,ast.AsyncFunctionDef) and n.name=='start_ensemble')
        node.decorator_list=[]
        ns={'HTTPException':HTTPException,'BackgroundTasks':BackgroundTasks,
            'core':SimpleNamespace(output_format=['flac']), '_validate_audio_path':lambda p:None,
            '_create_task':lambda x:'job', 'run_ensemble_task':lambda *args:None}
        exec(compile(ast.Module(body=[node],type_ignores=[]),'<endpoint>','exec'),ns)
        payload={'audio_path':'input.wav','models':PRESET['models'],'out_format':'flac'}
        bg=BackgroundTasks();asyncio.run(ns['start_ensemble'](payload,bg))
        self.assertIsNone(bg.tasks[0].args[-1])
        payload['params']={'ensemble_profile':'studio_pro'}
        bg=BackgroundTasks();asyncio.run(ns['start_ensemble'](payload,bg))
        self.assertEqual(bg.tasks[0].args[-1],'studio_pro')
        payload['models']=PRESET['models'][:2]
        with self.assertRaises(HTTPException): asyncio.run(ns['start_ensemble'](payload,BackgroundTasks()))

    def test_exact_four_distinct_models_and_normalized_specialist_weights(self):
        validate_models(PRESET['models'])
        self.assertEqual(len({m['model_key'] for m in PRESET['models']}),4)
        for stem in ('vocal','inst'):
            self.assertAlmostEqual(sum(m[stem+'_weight'] for m in PRESET['models']),1)
        with self.assertRaises(ValueError): validate_models(PRESET['models'][:3])

    def test_stem_classification_ignores_input_name(self):
        self.assertEqual(classify_stem('My_vocals_song_(Instrumental)_model.flac'),'inst')
        self.assertEqual(classify_stem('inst_(Vocals)_model.flac'),'vocal')
        with self.assertRaises(ValueError): classify_stem('ambiguous.flac')

    def test_merge_keeps_quiet_stem_and_exact_length(self):
        with tempfile.TemporaryDirectory() as tmp:
            a,b,out=[Path(tmp)/n for n in ['a.wav','b.wav','out.wav']]
            sf.write(a,np.ones((4410,2))*.2,44100,subtype='FLOAT')
            sf.write(b,np.zeros((4410,2)),44100,subtype='FLOAT')
            subprocess.run(merge_command([a,b],[.25,.75],out,4410),check=True,capture_output=True)
            result,rate=sf.read(out)
            self.assertEqual(result.shape,(4410,2))
            self.assertTrue(np.allclose(result,.05,atol=1/32768))

    def test_pipeline_applies_settings_and_rejects_missing_stem(self):
        with tempfile.TemporaryDirectory() as tmp:
            source=Path(tmp)/'input.wav'
            sf.write(source,np.zeros((4410,2)),44100)
            calls=[]
            def separate(*args,**kwargs):
                calls.append(args)
                file=Path(tmp)/'sample_(Vocals)_model.flac'
                sf.write(file,np.zeros((16*44100,2)),44100)
                return [file]
            from types import SimpleNamespace
            core=SimpleNamespace(roformer_separator=separate,mdxc_separator=separate,clear_gpu_and_ram_cache=lambda:None)
            with self.assertRaisesRegex(ValueError,'birlikte'):
                run_studio_pro(core,source,PRESET['models'],'flac',tmp,lambda p,m:None)
            self.assertEqual(calls[0][2:10],('flac',256,False,8,1,1.0,0.0,''))

if __name__=='__main__': unittest.main()
