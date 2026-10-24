from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import shutil
import numpy as np
import soundfile as sf
from comparison_ensemble import PRESETS,validate_models,max_spectrum,run,attach_sw_vocal_pair


class ComparisonTests(unittest.TestCase):
    def test_clean_music_combines_three_routes_and_preserves_mixture(self):
        from comparison_ensemble import median_spectrum
        t=np.arange(8192)/44100
        mixture=np.column_stack([np.sin(t*440*2*np.pi)]*2).astype('float32')*.1
        np.testing.assert_allclose(median_spectrum([mixture*.2,mixture*.6,mixture*.9]),mixture*.6,atol=1e-6)
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);source=root/'source.wav'
            sf.write(source,mixture,44100,subtype='FLOAT')
            def separate(prepared,key,*args,work_dir,**kwargs):
                wave=mixture*.2 if 'SW 6 Stem' in key else mixture*.5
                tag='Vocals' if 'SW 6 Stem' in key else 'Instrumental'
                path=Path(work_dir)/f'source_({tag}).wav'
                sf.write(path,wave,44100,subtype='FLOAT');return [str(path)]
            def atlas(core,prepared,models,fmt,folder,progress,**kwargs):
                self.assertEqual(len(models),3)
                path=Path(folder)/'AtlasStudio_Instrumental_test.wav'
                sf.write(path,mixture*.6,44100,subtype='FLOAT');return [str(path)]
            def decode(command,**kwargs):
                shutil.copyfile(command[command.index('-i')+1],command[-1]);return SimpleNamespace(returncode=0)
            core=SimpleNamespace(roformer_separator=separate,clear_gpu_and_ram_cache=lambda:None)
            progress=[]
            with patch('comparison_ensemble.subprocess.run',side_effect=decode),patch('atlas_studio.run_atlas_studio',side_effect=atlas) as atlas_run:
                files=run(core,source,PRESETS['clean_music']['models'],'wav',root,lambda p,m:progress.append(p),'clean_music')
            atlas_run.assert_called_once()
            self.assertEqual(len(PRESETS['clean_music']['models']),7)
            vocal,_=sf.read(files[0]);inst,_=sf.read(files[1])
            np.testing.assert_allclose(inst,mixture*.6,atol=1e-6)
            np.testing.assert_allclose(vocal+inst,mixture,atol=1e-6)
            self.assertEqual(progress,sorted(progress))
            self.assertTrue(all(Path(p).name.startswith('CleanMusic_') for p in files))

    def test_six_head_runner_exports_vocals_and_full_accompaniment(self):
        mixture=np.ones((2,4000),dtype='float32')
        instance=SimpleNamespace(demix=lambda mix:{'vocals':mix*.2,'bass':mix*.3,'drums':mix*.1,'other':mix*.1})
        attach_sw_vocal_pair(instance)
        pair=instance.demix(mixture)
        np.testing.assert_allclose(pair['instrumental'],mixture*.8)
        self.assertEqual(instance.primary_stem_name,'vocals')

    def test_preset_rejects_different_models_and_lossy_format(self):
        for key,preset in PRESETS.items():
            with self.assertRaises(ValueError):validate_models(list(reversed(preset['models'])),key)
            with self.assertRaises(ValueError):validate_models(preset['models'],key,'mp3')

    def test_max_spec_preserves_larger_complex_bins(self):
        t=np.arange(44100)/44100
        wave=np.column_stack([np.sin(t*440*2*np.pi)]*2).astype('float32')*.1
        np.testing.assert_allclose(max_spectrum([wave*.5,wave]),wave,atol=1e-6)

    def test_sw_uses_mixture_minus_vocals_and_outputs_sum_to_source(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);source=root/'source_vocals.wav'
            t=np.arange(44100)/44100
            mixture=np.column_stack([np.sin(t*440*2*np.pi)]*2).astype('float32')*.1
            sf.write(source,mixture,44100,subtype='FLOAT')
            def separate(prepared,key,*args,work_dir,**kwargs):
                files=[]
                estimates={'vocals':mixture*.2,'other':mixture*.01,'bass':mixture*.3} if 'SW 6 Stem' in key else {'Instrumental':mixture*.6,'Vocals':mixture*.4}
                for tag,wave in estimates.items():
                    path=Path(work_dir)/f'source_vocals_({tag})_model.wav';sf.write(path,wave,44100,subtype='FLOAT');files.append(str(path))
                return files
            def decode(command,**kwargs):shutil.copyfile(source,command[-1]);return SimpleNamespace(returncode=0)
            core=SimpleNamespace(roformer_separator=separate,clear_gpu_and_ram_cache=lambda:None)
            with patch('comparison_ensemble.subprocess.run',side_effect=decode):
                files=run(core,source,PRESETS['lale_instrument']['models'],'wav',root,lambda *args:None,'lale_instrument')
            vocal,_=sf.read(files[0]);inst,_=sf.read(files[1])
            np.testing.assert_allclose(inst,mixture*.8,atol=1e-6)
            np.testing.assert_allclose(vocal+inst,mixture,atol=1e-6)
            self.assertTrue(all(Path(p).name.startswith('Lale_') for p in files))
