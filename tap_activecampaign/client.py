import asyncio
import json
import backoff
import ipaddress
import threading
import time
from collections import deque
from urllib.parse import urlparse
import socket
import aiohttp
import requests
from yarl import URL
from singer import metrics
import singer

from tap_activecampaign.exceptions import (
    Server5xxError,
    Server429Error,
    ActiveCampaignError,
    ActiveCampaignBadRequestError,
    ActiveCampaignUnauthorizedError,
    ActiveCampaignForbiddenError,
    ActiveCampaignNotFoundError,
    ActiveCampaignUnprocessableEntityError,
    ActiveCampaignRateLimitError,
    ActiveCampaignInternalServerError,
    STATUS_CODE_EXCEPTION_MAPPING,
)


LOGGER = singer.get_logger()
REQUEST_TIMEOUT = 300

DEFAULT_API_VERSION = '3'


class RateLimiter:
    """Allow `limit` request starts per `every` seconds, shared by threads and asyncio tasks."""

    def __init__(self, limit, every):
        self._every = every
        self._starts = deque(maxlen=limit)
        self._lock = threading.Lock()

    def _reserve(self):
        """Book the next free start time and return how long to wait for it."""
        # The lock is only held for this bookkeeping, never while sleeping, so it is safe in an event loop.
        with self._lock:
            now = time.monotonic()
            start = now
            if len(self._starts) == self._starts.maxlen:
                start = max(now, self._starts[0] + self._every)
            self._starts.append(start)
        return start - now

    def wait(self):
        # singer's utils.ratelimit is not thread-safe, and parallel contact requests share the limit.
        delay = self._reserve()
        if delay > 0:
            time.sleep(delay)

    async def wait_async(self):
        delay = self._reserve()
        if delay > 0:
            await asyncio.sleep(delay)


# Rate limit: https://developers.activecampaign.com/reference/rate-limits
REQUEST_LIMITER = RateLimiter(5, 1)

def should_retry_error(exception):
    """
        Return true if exception is required to retry otherwise return false
    """

    if isinstance(exception, OSError) or isinstance(exception, Server5xxError) or \
        isinstance(exception, Server429Error) or isinstance(exception, ActiveCampaignForbiddenError):
        # Retry Server5xxError and Server429Error exception. Retry exception if it is child class of OSError.
        # OSError is Parent class of ConnectionError, ConnectionResetError, TimeoutError and other errors mentioned in https://docs.python.org/3/library/exceptions.html#os-exceptions
        # Retry ActiveCampaignForbiddenError as the source raises 403 Authentication issues intermittently
        return True
    elif type(exception) == Exception and type(exception.args[0][1]) == ConnectionResetError:
        # Tap raises Exception: ConnectionResetError(104, 'Connection reset by peer'). That's why we are retrying this error also.
        # Reference: https://app.circleci.com/pipelines/github/singer-io/tap-activecampaign/554/workflows/d448258e-20df-4e66-b2aa-bc8bd1f08912/jobs/558
        return True
    elif type(exception) == ConnectionResetError:
        return True
    elif isinstance(exception, aiohttp.ClientConnectionError):
        # aiohttp's dropped-connection errors (e.g. ServerDisconnectedError) are not OSErrors.
        return True
    else:
        return False

def get_exception_for_status_code(status_code):
    # Map the status code with `STATUS_CODE_EXCEPTION_MAPPING` dictionary and accordingly return the error.
    if status_code > 500:
        # Raise Server5xxError if status code is greater than 500
        return Server5xxError

    return STATUS_CODE_EXCEPTION_MAPPING.get(status_code, {}).get("raise_exception", ActiveCampaignError)

# Example 422 error
# {
#   "errors": [
#     {
#       "title": "The connection service was not provided."
#     },
#     {
#       "title": "The connection externalid was not provided."
#     }
#   ]
# }
def raise_for_error(response):
    # If the response contains an `errors` object with multiple errors, prepare an error message containing the title of all errors in the `errors` object.
    # Otherwise prepare a custom default message and raise the exception.

    try:
        response_json = response.json() # retrieve json response
    except Exception:
        response_json = {}
    raise error_for_status(response.status_code, response_json) from None

def error_for_status(status_code, response_json):
    """Build the exception for an error response; shared by the requests and aiohttp clients."""
    if not isinstance(response_json, dict):
        response_json = {}
    errors = response_json.get('errors', [])
    if errors: # response containing `errors` object
        message = 'HTTP-error-code: {}, Error:'.format(status_code)
        # loop through all errors
        for error in errors:
            title = error.get('title')
            message = '{} {}'.format(message, title)
    else:
        # prepare custom default error message
        message = "HTTP-error-code: {}, Error: {}".format(status_code,
                response_json.get("message", STATUS_CODE_EXCEPTION_MAPPING.get(
                status_code, {}).get("message", "Unknown Error")))

    exc = get_exception_for_status_code(status_code)

    return exc(message)

def is_api_url_valid(api_url):
    parsed_url = urlparse(api_url)

    if parsed_url.scheme != "https":
        return False

    try:
        # Ensure the hostname is not an IP address
        ip = ipaddress.ip_address(parsed_url.hostname)
        # Reject if the IP address is private
        if ip.is_private:
            return False
    except ValueError:
        # If the hostname is not an IP address, resolve it to check if it points to a private IP
        try:
            resolved_ip = ipaddress.ip_address(socket.gethostbyname(parsed_url.hostname))
            if resolved_ip.is_private:
                return False
        except ValueError:
            return False

    return True


class ActiveCampaignClient(object):
    def __init__(self,
                 api_url,
                 api_token,
                 user_agent=None,
                 request_timeout=None):
        self.__api_url = api_url
        self.__api_token = api_token
        self.__user_agent = user_agent
        self.__session = requests.Session()
        self.__verified = False
        self.base_url = '{}/api/{}/'.format(self.__api_url, DEFAULT_API_VERSION)

        if not is_api_url_valid(api_url):
            raise Exception('Error: api_url is not valid')

        # if request_timeout is other than 0, "0" or "" then use request_timeout
        if request_timeout and float(request_timeout):
            self.request_timeout = float(request_timeout)
        else: # If value is 0, "0" or "" then set default to 300 seconds.
            self.request_timeout = REQUEST_TIMEOUT

    # Backoff for Server5xxError, Server429Error, OSError and Exception with ConnectionResetError.
    @backoff.on_exception(backoff.expo,
                          (Exception),
                          giveup=lambda e: not should_retry_error(e),
                          max_tries=5,
                          factor=2)
    def __enter__(self):
        self.__verified = self.check_api_token()
        return self

    def __exit__(self, exception_type, exception_value, traceback):
        self.__session.close()

    def async_client(self, max_connections):
        """An aiohttp client with the same credentials, timeout and rate limit, for concurrent requests."""
        return AsyncActiveCampaignClient(
            self.__api_url, self.__api_token, self.__user_agent, self.request_timeout, max_connections)

    def check_api_token(self):
        if self.__api_token is None:
            raise Exception('Error: Missing api_token.')
        headers = {}
        if self.__user_agent:
            headers['User-Agent'] = self.__user_agent
        headers['Api-Token'] = self.__api_token
        headers['Accept'] = 'application/json'
        url = self.base_url + 'users/me'
        response = self.__session.get(
            # Simple endpoint that returns 1 record w/ default organization URN
            url=url,
            headers=headers,
            timeout=self.request_timeout)
        if response.status_code != 200:
            raise_for_error(response)
        else:
            return True

    # Backoff for Server5xxError, Server429Error, OSError and Exception with ConnectionResetError.
    @backoff.on_exception(backoff.expo,
                          (Exception),
                          giveup=lambda e: not should_retry_error(e),
                          max_tries=5,
                          factor=2)
    def request(self, method, path=None, url=None, api_version=None, **kwargs):
        REQUEST_LIMITER.wait()
        if not self.__verified:
            self.__verified = self.check_api_token()

        if not api_version:
            api_version = DEFAULT_API_VERSION

        if not url and path:
            url = '{}/api/{}/{}'.format(self.__api_url, api_version, path)

        if 'endpoint' in kwargs:
            endpoint = kwargs['endpoint']
            del kwargs['endpoint']
        else:
            endpoint = None

        if 'headers' not in kwargs:
            kwargs['headers'] = {}
        kwargs['headers']['Api-Token'] = self.__api_token
        kwargs['headers']['Accept'] = 'application/json'

        if self.__user_agent:
            kwargs['headers']['User-Agent'] = self.__user_agent

        if method == 'POST':
            kwargs['headers']['Content-Type'] = 'application/json'

        with metrics.http_request_timer(endpoint) as timer:
            response = self.__session.request(method, url, stream=True, timeout=self.request_timeout, **kwargs)
            timer.tags[metrics.Tag.http_status_code] = response.status_code

        if response.status_code != 200:
            raise_for_error(response)

        # Log invalid JSON (e.g. unterminated string errors)
        try:
            response_json = response.json()
        except Exception as err:
            LOGGER.error('{}'.format(err))
            LOGGER.error('response content: {}'.format(response.content))
            if response.content != b"":
                raise err

            # Handling empty response b'' given by ActiveCampaign APIs
            response_json = {}

        return response_json

    def get(self, path, api_version=None, **kwargs):
        return self.request('GET', path=path, api_version=api_version, **kwargs)

    def post(self, path, api_version=None, **kwargs):
        return self.request('POST', path=path, api_version=api_version, **kwargs)


class AsyncActiveCampaignClient:
    """
    asyncio counterpart of ActiveCampaignClient.get, used to request several contacts at the same time.
    It shares REQUEST_LIMITER with the requests-based client, and maps errors and retries the same way.
    Create it from ActiveCampaignClient.async_client() (which has already checked the token) and use it
    as an async context manager inside a running event loop.
    """

    def __init__(self, api_url, api_token, user_agent, request_timeout, max_connections):
        self.base_url = '{}/api/{}/'.format(api_url, DEFAULT_API_VERSION)
        self._api_url = api_url
        self._headers = {'Api-Token': api_token, 'Accept': 'application/json'}
        if user_agent:
            self._headers['User-Agent'] = user_agent
        self._timeout = aiohttp.ClientTimeout(total=request_timeout)
        self._max_connections = max_connections
        self._session = None

    async def __aenter__(self):
        self._session = aiohttp.ClientSession(
            headers=self._headers,
            timeout=self._timeout,
            connector=aiohttp.TCPConnector(limit_per_host=self._max_connections))
        return self

    async def __aexit__(self, exception_type, exception_value, traceback):
        await self._session.close()

    def _url(self, path, params, api_version):
        url = '{}/api/{}/{}'.format(self._api_url, api_version or DEFAULT_API_VERSION, path)
        if params:
            url = '{}?{}'.format(url, params)
        # Same quoting requests applies to a string querystring, so both clients send identical URLs.
        return URL(requests.utils.requote_uri(url), encoded=True)

    # Backoff for Server5xxError, Server429Error, OSError, aiohttp connection errors and timeouts.
    @backoff.on_exception(backoff.expo,
                          (Exception),
                          giveup=lambda e: not should_retry_error(e),
                          max_tries=5,
                          factor=2)
    async def get(self, path, params=None, endpoint=None, api_version=None):
        """GET `path` with `params` (a querystring, as built by the streams) and return the JSON body."""
        await REQUEST_LIMITER.wait_async()
        with metrics.http_request_timer(endpoint) as timer:
            async with self._session.get(self._url(path, params, api_version)) as response:
                timer.tags[metrics.Tag.http_status_code] = response.status
                body = await response.read()

        if response.status != 200:
            try:
                response_json = json.loads(body)
            except Exception:
                response_json = {}
            raise error_for_status(response.status, response_json)

        if body == b"":
            # Handling empty response b'' given by ActiveCampaign APIs
            return {}
        try:
            return json.loads(body)
        except Exception as err:
            # Log invalid JSON (e.g. unterminated string errors)
            LOGGER.error('{}'.format(err))
            LOGGER.error('response content: {}'.format(body))
            raise
