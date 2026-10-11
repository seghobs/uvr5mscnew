import unittest
from unittest.mock import patch,Mock
from tools.atlas_new_models import assert_idle_backend


class IdleBackendTests(unittest.TestCase):
    def test_specific_loopback_service_does_not_hide_uvr_jobs(self):
        foreign=Mock(status_code=404)
        uvr=Mock(status_code=200)
        uvr.json.return_value={'jobs':[{'status':'running'}]}
        with patch('tools.atlas_new_models.requests.Session') as session:
            session.return_value.get.side_effect=[foreign,uvr]
            with self.assertRaisesRegex(RuntimeError,'active'):assert_idle_backend()
            self.assertEqual(session.return_value.get.call_count,2)

    def test_completed_jobs_allow_research_without_starting_services(self):
        uvr=Mock(status_code=200);uvr.json.return_value={'jobs':[{'status':'completed'}]}
        with patch('tools.atlas_new_models.requests.Session') as session:
            session.return_value.get.return_value=uvr
            assert_idle_backend()
            self.assertEqual(session.return_value.get.call_count,1)

if __name__=='__main__':unittest.main()
