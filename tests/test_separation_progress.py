import unittest
from types import SimpleNamespace
from separation_progress import attach_roformer_progress


class FakeNetwork:
    def register_forward_hook(self, hook):
        self.hook = hook
        return SimpleNamespace(remove=lambda: setattr(self, 'hook', None))


class SeparationProgressTests(unittest.TestCase):
    def instance(self, step=1):
        return SimpleNamespace(is_roformer=True, overlap=step, model_run=FakeNetwork(),
            model_data_cfgdict=SimpleNamespace(audio=SimpleNamespace(sample_rate=44100)))

    def test_reports_actual_chunks_and_leaves_output_untouched(self):
        instance = self.instance(); events = []
        handle = attach_roformer_progress(instance, 44100*2+1, lambda p,m:events.append((p,m)))
        output = object()
        for _ in range(3):
            self.assertIsNone(instance.model_run.hook(None, (), output))
        self.assertEqual([m for p,m in events], [f'Ses ayrıştırılıyor · {i}/3 parça' for i in (1,2,3)])
        self.assertTrue(all(a[0]<b[0] for a,b in zip(events, events[1:])))
        self.assertAlmostEqual(events[-1][0], .95)
        handle.remove(); self.assertIsNone(instance.model_run.hook)

    def test_jobs_do_not_share_counters(self):
        a,b = self.instance(),self.instance(); ea,eb = [],[]
        attach_roformer_progress(a, 88200, lambda p,m:ea.append(m))
        attach_roformer_progress(b, 44100, lambda p,m:eb.append(m))
        a.model_run.hook(None, (), None); b.model_run.hook(None, (), None)
        self.assertIn('1/2', ea[0]); self.assertIn('1/1', eb[0])

    def test_unsupported_or_empty_input_has_no_hook(self):
        instance = self.instance()
        self.assertIsNone(attach_roformer_progress(instance, 0, print))
        instance.is_roformer = False
        self.assertIsNone(attach_roformer_progress(instance, 44100, print))


if __name__ == '__main__': unittest.main()
