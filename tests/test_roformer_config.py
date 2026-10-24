import unittest
import tempfile
from pathlib import Path
from roformer_config import compatible_single_target_config


class LegacyCacheTests(unittest.TestCase):
    def test_matching_legacy_pair_is_reused_without_altering_originals(self):
        import torch
        from safetensors.torch import save_file
        from roformer_config import reuse_legacy_safetensors
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            save_file({'band_split.to_features.0.0.gamma': torch.ones(2)}, str(root/'model.safetensors'))
            (root/'config.yaml').write_text('model:\n  freqs_per_bands: [2]\n')
            target = root/'isolated'
            self.assertTrue(reuse_legacy_safetensors(root, target))
            self.assertEqual((target/'model.safetensors').read_bytes(), (root/'model.safetensors').read_bytes())
            self.assertEqual((target/'config.yaml').read_bytes(), (root/'config.yaml').read_bytes())

    def test_unrelated_config_is_not_copied(self):
        import torch
        from safetensors.torch import save_file
        from roformer_config import reuse_legacy_safetensors
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            save_file({'band_split.to_features.0.0.gamma': torch.ones(2)}, str(root/'model.safetensors'))
            (root/'config.yaml').write_text('model:\n  freqs_per_bands: [2, 2]\n')
            self.assertFalse(reuse_legacy_safetensors(root, root/'isolated'))
            self.assertFalse((root/'isolated').exists())


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
