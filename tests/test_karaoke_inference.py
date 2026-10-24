import unittest
from types import SimpleNamespace
from unittest.mock import Mock,patch
import numpy as np
import torch
from karaoke_inference import EmissionCache,RefinementSession

class InferenceReuseTests(unittest.TestCase):
    def cache(self,max_bytes=1024):
        model=Mock(side_effect=lambda **kw:SimpleNamespace(logits=torch.stack((kw['input_values'][:,:4],kw['input_values'][:,:4]+1),-1)))
        extractor=Mock(side_effect=lambda values,**kw:{'input_values':torch.from_numpy(values.copy())[None]})
        return EmissionCache(model,extractor,'cpu',max_bytes),model,extractor

    def test_exact_clip_reuses_unmodified_cpu_evidence(self):
        cache,model,extractor=self.cache()
        wave=np.linspace(-1,1,800,dtype='float32')
        first=cache.infer(wave,16000);second=cache.infer(wave.copy(),16000)
        self.assertTrue(torch.equal(first,second));self.assertEqual(model.call_count,1)
        self.assertEqual(extractor.call_count,1);self.assertEqual(cache.stats()['reused_clips'],1)
        self.assertEqual(first.device.type,'cpu')
        wave[0]+=.01
        cache.infer(wave,16000)
        self.assertEqual(model.call_count,2)

    def test_distinct_models_and_sample_rates_never_share_evidence(self):
        cache,model,_=self.cache();other,second,_=self.cache()
        wave=np.ones(800,dtype='float32')
        cache.infer(wave,16000);cache.infer(wave,8000);other.infer(wave,16000)
        self.assertEqual(model.call_count,2);self.assertEqual(second.call_count,1)

    def test_bounded_cache_evicts_without_changing_results(self):
        cache,model,_=self.cache(max_bytes=32)
        a=np.ones(800,dtype='float32');b=a*2
        first=cache.infer(a,16000);cache.infer(b,16000);again=cache.infer(a,16000)
        self.assertEqual(model.call_count,3);self.assertTrue(torch.equal(first,again))
        self.assertLessEqual(cache.bytes,32)

    def test_failed_inference_is_not_cached(self):
        cache,model,_=self.cache();model.side_effect=RuntimeError('GPU unavailable')
        with self.assertRaises(RuntimeError):cache.infer(np.ones(800,dtype='float32'),16000)
        self.assertFalse(cache.entries)
        self.assertEqual(cache.calls,0)

    def test_retry_passes_load_once_and_adapter_switch_reloads(self):
        model=Mock();model.eval.return_value=model;model.to.return_value=model
        extractor=Mock()
        with patch('karaoke_alignment_models.ensure_model',return_value=('local-model',{'[PAD]':0})),patch('transformers.Wav2Vec2ForCTC.from_pretrained',return_value=model) as weights,patch('transformers.Wav2Vec2FeatureExtractor.from_pretrained',return_value=extractor),patch('torch.cuda.is_available',return_value=False):
            with RefinementSession() as session:
                first,_=session.load('tr')
                again,_=session.load('tr')
                self.assertIs(first,again);self.assertEqual(weights.call_count,1)
                second,_=session.load('kmr_mms')
                self.assertIsNot(first,second);self.assertEqual(weights.call_count,2)
                self.assertEqual(weights.call_args.kwargs['target_lang'],'kmr-script_latin')
                for language,adapter in [('az','azj-script_latin'),('en','eng')]:
                    session.load(language)
                    self.assertEqual(weights.call_args.kwargs['target_lang'],adapter)
            self.assertIsNone(session.cache)

    def test_session_releases_model_even_on_error(self):
        session=RefinementSession()
        with self.assertRaises(RuntimeError):
            with session:
                session.cache=SimpleNamespace(device='cpu');session.language='tr'
                raise RuntimeError('cancelled')
        self.assertIsNone(session.cache);self.assertIsNone(session.language)

if __name__=='__main__':unittest.main()
