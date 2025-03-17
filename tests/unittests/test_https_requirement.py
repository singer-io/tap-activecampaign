from tap_activecampaign.client import ActiveCampaignClient
import unittest


class TestRequestHTTPSRequirement(unittest.TestCase):
    def test_https_requirement(self):
        '''
        Test that the client raises an Exception when the api_url is not https
        '''
        config = {"api_url": "http://activecampaign.com", "api_token": "dummy_at", "user_agent": "test_ua", "request_timeout": 100}
        with self.assertRaises(Exception):
            ActiveCampaignClient(**config)
