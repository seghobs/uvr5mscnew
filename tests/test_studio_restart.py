import tempfile
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch, Mock
import studio_restart as restart
import service_control as service


class StudioRestartTests(TestCase):
    def test_build_failure_preserves_running_services(self):
        with patch.object(restart,'wait_idle'), patch.object(restart,'build',side_effect=RuntimeError('build failed')), patch.object(restart,'update') as update, patch.object(service,'stop') as stop:
            restart.run('test')
            stop.assert_not_called()
            update.assert_called_once_with('test','failed','build failed')

    def test_busy_jobs_are_waited_for(self):
        with patch.object(service,'prepare',side_effect=[service.ServiceBusy('busy'),None]) as prepare, patch.object(restart.time,'sleep'), patch.object(restart,'update') as update:
            restart.wait_idle('test')
            self.assertEqual(prepare.call_count,2)
            self.assertEqual(update.call_args.args[1],'waiting')

    def test_request_deduplicates_running_restart(self):
        import time
        current={'phase':'building','id':'existing','updated_at':time.time()}
        with patch.object(restart,'status',return_value=current),patch.object(restart,'detached') as spawn:
            self.assertEqual(restart.request(),current)
            spawn.assert_not_called()

    def test_build_uses_separate_directory(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(restart,'ROOT',Path(folder)), patch.object(restart,'update'), patch.object(restart.shutil,'which',return_value='npm'), patch.object(restart.subprocess,'run',return_value=Mock(returncode=0)) as run:
            target=Path(folder)/'frontend/.next-restart-test'
            target.mkdir(parents=True);(target/'BUILD_ID').write_text('build')
            environment=restart.build('test')
            self.assertEqual(environment['UVR_NEXT_DIST'],'.next-restart-test')
            self.assertEqual(run.call_args.kwargs['env']['UVR_NEXT_DIST'],'.next-restart-test')
