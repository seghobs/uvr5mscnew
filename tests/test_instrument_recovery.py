import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import shutil

import numpy as np
import soundfile as sf
from instrument_recovery import recover_instruments,target_output,run_recovery


class RecoveryTests(unittest.TestCase):
    def tones(self):
        t=np.arange(44100)/44100
        instrument=np.column_stack([np.sin(2*np.pi*440*t)]*2).astype('float32')*.1
        voice=np.column_stack([np.sin(2*np.pi*1760*t)]*2).astype('float32')*.1
        return instrument,voice

    def test_recovers_missing_tone_without_doubling_overlapping_experts(self):
        instrument,voice=self.tones();mixture=instrument+voice
        once=recover_instruments(mixture,instrument*.5,[instrument])
        overlap=recover_instruments(mixture,instrument*.5,[instrument,instrument,instrument])
        np.testing.assert_allclose(once,overlap,atol=1e-7)
        self.assertLess(np.linalg.norm(once-instrument),np.linalg.norm(instrument*.5-instrument))
        # Transfer is bounded; no second copy of an already preserved instrument.
        preserved=recover_instruments(mixture,instrument,[instrument])
        self.assertLess(np.linalg.norm(preserved-instrument),np.linalg.norm(instrument)*.03)
        np.testing.assert_array_equal(recover_instruments(mixture,instrument,[instrument],0),instrument)
        np.testing.assert_allclose(recover_instruments(mixture,instrument,[instrument*0]),instrument,atol=1e-7)

    def test_rejects_wrong_target_and_invalid_audio(self):
        with self.assertRaises(ValueError):target_output(['source_(other).wav'],'flute')
        x,_=self.tones()
        with self.assertRaises(ValueError):recover_instruments(x,x,[x[:-1]])
        with self.assertRaises(ValueError):recover_instruments(x,x,[x],1.1)

    def test_pipeline_uses_clean_baseline_and_exports_complementary_pair(self):
        instrument,voice=self.tones();mixture=instrument+voice
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);source=root/'source.wav'
            sf.write(source,mixture,44100,subtype='FLOAT')
            def clean(core,prepared,fmt,folder,progress):
                path=Path(folder)/'CleanMusic_Instrumental_test.wav'
                sf.write(path,instrument*.5,44100,subtype='FLOAT');progress(1,'done');return [str(path)]
            def separate(prepared,name,*args,work_dir,**kwargs):
                tag=next(t for t in ['flute','violin','wind'] if t in name.lower())
                path=Path(work_dir)/f'probe_({tag}).wav'
                sf.write(path,instrument,44100,subtype='FLOAT');return [str(path)]
            def decode(command,**kwargs):
                shutil.copyfile(source,command[-1]);return SimpleNamespace(returncode=0)
            core=SimpleNamespace(roformer_separator=separate,clear_gpu_and_ram_cache=lambda:None)
            progress=[]
            with patch('comparison_ensemble.run_clean_music',side_effect=clean) as base,patch('instrument_recovery.subprocess.run',side_effect=decode):
                files=run_recovery(core,source,'wav',root,lambda p,m:progress.append(p))
            base.assert_called_once()
            vocal,sr=sf.read(files[0]);inst,_=sf.read(files[1])
            np.testing.assert_allclose(vocal+inst,mixture,atol=1e-7)
            self.assertLess(np.linalg.norm(inst-instrument),np.linalg.norm(instrument*.5-instrument))
            self.assertTrue(all(Path(p).name.startswith('CleanMusicRestore_') for p in files))
            self.assertEqual(progress,sorted(progress))
