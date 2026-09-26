import threading
import unittest
from unittest.mock import patch

import api_modern


class GpuLifecycleTests(unittest.TestCase):
    def setUp(self):
        with api_modern._gpu_activity_lock:
            api_modern._cancel_gpu_idle_shutdown()
            api_modern._gpu_active_operations = 0

    def tearDown(self):
        with api_modern._gpu_activity_lock:
            api_modern._cancel_gpu_idle_shutdown()

    def test_cleanup_waits_for_the_last_concurrent_gpu_operation(self):
        first_started = threading.Event()
        second_started = threading.Event()
        release_first = threading.Event()
        release_second = threading.Event()

        @api_modern.gpu_operation
        def work(started, release):
            started.set()
            release.wait(2)

        with patch.object(api_modern, '_release_all_gpu_resources') as cleanup:
            first = threading.Thread(target=work, args=(first_started, release_first))
            second = threading.Thread(target=work, args=(second_started, release_second))
            first.start(); second.start()
            self.assertTrue(first_started.wait(1))
            self.assertTrue(second_started.wait(1))
            release_first.set(); first.join(1)
            cleanup.assert_not_called()
            release_second.set(); second.join(1)
            cleanup.assert_called_once_with()

    def test_cleanup_runs_when_gpu_operation_fails(self):
        @api_modern.gpu_operation
        def fail():
            raise RuntimeError('test')

        with patch.object(api_modern, '_release_all_gpu_resources') as cleanup:
            with self.assertRaises(RuntimeError):
                fail()
            cleanup.assert_called_once_with()

    def test_idle_backend_restart_releases_the_cuda_process(self):
        restarted = threading.Event()

        @api_modern.gpu_operation
        def work():
            return 'done'

        with patch.object(api_modern, 'GPU_IDLE_SHUTDOWN_SECONDS', .01), \
             patch.object(api_modern, '_release_all_gpu_resources'), \
             patch.object(api_modern, '_launch_service_control', side_effect=lambda action: restarted.set()):
            self.assertEqual(work(), 'done')
            self.assertTrue(restarted.wait(1))


if __name__ == '__main__':
    unittest.main()
