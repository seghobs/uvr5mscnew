import tempfile
from pathlib import Path
from types import SimpleNamespace
import unittest
import torch
from separation_checkpoint import attach_checkpoint,SeparationTasks


class Network(torch.nn.Module):
    def __init__(self,fail_at=None):
        super().__init__();self.weight=torch.nn.Parameter(torch.tensor(2.));self.calls=0;self.fail_at=fail_at
    def forward(self,x):
        self.calls+=1
        if self.calls==self.fail_at:raise RuntimeError('simulated crash')
        return x*self.weight


class CheckpointTests(unittest.TestCase):
    def instance(self,root,fail_at=None):
        model=root/'model.ckpt';model.write_bytes(b'weights')
        return SimpleNamespace(is_roformer=True,model_path=model,model_data_cfgdict='native',overlap=2,model_run=Network(fail_at))

    def test_crash_resume_exact_without_recomputing_completed_chunks(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);source=root/'audio.wav';source.write_bytes(b'audio')
            first=self.instance(root,3);restore=attach_checkpoint(first,source,{},root/'chunks')
            expected=[torch.ones(1,2,8)*i*2 for i in range(4)]
            first.model_run(torch.zeros(1,2,8));first.model_run(torch.ones(1,2,8))
            with self.assertRaises(RuntimeError):first.model_run(torch.ones(1,2,8)*2)
            restore()
            resumed=self.instance(root);attach_checkpoint(resumed,source,{},root/'chunks')
            actual=[resumed.model_run(torch.ones(1,2,8)*i) for i in range(4)]
            self.assertEqual(resumed.model_run.calls,2)
            for a,b in zip(actual,expected):self.assertTrue(torch.equal(a,b))

    def test_changed_source_never_reuses_old_chunks(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);source=root/'audio.wav';source.write_bytes(b'one')
            first=self.instance(root);attach_checkpoint(first,source,{},root/'chunks');first.model_run(torch.ones(1,2,8))
            source.write_bytes(b'two')
            second=self.instance(root);attach_checkpoint(second,source,{},root/'chunks');second.model_run(torch.ones(1,2,8))
            self.assertEqual(second.model_run.calls,1)

    def test_changed_model_or_parameters_never_reuse_old_chunks(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);source=root/'audio.wav';source.write_bytes(b'audio')
            first=self.instance(root);attach_checkpoint(first,source,{'overlap':8},root/'chunks');first.model_run(torch.ones(1,2,8))
            changed_params=self.instance(root);attach_checkpoint(changed_params,source,{'overlap':4},root/'chunks');changed_params.model_run(torch.ones(1,2,8))
            self.assertEqual(changed_params.model_run.calls,1)
            changed_model=self.instance(root);Path(changed_model.model_path).write_bytes(b'new weights')
            attach_checkpoint(changed_model,source,{'overlap':8},root/'chunks');changed_model.model_run(torch.ones(1,2,8))
            self.assertEqual(changed_model.model_run.calls,1)

    def test_tensor_checksum_mismatch_recomputed(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);source=root/'audio.wav';source.write_bytes(b'audio')
            first=self.instance(root);attach_checkpoint(first,source,{},root/'chunks');first.model_run(torch.ones(1,2,8))
            file=next((root/'chunks').glob('*/*.pt'))
            saved=torch.load(file,weights_only=True);saved['output']+=1;torch.save(saved,file)
            resumed=self.instance(root);attach_checkpoint(resumed,source,{},root/'chunks')
            output=resumed.model_run(torch.ones(1,2,8))
            self.assertEqual(resumed.model_run.calls,1)
            self.assertTrue(torch.equal(output,torch.ones(1,2,8)*2))

    def test_corrupt_saved_chunk_recomputed(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);source=root/'audio.wav';source.write_bytes(b'audio')
            first=self.instance(root);attach_checkpoint(first,source,{},root/'chunks');first.model_run(torch.ones(1,2,8))
            next((root/'chunks').glob('*/*.pt')).write_bytes(b'corrupt')
            resumed=self.instance(root);attach_checkpoint(resumed,source,{},root/'chunks');resumed.model_run(torch.ones(1,2,8))
            self.assertEqual(resumed.model_run.calls,1)

    def test_task_restores_same_identifier_and_cancel_does_not_resume(self):
        with tempfile.TemporaryDirectory() as folder:
            file=Path(folder)/'tasks.json';store=SeparationTasks(file)
            task={'status':'processing','separation_request':{'kind':'ensemble','audio_path':'source.wav'}}
            store.update('same-id',task)
            self.assertEqual(SeparationTasks(file).pending(),[('same-id',task)])
            store.cancel_all();self.assertEqual(SeparationTasks(file).pending(),[])
