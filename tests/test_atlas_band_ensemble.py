import unittest
import numpy as np
from atlas_band_ensemble import combine_frequency,validate_frequency_weights


class FrequencyEnsembleTests(unittest.TestCase):
    def test_constant_frequency_weights_match_sample_average_including_edges(self):
        rng=np.random.default_rng(29)
        source=rng.normal(0,.1,(44173,2))
        candidates=[rng.normal(0,.1,source.shape) for _ in range(3)]
        spec={'anchors_hz':[0,22050],'weights':[[.2,.2],[.3,.3],[.5,.5]]}
        vocal,inst=combine_frequency(source,candidates,spec)
        np.testing.assert_allclose(vocal,.2*candidates[0]+.3*candidates[1]+.5*candidates[2],atol=1e-15)
        np.testing.assert_allclose(vocal+inst,source,atol=1e-15)

    def test_frequency_experts_recover_complementary_tones(self):
        t=np.arange(44100)/44100
        low=np.column_stack([.1*np.sin(2*np.pi*220*t)]*2)
        high=np.column_stack([.1*np.sin(2*np.pi*3000*t)]*2)
        source=low+high+np.column_stack([.05*np.sin(2*np.pi*880*t)]*2)
        spec={'anchors_hz':[0,1000,2000,22050],'weights':[[1,1,0,0],[0,0,1,1]]}
        vocal,inst=combine_frequency(source,[low,high],spec)
        self.assertLess(np.mean((vocal-low-high)**2),.01*np.mean((.5*low+.5*high-low-high)**2))
        np.testing.assert_allclose(vocal+inst,source,atol=1e-15)

    def test_invalid_configuration_and_source_are_rejected(self):
        for spec in ({'anchors_hz':[0,22050],'weights':[[.2,.5]]},
                     {'anchors_hz':[0,0,22050],'weights':[[1,1,1]]},
                     {'anchors_hz':[0,22050],'weights':[[np.nan,1]]}):
            with self.assertRaises(ValueError):validate_frequency_weights(spec,1)
        x=np.zeros((4410,2));spec={'anchors_hz':[0,22050],'weights':[[1,1]]}
        with self.assertRaises(ValueError):combine_frequency(x+np.nan,[x],spec)
