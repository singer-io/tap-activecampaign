from tap_activecampaign.client import ActiveCampaignClient
import unittest
from unittest import mock
from requests.exceptions import Timeout, ConnectionError

class TestBackoffError(unittest.TestCase):
    '''
    Test that backoff logic works properly.
    '''
    @mock.patch('tap_activecampaign.client.requests.Session.request')
    @mock.patch('tap_activecampaign.client.ActiveCampaignClient.check_api_token')
    def test_request_timeout_and_backoff(self, mock_get_token, mock_request):
        """
        Check whether the request backoffs properly for request() for 5 times in case of Timeout error.
        """
        mock_request.side_effect = Timeout
        client = ActiveCampaignClient("dummy_client_id", "dummy_client_secret", "dummy_refresh_token", 300)
        with self.assertRaises(Timeout):
            client.request("GET")
        self.assertEquals(mock_request.call_count, 5)

    @mock.patch('tap_activecampaign.client.requests.Session.request')
    def test_check_api_token_timeout_and_backoff(self, mocked_request):
        """
        Check whether the request backoffs properly for __enter__() for 5 times in case of Timeout error.
        """
        mocked_request.side_effect = Timeout

        config = {
            "api_url": "http://dummy_url.com",
            "api_token": "dummy_cs",
            "user_agent": "test_ua"
        }
        # initialize 'ActiveCampaignClient'
        try:
            with ActiveCampaignClient(config['api_url'],
                                      config['api_token'],
                                      config['user_agent'],
                                      config.get('request_timeout')) as client:
                pass
        except Timeout:
            # verify that we backoff for 5 times
            self.assertEquals(mocked_request.call_count, 5)
        
    @mock.patch('tap_activecampaign.client.requests.Session.request')
    def test_check_api_token_connection_error_and_backoff(self, mocked_request):
        """
        Check whether the request backoffs properly for __enter__() for 5 times in case of Timeout error.
        """
        mocked_request.side_effect = ConnectionError

        config = {
            "api_url": "http://dummy_url.com",
            "api_token": "dummy_cs",
            "user_agent": "test_ua"
        }
        # initialize 'ActiveCampaignClient'
        try:
            with ActiveCampaignClient(config['api_url'],
                                      config['api_token'],
                                      config['user_agent'],
                                      config.get('request_timeout')) as client:
                pass
        except ConnectionError:
            # verify that we backoff for 5 times
            self.assertEquals(mocked_request.call_count, 5)

class MockResponse():
    '''
    Mock response  object for the requests call 
    '''
    def __init__(self, resp, status_code, content=[""], headers=None, raise_error=False, text={}):
        self.json_data = resp
        self.status_code = status_code
        self.content = content
        self.headers = headers
        self.raise_error = raise_error
        self.text = text
        self.reason = "error"

    def prepare(self):
        return (self.json_data, self.status_code, self.content, self.headers, self.raise_error)

    def json(self):
        return self.text

class TestRequestTimeoutValue(unittest.TestCase):
    '''
    Test that request timeout parameter works properly in various cases
    '''
    @mock.patch('tap_activecampaign.client.requests.Session.request', return_value = MockResponse("", status_code=200))
    @mock.patch('tap_activecampaign.client.ActiveCampaignClient.check_api_token')
    def test_config_provided_request_timeout(self, mock_get, mock_request):
        """ 
            Unit tests to ensure that request timeout is set based on config value
        """
        config = {"api_url": "http://dummy_url.com", "api_token": "dummy_at", "user_agent": "test_ua", "request_timeout": 100}
        client = ActiveCampaignClient(**config)
        client.request("GET", "dummy_path")
        
        mock_request.assert_called_with('GET', 'http://dummy_url.com/api/3/dummy_path', stream=True, timeout=100.0, headers={'Api-Token': 'dummy_at', 'Accept': 'application/json', 'User-Agent': 'test_ua'})

    @mock.patch('tap_activecampaign.client.requests.Session.request', return_value = MockResponse("", status_code=200))
    @mock.patch('tap_activecampaign.client.ActiveCampaignClient.check_api_token')
    def test_default_value_request_timeout(self, mock_get, mock_request):
        """ 
            Unit tests to ensure that request timeout is set based default value
        """
        config = {"api_url": "http://dummy_url.com", "api_token": "dummy_at", "user_agent": "test_ua"}
        client = ActiveCampaignClient(**config)
        client.request("GET", "dummy_path")
        
        mock_request.assert_called_with('GET', 'http://dummy_url.com/api/3/dummy_path', stream=True, timeout=300, headers={'Api-Token': 'dummy_at', 'Accept': 'application/json', 'User-Agent': 'test_ua'})

    @mock.patch('tap_activecampaign.client.requests.Session.request', return_value = MockResponse("", status_code=200))
    @mock.patch('tap_activecampaign.client.ActiveCampaignClient.check_api_token')
    def test_config_provided_empty_request_timeout(self, mock_get, mock_request):
        """ 
            Unit tests to ensure that request timeout is set based on default value if empty value is given in config
        """
        config = {"api_url": "http://dummy_url.com", "api_token": "dummy_at", "user_agent": "test_ua", "request_timeout": ""}
        client = ActiveCampaignClient(**config)
        client.request("GET", "dummy_path")
        
        mock_request.assert_called_with('GET', 'http://dummy_url.com/api/3/dummy_path', stream=True, timeout=300.0, headers={'Api-Token': 'dummy_at', 'Accept': 'application/json', 'User-Agent': 'test_ua'})

    @mock.patch('tap_activecampaign.client.requests.Session.request', return_value = MockResponse("", status_code=200))
    @mock.patch('tap_activecampaign.client.ActiveCampaignClient.check_api_token')
    def test_config_provided_string_request_timeout(self, mock_get, mock_request):
        """ 
            Unit tests to ensure that request timeout is set based on config string value
        """
        config = {"api_url": "http://dummy_url.com", "api_token": "dummy_at", "user_agent": "test_ua", "request_timeout": "100"}
        client = ActiveCampaignClient(**config)
        client.request("GET", "dummy_path")
        
        mock_request.assert_called_with('GET', 'http://dummy_url.com/api/3/dummy_path', stream=True, timeout=100.0, headers={'Api-Token': 'dummy_at', 'Accept': 'application/json', 'User-Agent': 'test_ua'})

    @mock.patch('tap_activecampaign.client.requests.Session.request', return_value = MockResponse("", status_code=200))
    @mock.patch('tap_activecampaign.client.ActiveCampaignClient.check_api_token')
    def test_config_provided_float_request_timeout(self, mock_get, mock_request):
        """ 
            Unit tests to ensure that request timeout is set based on config float value
        """
        config = {"api_url": "http://dummy_url.com", "api_token": "dummy_at", "user_agent": "test_ua", "request_timeout": 100.5}
        client = ActiveCampaignClient(**config)
        client.request("GET", "dummy_path")
        
        mock_request.assert_called_with('GET', 'http://dummy_url.com/api/3/dummy_path', stream=True, timeout=100.5, headers={'Api-Token': 'dummy_at', 'Accept': 'application/json', 'User-Agent': 'test_ua'})
