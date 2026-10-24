import tempfile
import ast
import json
import unittest
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import service_control as service


class SupervisorTests(unittest.TestCase):
    def supervise(self, codes, info=None):
        workers=[SimpleNamespace(pid=100+i,wait=Mock(return_value=code)) for i,code in enumerate(codes)]
        with tempfile.TemporaryDirectory() as directory, \
             patch.object(service,'ROOT',Path(directory)), \
             patch.object(service.subprocess,'Popen',side_effect=workers) as spawn, \
             patch.object(service,'service_info',return_value=info), \
             patch.object(service.psutil,'process_iter',return_value=[]), \
             patch.object(service,'management_lock',side_effect=nullcontext), \
             patch.object(service.time,'sleep'), \
             patch.object(service,'service_event') as events:
            service.supervise_backend()
            return spawn,events

    def test_native_crash_is_logged_and_recovered(self):
        spawn,events=self.supervise([0xC0000005,0])
        self.assertEqual(spawn.call_count,2)
        exits=[call.kwargs for call in events.call_args_list if call.args[0]=='backend_exited']
        self.assertEqual(exits[0]['windows_status'],'0xC0000005')
        self.assertIn('faulthandler',spawn.call_args.args[0])

    def test_clean_shutdown_does_not_restart(self):
        spawn,_=self.supervise([0])
        self.assertEqual(spawn.call_count,1)

    def test_repeated_startup_failures_are_bounded(self):
        spawn,events=self.supervise([1,1,1,1])
        self.assertEqual(spawn.call_count,4)
        self.assertEqual(events.call_args.args[0],'recovery_limit_reached')

    def test_recovery_does_not_replace_an_existing_api(self):
        spawn,_=self.supervise([1],info={'pid':999})
        self.assertEqual(spawn.call_count,1)

    def test_intentional_stop_disables_recovery_before_worker_termination(self):
        worker=SimpleNamespace(pid=123)
        order=[]
        with patch.object(service,'prepare'),patch.object(service,'service_event'), \
             patch.object(service,'stop_supervisors',side_effect=lambda:order.append('supervisor')), \
             patch.object(service.psutil,'process_iter',return_value=[worker]), \
             patch.object(service,'owns_backend',return_value=True), \
             patch.object(service,'terminate_tree',side_effect=lambda p:order.append('worker')):
            service.stop()
        self.assertEqual(order,['supervisor','worker'])

    def test_real_failed_child_is_replaced(self):
        with tempfile.TemporaryDirectory() as directory, \
             patch.object(service,'ROOT',Path(directory)), \
             patch.object(service,'service_info',return_value=None), \
             patch.object(service.psutil,'process_iter',return_value=[]), \
             patch.object(service.time,'sleep'):
            root=Path(directory)
            (root/'api_modern.py').write_text(
                "from pathlib import Path\nimport sys\np=Path('attempt')\n"
                "previous=p.exists()\np.write_text('ready')\nsys.exit(0 if previous else 7)\n")
            service.supervise_backend()
            events=[json.loads(line) for line in (root/'logs/service-events.jsonl').read_text().splitlines()]
            exits=[event['exit_code'] for event in events if event['event']=='backend_exited']
            self.assertEqual(exits,[7,0])

    def test_api_restart_helper_carries_generation_and_keeps_errors(self):
        source=ast.parse((service.ROOT/'api_modern.py').read_text(encoding='utf8'))
        function=next(node for node in source.body if isinstance(node,ast.FunctionDef) and node.name=='_launch_service_control')
        for action in ('restart','force-restart','stop'):
            with tempfile.TemporaryDirectory() as directory,patch.object(service,'service_event'):
                root=Path(directory);(root/'logs').mkdir()
                launch=Mock()
                namespace=dict(__file__=str(root/'api_modern.py'),sys=service.sys,os=service.os,
                               time=SimpleNamespace(sleep=Mock()),Path=Path,
                               subprocess=SimpleNamespace(Popen=launch,DEVNULL=-3,STDOUT=-2,
                                   CREATE_NO_WINDOW=0,DETACHED_PROCESS=0,CREATE_NEW_PROCESS_GROUP=0))
                exec(compile(ast.Module(body=[function],type_ignores=[]),'helper-test','exec'),namespace)
                namespace['_launch_service_control'](action)
                self.assertEqual(launch.call_args.args[0][-1],str(service.os.getpid()))
                self.assertEqual(launch.call_args.kwargs['stdout'].name,str(root/'logs/backend.log'))


if __name__=='__main__':unittest.main()
