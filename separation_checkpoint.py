"""Exact Roformer inference checkpoints; replay overlap-add without repeating GPU work."""
import hashlib
import json
import os
import pickle
from pathlib import Path
import threading
import time


def file_digest(path):
    digest=hashlib.sha256()
    with Path(path).open('rb') as handle:
        for block in iter(lambda:handle.read(1024*1024),b''):digest.update(block)
    return digest.hexdigest()


def attach_checkpoint(instance, source, params, root):
    if not getattr(instance,'is_roformer',False):return None
    import torch
    identity={'version':1,'source':file_digest(source),'model':file_digest(instance.model_path),
              'config':str(instance.model_data_cfgdict),'params':params,'overlap':instance.overlap,
              'torch':torch.__version__,'device':str(next(instance.model_run.parameters()).device)}
    key=hashlib.sha256(json.dumps(identity,sort_keys=True,default=str).encode()).hexdigest()
    folder=Path(root)/key;folder.mkdir(parents=True,exist_ok=True)
    model=instance.model_run;original=model.forward;index=0
    def forward(x,*args,**kwargs):
        nonlocal index
        number=index;index+=1
        target=folder/f'{number:06d}.pt'
        input_key=hashlib.sha256(x.detach().cpu().contiguous().numpy().tobytes()).hexdigest()
        try:
            saved=torch.load(target,map_location='cpu',weights_only=True)
            output=saved['output']
            output_hash=hashlib.sha256(output.contiguous().numpy().tobytes()).hexdigest()
            if saved['input']==input_key and saved['checksum']==output_hash and isinstance(output,torch.Tensor) and torch.isfinite(output).all():
                return output.to(x.device)
        except (OSError,RuntimeError,ValueError,KeyError,EOFError,pickle.UnpicklingError,AttributeError):pass
        output=original(x,*args,**kwargs)
        if not isinstance(output,torch.Tensor) or not torch.isfinite(output).all():
            raise ValueError('Model geçersiz checkpoint çıktısı üretti')
        temporary=target.with_suffix('.tmp')
        cpu_output=output.detach().cpu().contiguous()
        torch.save({'input':input_key,'output':cpu_output,
                    'checksum':hashlib.sha256(cpu_output.numpy().tobytes()).hexdigest()},temporary)
        os.replace(temporary,target)
        return output
    model.forward=forward
    def restore():model.forward=original
    return restore


class SeparationTasks:
    def __init__(self,path):
        self.path=Path(path);self.lock=threading.RLock()
        try:self.records=json.loads(self.path.read_text(encoding='utf8'))
        except (OSError,ValueError):self.records={}

    def update(self,identifier,task):
        if not task.get('separation_request'):return
        with self.lock:
            self.records[identifier]=task
            self._write()

    def _write(self):
        self.path.parent.mkdir(parents=True,exist_ok=True)
        temporary=self.path.with_suffix('.tmp')
        temporary.write_text(json.dumps(self.records,ensure_ascii=False),encoding='utf8')
        os.replace(temporary,self.path)

    def pending(self):
        with self.lock:return [(key,dict(value)) for key,value in self.records.items() if value.get('status')=='processing']

    def cancel_all(self):
        with self.lock:
            for value in self.records.values():
                if value.get('status')=='processing':value.update(status='cancelled',updated_at=time.time())
            self._write()
