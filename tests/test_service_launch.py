import unittest
from unittest.mock import patch
import service_control as service


class LaunchTests(unittest.TestCase):
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
