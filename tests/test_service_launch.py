import unittest
from pathlib import Path
import tempfile
from unittest.mock import patch
from types import SimpleNamespace
import service_control as service


class LaunchTests(unittest.TestCase):
    def test_batch_launch_keeps_output_in_invoking_console(self):
        with tempfile.TemporaryDirectory() as directory,patch.object(service,'ROOT',Path(directory)),patch.object(service,'frontend_running',return_value=False),patch.object(service.subprocess,'call',return_value=0) as call:
            self.assertEqual(service.launch_frontend(),0)
            self.assertEqual(call.call_args.args[0],['cmd.exe','/d','/c','call',str(Path(directory)/'start.bat'),'--owned'])
            self.assertIs(call.call_args.kwargs['stdout'],service.sys.stdout)
            self.assertIs(call.call_args.kwargs['stderr'],service.sys.stderr)

    def test_old_shutdown_does_not_stop_new_server(self):
        with patch.object(service,'service_info',return_value={'pid':456}),patch.object(service,'stop') as stop:
            service.stop_generation(123)
            stop.assert_not_called()

    def test_shutdown_stops_only_requested_generation(self):
        with patch.object(service,'service_info',return_value={'pid':123}),patch.object(service,'stop') as stop:
            service.stop_generation(123)
            stop.assert_called_once_with(True)

    def test_frontend_stops_before_backend(self):
        frontend,backend=SimpleNamespace(pid=101),SimpleNamespace(pid=102)
        with patch.object(service,'prepare'),patch.object(service.psutil,'process_iter',side_effect=[[frontend,backend],[frontend,backend]]),patch.object(service,'owns_frontend',side_effect=lambda p:p is frontend),patch.object(service,'owns_backend',side_effect=lambda p:p is backend),patch.object(service,'terminate_tree') as terminate:
            service.stop(True)
            self.assertEqual([call.args[0] for call in terminate.call_args_list],[frontend,backend])
    def test_frontend_port_free(self):
        with patch.object(service.psutil,'net_connections',return_value=[]):
            self.assertFalse(service.frontend_running())

    def test_owned_frontend_is_reused(self):
        listener=SimpleNamespace(status='LISTEN',laddr=SimpleNamespace(port=3000),pid=123)
        with patch.object(service.psutil,'net_connections',return_value=[listener]),patch.object(service.psutil,'Process'),patch.object(service,'owns_frontend',return_value=True):
            self.assertTrue(service.frontend_running())

    def test_foreign_frontend_is_not_reused_or_terminated(self):
        listener=SimpleNamespace(status='LISTEN',laddr=SimpleNamespace(port=3000),pid=123)
        with patch.object(service.psutil,'net_connections',return_value=[listener]),patch.object(service.psutil,'Process'),patch.object(service,'owns_frontend',return_value=False),patch.object(service,'terminate_tree') as stop:
            with self.assertRaises(RuntimeError):service.frontend_running()
            stop.assert_not_called()

    def test_preset_weight_update_invalidates_loaded_service_revision(self):
        with tempfile.TemporaryDirectory() as directory,patch.object(service,'ROOT',Path(directory)):
            root=Path(directory);(root/'api_modern.py').write_text('unchanged python')
            folder=root/'frontend/src/lib';folder.mkdir(parents=True)
            preset=folder/'atlas-studio-v2-preset.json';preset.write_text('{"weight":0.4}')
            original=service.revision()
            (root/'unrelated-report.md').write_text('A documentation update does not restart services')
            self.assertEqual(original,service.revision())
            preset.write_text('{"weight":0.5}')
            self.assertNotEqual(original,service.revision())

    def test_busy_owned_server_allows_frontend_without_killing_jobs(self):
        current={'root':str(service.ROOT),'revision':'old'}
        with patch.object(service,'service_info',return_value=current),patch.object(service,'revision',return_value='new'),patch.object(service.psutil,'process_iter',return_value=[object()]),patch.object(service,'owns_backend',return_value=True),patch.object(service,'stop',side_effect=service.ServiceBusy('busy')),patch.object(service.subprocess,'Popen') as spawn:
            service.start(reuse_busy=True)
            spawn.assert_not_called()
            with self.assertRaises(service.ServiceBusy):service.start()

    def test_other_project_never_reused(self):
        with patch.object(service,'service_info',return_value={'root':str(service.ROOT/'another-project'),'revision':'old'}):
            with self.assertRaises(RuntimeError):service.start(reuse_busy=True)

    def test_connectivity_failure_not_misclassified_as_busy(self):
        with patch.object(service,'service_info',return_value={'root':str(service.ROOT)}),patch.object(service.urllib.request,'urlopen',side_effect=TimeoutError()):
            with self.assertRaises(RuntimeError) as error:service.prepare()
            self.assertNotIsInstance(error.exception,service.ServiceBusy)


if __name__=='__main__':unittest.main()
