import tempfile
import unittest
from pathlib import Path
import numpy as np
import soundfile as sf
from stem_transfer import transfer_pair


class TransferTests(unittest.TestCase):
    def test_sample_position_duration_mix_and_originals_preserved(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);sr=48000
            vocal=np.random.default_rng(4).normal(0,.1,(sr,2)).astype('float32');inst=vocal*.2
            sf.write(root/'v.wav',vocal,sr,subtype='FLOAT');sf.write(root/'i.wav',inst,sr,subtype='FLOAT')
            original=(root/'v.wav').read_bytes()
            result=transfer_pair(root,'v.wav','i.wav',.2,.6,.75)
            v,rate=sf.read(root/result['vocal']);i,_=sf.read(root/result['instrumental'])
            self.assertEqual(rate,sr);self.assertEqual(v.shape,vocal.shape)
            np.testing.assert_array_equal(v[:9600],vocal[:9600]);np.testing.assert_array_equal(v[28800:],vocal[28800:])
            np.testing.assert_allclose(v[10000:28000],vocal[10000:28000]*.25,atol=1e-7)
            np.testing.assert_allclose(v+i,vocal+inst,atol=1e-7)
            self.assertEqual(original,(root/'v.wav').read_bytes())

    def test_rejects_out_of_bounds_mismatched_pairs_and_paths(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            sf.write(root/'v.wav',np.zeros((1000,2)),1000)
            sf.write(root/'i.wav',np.zeros((999,2)),1000)
            for start,end,amount in [(0,1,1),(-1,.2,1),(0,float('nan'),1),(0,.5,2)]:
                with self.assertRaises(ValueError):transfer_pair(root,'v.wav','i.wav',start,end,amount)
            with self.assertRaises(ValueError):transfer_pair(root,'../other.wav','i.wav',0,.5)
            sf.write(root/'i.wav',np.zeros((1000,2)),1000)
            with self.assertRaises(ValueError):transfer_pair(root,'v.wav','i.wav',0,1.01)
