import unittest
from roformer_config import compatible_single_target_config


class ConfigCompatibilityTests(unittest.TestCase):
    def example(self):
        return {'audio': {'hop_length': 441}, 'model': {'num_stems': 1, 'stft_hop_length': 512,
            'mlp_expansion_factor': 4, 'use_torch_checkpoint': False, 'skip_connection': False},
            'training': {'instruments': ['vocals', 'other'], 'target_instrument': 'other'}}

    def test_single_instrument_output_gets_actual_target_label(self):
        original = self.example()
        effective = compatible_single_target_config(original)
        self.assertEqual(effective['training']['instruments'], ['other', 'vocals'])
        self.assertEqual(effective['audio']['hop_length'], 512)
        self.assertEqual(original['training']['instruments'], ['vocals', 'other'])
        self.assertEqual(original['audio']['hop_length'], 441)

    def test_multiple_outputs_keep_their_trained_order(self):
        config = self.example(); config['model']['num_stems'] = 2
        self.assertEqual(compatible_single_target_config(config)['training']['instruments'], ['vocals', 'other'])

    def test_non_equivalent_architecture_is_rejected(self):
        config = self.example(); config['model']['skip_connection'] = True
        with self.assertRaises(ValueError): compatible_single_target_config(config)
