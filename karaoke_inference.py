"""Request-scoped CTC reuse. Cache acoustic evidence, never word decisions."""
from collections import OrderedDict
import hashlib
import time


class EmissionCache:
    def __init__(self, model, extractor, device, max_bytes=64*1024**2):
        self.model,self.extractor,self.device=model,extractor,device
        self.max_bytes=max_bytes;self.bytes=0;self.entries=OrderedDict()
        self.hits=0;self.calls=0;self.seconds=0.

    def infer(self, mono, rate):
        import numpy as np
        import torch
        import torchaudio.functional as AF
        samples=np.ascontiguousarray(mono)
        # Exact samples and rate, scoped to one model/adapter/device instance.
        key=(rate,samples.dtype.str,samples.shape,hashlib.sha256(samples.tobytes()).digest())
        if key in self.entries:
            self.hits+=1;self.entries.move_to_end(key)
            return self.entries[key]
        wave=AF.resample(torch.from_numpy(samples.copy()),rate,16000)
        if len(wave)<400:return None
        inputs=self.extractor(wave.numpy(),sampling_rate=16000,return_tensors='pt')
        started=time.monotonic()
        with torch.inference_mode():
            emission=self.model(**{k:v.to(self.device) for k,v in inputs.items()}).logits.log_softmax(-1).cpu()
        self.calls+=1;self.seconds+=time.monotonic()-started
        size=emission.numel()*emission.element_size()
        if size<=self.max_bytes:
            while self.entries and self.bytes+size>self.max_bytes:
                _,old=self.entries.popitem(last=False);self.bytes-=old.numel()*old.element_size()
            self.entries[key]=emission;self.bytes+=size
        return emission

    def stats(self):
        return dict(model_calls=self.calls,reused_clips=self.hits,inference_seconds=round(self.seconds,3))


class RefinementSession:
    """Keep at most one model resident across supplementary retry passes."""
    def __init__(self):self.language=None;self.cache=None
    def load(self,language,progress=None):
        if self.language!=language:
            self.close()
            import torch
            from transformers import Wav2Vec2ForCTC,Wav2Vec2FeatureExtractor
            from karaoke_alignment_models import ensure_model, MMS_ADAPTERS
            directory,vocab=ensure_model(language,progress)
            required_gb=5 if language in MMS_ADAPTERS else 3
            device='cuda' if torch.cuda.is_available() and torch.cuda.mem_get_info()[0]>required_gb*1024**3 else 'cpu'
            adapter=MMS_ADAPTERS.get(language)
            model=Wav2Vec2ForCTC.from_pretrained(directory,local_files_only=True,**({'target_lang':adapter} if adapter else {})).eval().to(device)
            extractor=Wav2Vec2FeatureExtractor.from_pretrained(directory,local_files_only=True)
            self.cache=EmissionCache(model,extractor,device);self.vocab=vocab;self.language=language
        return self.cache,self.vocab
    def close(self):
        if self.cache is not None:
            device=self.cache.device
            self.cache=None;self.language=None
            if str(device).startswith('cuda'):
                import torch
                torch.cuda.empty_cache()
    def __enter__(self):return self
    def __exit__(self,*args):self.close()
