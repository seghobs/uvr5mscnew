import unittest
from types import SimpleNamespace
import numpy as np
from roformer_input import attach_minimum_window


class ShortRoformerTests(unittest.TestCase):
    def instance(self,override=False):
        calls=[]
        def demix(mix):
            calls.append(mix)
            return {'vocals':mix*.25,'other':mix*.75}
        instance=SimpleNamespace(is_roformer=True,segment_size=5,override_model_segment_size=override,
            model_data_cfgdict=SimpleNamespace(audio=SimpleNamespace(hop_length=512),inference=SimpleNamespace(dim_t=1536)),demix=demix)
        return instance,calls

    def test_short_input_is_padded_to_native_window_then_cropped_without_gain_change(self):
        instance,calls=self.instance();minimum=attach_minimum_window(instance)
        wave=np.full((2,705600),.125)
        result=instance.demix(wave)
        self.assertEqual(minimum,785920)
        self.assertEqual(calls[0].shape,(2,785920))
        self.assertEqual(result['vocals'].shape,wave.shape)
        np.testing.assert_array_equal(calls[0][:,:len(wave[0])],wave)
        self.assertFalse(calls[0][:,len(wave[0]):].any())
        np.testing.assert_array_equal(result['vocals']+result['other'],wave)

    def test_complete_window_uses_original_input_and_override_is_respected(self):
        instance,calls=self.instance(True);minimum=attach_minimum_window(instance)
        wave=np.ones((2,minimum))
        instance.demix(wave)
        self.assertIs(calls[0],wave)
        self.assertEqual(minimum,2048)

    def test_invalid_input_is_rejected_before_model_runs(self):
        instance,calls=self.instance();attach_minimum_window(instance)
        for wave in (np.empty((2,0)),np.zeros((1,100)),np.full((2,100),np.nan)):
            with self.assertRaises(ValueError):instance.demix(wave)
        self.assertFalse(calls)
