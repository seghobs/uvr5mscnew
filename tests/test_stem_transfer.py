import tempfile
import unittest
from pathlib import Path
import numpy as np
import soundfile as sf
from stem_transfer import transfer_pair


class TransferTests(unittest.TestCase):
    def test_frequency_selection_transfers_target_band_and_preserves_outside(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);sr=44100;t=np.arange(sr*4)/sr
            low=np.sin(2*np.pi*500*t)*.1;high=np.sin(2*np.pi*7000*t)*.1
            vocal=np.column_stack([low+high]*2).astype('float32');inst=np.zeros_like(vocal)
            sf.write(root/'v.wav',vocal,sr,subtype='FLOAT');sf.write(root/'i.wav',inst,sr,subtype='FLOAT')
            result=transfer_pair(root,'v.wav','i.wav',1,3,1,200,1500)
            v,_=sf.read(root/result['vocal']);i,_=sf.read(root/result['instrumental'])
            np.testing.assert_array_equal(v[:sr],vocal[:sr]);np.testing.assert_array_equal(v[3*sr:],vocal[3*sr:])
            np.testing.assert_array_equal(i[:sr],inst[:sr]);np.testing.assert_array_equal(i[3*sr:],inst[3*sr:])
            np.testing.assert_allclose(v+i,vocal+inst,atol=1e-7)
            signal=i[sr+2000:3*sr-2000,0];time=t[sr+2000:3*sr-2000]
            def amplitude(hz):return abs(np.sum(signal*np.exp(-2j*np.pi*hz*time)))*2/len(signal)
            self.assertGreater(amplitude(500),.08)
            self.assertLess(amplitude(7000),.005)
            self.assertEqual(sf.info(root/result['vocal']).subtype,'FLOAT')

    def test_whole_song_mode_filters_beyond_preview_and_streams_consistently(self):
        from scipy.signal import sosfilt
        from stem_transfer import band_filters
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);sr=44100;t=np.arange(sr*4)/sr
            wave=np.column_stack([np.sin(2*np.pi*500*t)*.1]*2).astype('float32')
            sf.write(root/'v.wav',wave,sr,subtype='FLOAT');sf.write(root/'i.wav',wave*0,sr,subtype='FLOAT')
            result=transfer_pair(root,'v.wav','i.wav',1,1.2,.5,200,1500,'all')
            v,_=sf.read(root/result['vocal']);i,_=sf.read(root/result['instrumental'])
            reference=sosfilt(band_filters(200,1500,sr),wave,axis=0)*.5
            np.testing.assert_allclose(i[1000:-1000],reference[1000:-1000],atol=1e-7)
            np.testing.assert_allclose(v+i,wave,atol=1e-7)
            self.assertEqual(result['start'],0);self.assertEqual(result['end'],4)
            for lo,hi in [(100,None),(2000,1000),(20,30000),(float('nan'),4000)]:
                with self.assertRaises(ValueError):transfer_pair(root,'v.wav','i.wav',1,2,1,lo,hi)

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
