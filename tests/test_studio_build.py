import json
import tempfile
from pathlib import Path
from unittest import TestCase
from studio_build import fingerprint,record,cached
from studio_watch import QuietChanges


class BuildCacheTests(TestCase):
    def test_startup_build_releases_running_status_on_success_and_failure(self):
        import studio_build as cache
        import studio_restart as restart
        from unittest.mock import patch
        with patch.object(cache,'cached',return_value=None),patch.object(cache,'fingerprint',return_value='digest'),patch.object(cache,'record'):
            with patch.object(restart,'build',return_value={'UVR_NEXT_DIST':'.next-test'}),patch.object(restart,'update') as update:
                cache.ensure()
                self.assertEqual(update.call_args.args[1],'completed')
            with patch.object(restart,'build',side_effect=RuntimeError('failed')),patch.object(restart,'update') as update:
                with self.assertRaises(RuntimeError):cache.ensure()
                self.assertEqual(update.call_args.args[1],'failed')

    def project(self,root):
        (root/'frontend/src').mkdir(parents=True)
        (root/'frontend/src/page.tsx').write_text('original')
        (root/'backend.py').write_text('original')
        (root/'frontend/tsconfig.json').write_text(json.dumps({'include':['src/**/*.ts','.next/types/**/*.ts']}))
        target=root/'frontend/.next-restart-test';target.mkdir()
        for name in ['BUILD_ID','prerender-manifest.json','routes-manifest.json']:(target/name).write_text('test')
        record({'UVR_NEXT_DIST':target.name},fingerprint(root),root)

    def test_unchanged_sources_skip_and_python_frontend_deletion_invalidate(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);self.project(root)
            self.assertIsNotNone(cached(root))
            (root/'backend.py').write_text('updated')
            self.assertIsNone(cached(root))
            record({'UVR_NEXT_DIST':'.next-restart-test'},fingerprint(root),root)
            (root/'frontend/src/page.tsx').unlink()
            self.assertIsNone(cached(root))

    def test_build_outputs_and_generated_includes_do_not_invalidate(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);self.project(root)
            import os
            os.utime(root/'backend.py',None)
            (root/'frontend/.next-restart-test/BUILD_ID').write_text('generated')
            (root/'frontend/next-env.d.ts').write_text('generated')
            (root/'frontend/tsconfig.json').write_text(json.dumps({'include':['src/**/*.ts','.next-restart-other/types/**/*.ts']}))
            self.assertIsNotNone(cached(root))
            (root/'frontend/.next-restart-test/BUILD_ID').unlink()
            self.assertIsNone(cached(root))

    def test_python_syntax_failure_never_runs_build(self):
        import studio_restart as restart
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/'broken.py').write_text('def broken(')
            with patch.object(restart,'ROOT',root),patch.object(restart,'_build') as build:
                with self.assertRaises(SyntaxError):restart.build('test')
                build.assert_not_called()

    def test_debounce_waits_and_failure_is_not_retried_without_edit(self):
        changes=QuietChanges('a')
        self.assertFalse(changes.ready('b',10))
        self.assertFalse(changes.ready('c',20))
        self.assertFalse(changes.ready('c',34))
        self.assertTrue(changes.ready('c',35))
        changes.attempted='c'
        self.assertFalse(changes.ready('c',100))
        self.assertFalse(changes.ready('d',101))
        self.assertTrue(changes.ready('d',116))
