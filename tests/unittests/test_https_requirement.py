from tap_activecampaign.client import ActiveCampaignClient
import unittest


class TestRequestHTTPSRequirement(unittest.TestCase):
    '''
    Test that the client raises an Exception when the api_url is not https
    '''
    def test_https_requirement(self):
        """
            Unit tests to ensure that request timeout is set based on config value
        """
        config = {"api_url": "http://dummy_url.com", "api_token": "dummy_at", "user_agent": "test_ua", "request_timeout": 100}

        self.assertRaises(Exception, ActiveCampaignClient(**config))
