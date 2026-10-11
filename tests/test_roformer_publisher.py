import copy
import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
from roformer_publisher import REGISTRY, normalize_config, verify, architecture_scope


class PublisherTests(unittest.TestCase):
    def test_custom_kwargs_and_target_order_preserved(self):
        config={'model':{'stft_hop_length':512,'use_torch_checkpoint':True,'skip_connection':False,'custom_depth':4},
                'audio':{'hop_length':441},'inference':{'batch_size':8},
                'training':{'target_instrument':'instrument','instruments':['vocals','instrument']}}
        before=copy.deepcopy(config['model'])
        result=normalize_config(config)
        self.assertEqual(result['model'],before)
        self.assertEqual(result['training']['instruments'],['instrumental','vocals'])
        self.assertEqual(result['training']['target_instrument'],'instrumental')
        self.assertEqual(result['audio']['hop_length'],512)
        self.assertEqual(result['inference']['batch_size'],1)

    def test_checksum_blocks_modified_publisher_code(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'publisher.py';path.write_bytes(b'original')
            digest=hashlib.sha256(b'original').hexdigest()
            verify(path,digest)
            path.write_bytes(b'modified code')
            with self.assertRaises(ValueError):verify(path,digest)

    def test_architecture_override_restored_after_loading_failure(self):
        import audio_separator.separator.architectures.mdxc_separator as runner
        original=runner.BSRoformer;custom=object()
        name=next(iter(REGISTRY))
        separator=Mock();separator.download_model_files.return_value=(None,None,None,'folder/checkpoint',None)
        with patch('roformer_publisher.publisher_class',return_value=custom):
            with self.assertRaises(RuntimeError):
                with architecture_scope(separator,name):
                    self.assertIs(runner.BSRoformer,custom)
                    raise RuntimeError('load failed')
        self.assertIs(runner.BSRoformer,original)

    def test_stock_model_does_not_download_or_replace_architecture(self):
        import audio_separator.separator.architectures.mdxc_separator as runner
        original=runner.BSRoformer;separator=Mock()
        with architecture_scope(separator,'stock.ckpt'):
            self.assertIs(runner.BSRoformer,original)
        separator.download_model_files.assert_not_called()
