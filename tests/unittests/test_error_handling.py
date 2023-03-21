import unittest
from unittest.mock import patch
import requests
from tap_activecampaign import client

# mock responce
class Mockresponse:
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

    def raise_for_status(self):
        if not self.raise_error:
            return self.status_code

        raise requests.HTTPError("mock sample message")

    def json(self):
        return self.text

def mock_send_400(*args, **kwargs):
    return Mockresponse("", 400, raise_error=True)

def mock_send_401(*args, **kwargs):
    return Mockresponse("", 401, raise_error=True)

def mock_send_403(*args, **kwargs):
    return Mockresponse("", 403, raise_error=True)

def mock_send_404(*args, **kwargs):
    return Mockresponse("", 404, raise_error=True)

def mock_send_422(*args, **kwargs):
    error = {
        "errors": [
            {
            "title": "The connection service was not provided."
            },
            {
            "title": "The connection externalid was not provided."
            }
        ]
    }
    return Mockresponse("", 422, raise_error=True, text=error)

def mock_send_429(*args, **kwargs):
    return Mockresponse("", 429, raise_error=True)

def mock_send_500(*args, **kwargs):
    return Mockresponse("", 500, raise_error=True)

def mock_send_501(*args, **kwargs):
    return Mockresponse("", 501, raise_error=True)

def mock_send_502(*args, **kwargs):
    return Mockresponse("", 502, raise_error=True)

class TestActiveCampaignErrorhandlingForRequestMethod(unittest.TestCase):
    """
    Test error handling for `request` method
    """
    @patch("tap_activecampaign.client.ActiveCampaignClient.check_api_token")
    @patch("requests.Session.request", side_effect=mock_send_400)
    def test_request_with_handling_for_400_exception_handling(self, mocked_request, mock_api_token):
        """
        Test that `request` method raise 400 error with proper message
        """
        _client = client.ActiveCampaignClient('dummy_url', 'dummy_token')
        
        expected_error_message = "HTTP-error-code: 400, Error: A validation exception has occurred."

        with self.assertRaises(client.ActiveCampaignBadRequestError) as e:
            _client.request("base_url")
            
        # Verifying the message formed for the custom exception
        self.assertEqual(str(e.exception), expected_error_message)

    @patch("tap_activecampaign.client.ActiveCampaignClient.check_api_token")
    @patch("requests.Session.request", side_effect=mock_send_401)
    def test_request_with_handling_for_401_exception_handling(self, mocked_request, mock_api_token):
        """
        Test that `request` method raise 401 error with proper message
        """
        _client = client.ActiveCampaignClient('dummy_url', 'dummy_token')
        
        expected_error_message = "HTTP-error-code: 401, Error: Invalid authorization credentials."
    
        with self.assertRaises(client.ActiveCampaignUnauthorizedError) as e:
            _client.request("base_url")
            
        # Verifying the message formed for the custom exception
        self.assertEqual(str(e.exception), expected_error_message)


    @patch("tap_activecampaign.client.ActiveCampaignClient.check_api_token")
    @patch("requests.Session.request", side_effect=mock_send_403)
    def test_request_with_handling_for_403_exception_handling(self, mocked_request, mock_api_token):
        """
        Test that `request` method raise 403 error with proper message
        """
        _client = client.ActiveCampaignClient('dummy_url', 'dummy_token')

        expected_error_message = "HTTP-error-code: 403, Error: The request could not be authenticated or the authenticated user is not authorized to access the requested resource."
    
        with self.assertRaises(client.ActiveCampaignForbiddenError) as e:
            _client.request("base_url")
            
        # Verifying the message formed for the custom exception
        self.assertEqual(str(e.exception), expected_error_message)


    @patch("tap_activecampaign.client.ActiveCampaignClient.check_api_token")
    @patch("requests.Session.request", side_effect=mock_send_404)
    def test_request_with_handling_for_404_exception_handling(self, mocked_request, mock_api_token):
        """
        Test that `request` method raise 404 error with proper message
        """
        _client = client.ActiveCampaignClient('dummy_url', 'dummy_token')

        expected_error_message = "HTTP-error-code: 404, Error: The requested resource does not exist."
    
        with self.assertRaises(client.ActiveCampaignNotFoundError) as e:
            _client.request("base_url")
            
        # Verifying the message formed for the custom exception
        self.assertEqual(str(e.exception), expected_error_message)


    @patch("tap_activecampaign.client.ActiveCampaignClient.check_api_token")
    @patch("requests.Session.request", side_effect=mock_send_422)
    def test_request_with_handling_for_422_exception_handling(self, mocked_request, mock_api_token):
        """
        Test that `request` method raise 422 error with proper message comes from API response.
        """
        _client = client.ActiveCampaignClient('dummy_url', 'dummy_token')

        expected_error_message = "HTTP-error-code: 422, Error: The connection service was not provided. The connection externalid was not provided."
    
        with self.assertRaises(client.ActiveCampaignUnprocessableEntityError) as e:
            _client.request("base_url")
            
        # Verifying the message formed for the custom exception
        self.assertEqual(str(e.exception), expected_error_message)


    @patch("time.sleep")
    @patch("tap_activecampaign.client.ActiveCampaignClient.check_api_token")
    @patch("requests.Session.request", side_effect=mock_send_429)
    def test_request_with_handling_for_429_exception_handling(self, mocked_request, mock_api_token, mock_sleep):
        """
        Test that `request` method raise 429 error with proper message
        """
        _client = client.ActiveCampaignClient('dummy_url', 'dummy_token')

        expected_error_message = "HTTP-error-code: 429, Error: The user has sent too many requests in a given amount of time ('rate limiting') - contact support or account manager for more details."
    
        with self.assertRaises(client.ActiveCampaignRateLimitError) as e:
            _client.request("base_url")
            
        # Verifying the message formed for the custom exception
        self.assertEqual(str(e.exception), expected_error_message)


    @patch("time.sleep")
    @patch("tap_activecampaign.client.ActiveCampaignClient.check_api_token")
    @patch("requests.Session.request", side_effect=mock_send_500)
    def test_request_with_handling_for_500_exception_handling(self, mocked_request, mock_api_token, mock_sleep):
        """
        Test that `request` method raise 500 error with proper message
        """
        _client = client.ActiveCampaignClient('dummy_url', 'dummy_token')

        expected_error_message = "HTTP-error-code: 500, Error: The server encountered an unexpected condition which prevented" \
            " it from fulfilling the request."    
        with self.assertRaises(client.ActiveCampaignInternalServerError) as e:
            _client.request("base_url")
            
        # Verifying the message formed for the custom exception
        self.assertEqual(str(e.exception), expected_error_message)


    @patch("time.sleep")
    @patch("tap_activecampaign.client.ActiveCampaignClient.check_api_token")
    @patch("requests.Session.request", return_value=Mockresponse("", 200, content=b""))
    def test_request_with_handling_for_empty_content(self, mocked_request, mock_api_token, mock_sleep):
        """
        Test that `request` method gives empty json `{}` response when content is empty for a 200 response.
        """
        _client = client.ActiveCampaignClient('dummy_url', 'dummy_token')

        response = _client.request("base_url")

        # Verifying the empty response
        self.assertEqual({}, response)


class TestActiveCampaignErrorhandlingForCheckApiTokenMethod(unittest.TestCase):

    @patch("requests.Session.get", side_effect=mock_send_400)
    def test_request_with_handling_for_400_exception_handling(self, mocked_request):
        """
        Test that `__enter__` method raise 400 error with proper message
        """
        _client = client.ActiveCampaignClient('dummy_url', 'dummy_token')

        expected_error_message = "HTTP-error-code: 400, Error: A validation exception has occurred."
    
        with self.assertRaises(client.ActiveCampaignBadRequestError) as e:
            _client.__enter__()
            
        # Verifying the message formed for the custom exception
        self.assertEqual(str(e.exception), expected_error_message)


    @patch("requests.Session.get", side_effect=mock_send_401)
    def test_request_with_handling_for_401_exception_handling(self, mocked_request):
        """
        Test that `__enter__` method raise 401 error with proper message
        """
        _client = client.ActiveCampaignClient('dummy_url', 'dummy_token')

        expected_error_message = "HTTP-error-code: 401, Error: Invalid authorization credentials."
    
        with self.assertRaises(client.ActiveCampaignUnauthorizedError) as e:
            _client.__enter__()
            
        # Verifying the message formed for the custom exception
        self.assertEqual(str(e.exception), expected_error_message)

    @patch("requests.Session.get", side_effect=mock_send_403)
    def test_request_with_handling_for_403_exception_handling(self, mocked_request):
        """
        Test that `__enter__` method raise 403 error with proper message
        """
        _client = client.ActiveCampaignClient('dummy_url', 'dummy_token')

        expected_error_message = "HTTP-error-code: 403, Error: The request could not be authenticated or the authenticated user is not authorized to access the requested resource."
    
        with self.assertRaises(client.ActiveCampaignForbiddenError) as e:
            _client.__enter__()
            
        # Verifying the message formed for the custom exception
        self.assertEqual(str(e.exception), expected_error_message)


    @patch("requests.Session.get", side_effect=mock_send_404)
    def test_request_with_handling_for_404_exception_handling(self, mocked_request):
        """
        Test that `__enter__` method raise 404 error with proper message
        """
        _client = client.ActiveCampaignClient('dummy_url', 'dummy_token')

        expected_error_message = "HTTP-error-code: 404, Error: The requested resource does not exist."
    
        with self.assertRaises(client.ActiveCampaignNotFoundError) as e:
            _client.__enter__()
            
        # Verifying the message formed for the custom exception
        self.assertEqual(str(e.exception), expected_error_message)


    @patch("requests.Session.get", side_effect=mock_send_422)
    def test_request_with_handling_for_422_exception_handling(self, mocked_request):
        """
        Test that `__enter__` method raise 422 error with proper message comes from API response.
        """
        _client = client.ActiveCampaignClient('dummy_url', 'dummy_token')

        expected_error_message = "HTTP-error-code: 422, Error: The connection service was not provided. The connection externalid was not provided."
    
        with self.assertRaises(client.ActiveCampaignUnprocessableEntityError) as e:
            _client.__enter__()
            
        # Verifying the message formed for the custom exception
        self.assertEqual(str(e.exception), expected_error_message)

    @patch("time.sleep")
    @patch("requests.Session.get", side_effect=mock_send_429)
    def test_request_with_handling_for_429_exception_handling(self, mocked_request, mock_sleep):
        """
        Test that `__enter__` method raise 429 error with proper message
        """
        _client = client.ActiveCampaignClient('dummy_url', 'dummy_token')

        expected_error_message = "HTTP-error-code: 429, Error: The user has sent too many requests in a given amount of time ('rate limiting') - contact support or account manager for more details."
    
        with self.assertRaises(client.ActiveCampaignRateLimitError) as e:
            _client.__enter__()
            
        # Verifying the message formed for the custom exception
        self.assertEqual(str(e.exception), expected_error_message)


    @patch("time.sleep")
    @patch("requests.Session.get", side_effect=mock_send_500)
    def test_request_with_handling_for_500_exception_handling(self, mocked_request, mock_sleep):
        """
        Test that `__enter__` method raise 500 error with proper message
        """
        _client = client.ActiveCampaignClient('dummy_url', 'dummy_token')

        expected_error_message = "HTTP-error-code: 500, Error: The server encountered an unexpected condition which prevented" \
            " it from fulfilling the request."    
        with self.assertRaises(client.ActiveCampaignInternalServerError) as e:
            _client.__enter__()
            
        # Verifying the message formed for the custom exception
        self.assertEqual(str(e.exception), expected_error_message)

@patch("time.sleep")
class TestActiveCampaignErrorhandlingBackoff(unittest.TestCase):
    """
    Test that tap perform backoff on 429, 5xx, ConnectionError and ConnectionResetError Exception.
    """

    @patch("requests.Session.get", side_effect=mock_send_429)
    def test_enter_method_handle_429_exception(self, mocked_request, mock_sleep):
        """
        Test that `__enter__` method retry 429 error 5 times
        """
        _client = client.ActiveCampaignClient('dummy_url', 'dummy_token')
    
        with self.assertRaises(client.ActiveCampaignRateLimitError) as e:
            _client.__enter__()
            
        # Verify that requests.Session.get called 5 times
        self.assertEqual(mocked_request.call_count, 5)


    @patch("requests.Session.get", side_effect=mock_send_500)
    def test_enter_method_handle_500_exception(self, mocked_request, mock_sleep):
        """
        Test that `__enter__` method retry 500 error 5 times
        """
        _client = client.ActiveCampaignClient('dummy_url', 'dummy_token')
    
        with self.assertRaises(client.ActiveCampaignInternalServerError) as e:
            _client.__enter__()
            
        # Verify that requests.Session.get called 5 times
        self.assertEqual(mocked_request.call_count, 5)

    @patch("requests.Session.get", side_effect=mock_send_501)
    def test_enter_method_handle_501_exception(self, mocked_request, mock_sleep):
        """
        Test that `__enter__` method retry 501 error 5 times
        """
        _client = client.ActiveCampaignClient('dummy_url', 'dummy_token')

        with self.assertRaises(client.Server5xxError) as e:
            _client.__enter__()
            
        # Verify that requests.Session.get called 5 times
        self.assertEqual(mocked_request.call_count, 5)

    @patch("requests.Session.get", side_effect=mock_send_502)
    def test_enter_method_handle_502_exception(self, mocked_request, mock_sleep):
        """
        Test that `__enter__` method retry 502 error 5 times
        """
        _client = client.ActiveCampaignClient('dummy_url', 'dummy_token')
    
        with self.assertRaises(client.Server5xxError) as e:
            _client.__enter__()
            
        # Verify that requests.Session.get called 5 times
        self.assertEqual(mocked_request.call_count, 5)

    @patch("requests.Session.get", side_effect=mock_send_401)
    def test_enter_method_does_not_retry_401_error(self, mocked_request, mock_sleep):
        """
        Test that `__enter__` method does not retry 401 error.
        """
        _client = client.ActiveCampaignClient('dummy_url', 'dummy_token')
    
        with self.assertRaises(client.ActiveCampaignUnauthorizedError) as e:
            _client.__enter__()
            
        # Verify that requests.Session.get called just 1 time
        self.assertEqual(mocked_request.call_count, 1)
            
    @patch("requests.Session.get", side_effect=requests.exceptions.ConnectionError)
    def test_enter_method_handle_connection_error(self, mocked_request, mock_sleep):
        """
        Test that `__enter__` method retry Connection error 5 times.
        """
        _client = client.ActiveCampaignClient('dummy_url', 'dummy_token')
    
        with self.assertRaises(requests.exceptions.ConnectionError) as e:
            _client.__enter__()
            
        # Verify that requests.Session.get called 5 times
        self.assertEqual(mocked_request.call_count, 5)

    @patch("requests.Session.get", side_effect=Exception(("Connection broken: ConnectionResetError(104, 'Connection reset by peer')", ConnectionResetError(104, 'Connection reset by peer'))))
    def test_enter_method_handle_connection_reset_exception(self, mocked_request, mock_sleep):
        """
        Test that `__enter__` method retry Connection error(104) with Exception 5 times.
        """
        _client = client.ActiveCampaignClient('dummy_url', 'dummy_token')
        
        with self.assertRaises(Exception) as e:
            _client.__enter__()

        # Verify that requests.Session.get called 5 times
        self.assertEqual(mocked_request.call_count, 5)

    @patch("requests.Session.get", side_effect=ConnectionResetError(104, 'Connection reset by peer'))
    def test_enter_method_handle_connection_reset_error(self, mocked_request, mock_sleep):
        """
        Test that `__enter__` method retry ConnectionResetError(104) with Exception 5 times.
        """
        _client = client.ActiveCampaignClient('dummy_url', 'dummy_token')

        with self.assertRaises(ConnectionResetError) as e:
            _client.__enter__()

        # Verify that requests.Session.get called 5 times
        self.assertEqual(mocked_request.call_count, 5)

    @patch("tap_activecampaign.client.ActiveCampaignClient.check_api_token")    
    @patch("requests.Session.request", side_effect=mock_send_429)
    def test_request_method_handle_429_exception(self, mocked_request, mock_api_token, mock_sleep):
        """
        Test that `request` method retry 429 error 5 times
        """
        _client = client.ActiveCampaignClient('dummy_url', 'dummy_token')
    
        with self.assertRaises(client.ActiveCampaignRateLimitError) as e:
            _client.request("base_url")
            
        # Verify that requests.Session.request called 5 times
        self.assertEqual(mocked_request.call_count, 5)

    @patch("tap_activecampaign.client.ActiveCampaignClient.check_api_token") 
    @patch("requests.Session.request", side_effect=mock_send_500)
    def test_request_method_handle_500_exception(self, mocked_request, mock_api_token, mock_sleep):
        """
        Test that `request` method retry 500 error 5 times
        """
        _client = client.ActiveCampaignClient('dummy_url', 'dummy_token')
    
        with self.assertRaises(client.ActiveCampaignInternalServerError) as e:
            _client.request("base_url")
            
        # Verify that requests.Session.request called 5 times
        self.assertEqual(mocked_request.call_count, 5)

    @patch("tap_activecampaign.client.ActiveCampaignClient.check_api_token") 
    @patch("requests.Session.request", side_effect=mock_send_501)
    def test_request_method_handle_501_exception(self, mocked_request, mock_api_token, mock_sleep):
        """
        Test that `request` method retry 501 error 5 times
        """
        _client = client.ActiveCampaignClient('dummy_url', 'dummy_token')
    
        with self.assertRaises(client.Server5xxError) as e:
            _client.request("base_url")
            
        # Verify that requests.Session.request called 5 times
        self.assertEqual(mocked_request.call_count, 5)

    @patch("tap_activecampaign.client.ActiveCampaignClient.check_api_token") 
    @patch("requests.Session.request", side_effect=mock_send_502)
    def test_request_method_handle_502_exception(self, mocked_request, mock_api_token, mock_sleep):
        """
        Test that `request` method retry 502 error 5 times
        """
        _client = client.ActiveCampaignClient('dummy_url', 'dummy_token')
    
        with self.assertRaises(client.Server5xxError) as e:
            _client.request("base_url")
            
        # Verify that requests.Session.request called 5 times
        self.assertEqual(mocked_request.call_count, 5)

    @patch("tap_activecampaign.client.ActiveCampaignClient.check_api_token") 
    @patch("requests.Session.request", side_effect=mock_send_401)
    def test_request_method_does_not_retry_401_error(self, mocked_request, mock_api_token, mock_sleep):
        """
        Test that `request` method does not retry 401 error.
        """
        _client = client.ActiveCampaignClient('dummy_url', 'dummy_token')
    
        with self.assertRaises(client.ActiveCampaignUnauthorizedError) as e:
            _client.request("base_url")
            
        # Verify that requests.Session.request called just 1 time
        self.assertEqual(mocked_request.call_count, 1)

    @patch("tap_activecampaign.client.ActiveCampaignClient.check_api_token")     
    @patch("requests.Session.request", side_effect=requests.exceptions.ConnectionError)
    def test_request_method_handle_connection_error(self, mocked_request, mock_api_token, mock_sleep):
        """
        Test that `request` method retry Connection error 5 times.
        """
        _client = client.ActiveCampaignClient('dummy_url', 'dummy_token')
    
        with self.assertRaises(requests.exceptions.ConnectionError) as e:
            _client.request("base_url")
            
        # Verify that requests.Session.request called 5 times
        self.assertEqual(mocked_request.call_count, 5)

    @patch("tap_activecampaign.client.ActiveCampaignClient.check_api_token") 
    @patch("requests.Session.request", side_effect=Exception(("Connection broken: ConnectionResetError(104, 'Connection reset by peer')", ConnectionResetError(104, 'Connection reset by peer'))))
    def test_request_method_handle_connection_reset_exception(self, mocked_request, mock_api_token, mock_sleep):
        """
        Test that `request` method retry Connection error(104) with Exception 5 times.
        """
        _client = client.ActiveCampaignClient('dummy_url', 'dummy_token')
    
        with self.assertRaises(Exception) as e:
            _client.request("base_url")

        # Verify that requests.Session.request called 5 times
        self.assertEqual(mocked_request.call_count, 5)

    @patch("tap_activecampaign.client.ActiveCampaignClient.check_api_token")
    @patch("requests.Session.request", side_effect=ConnectionResetError(104, 'Connection reset by peer'))
    def test_request_method_handle_connection_reset_error(self, mocked_request, mock_api_token, mock_sleep):
        """
        Test that `request` method retry ConnectionResetError(104) with Exception 5 times.
        """
        _client = client.ActiveCampaignClient('dummy_url', 'dummy_token')

        with self.assertRaises(ConnectionResetError) as e:
            _client.request("base_url")

        # Verify that requests.Session.request called 5 times
        self.assertEqual(mocked_request.call_count, 5)
