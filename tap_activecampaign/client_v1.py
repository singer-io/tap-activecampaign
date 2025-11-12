import backoff
import requests
from singer import metrics
import singer
import collections
import time
import threading
import functools
from requests.adapters import HTTPAdapter
from tap_activecampaign.client import (
    REQUEST_TIMEOUT,
    should_retry_error,
    raise_for_error
)
from urllib3 import Retry

LOGGER = singer.get_logger()


def ratelimit_mthreading(limit, every):
    """
    Decorator function for rate limiting the execution of a function within multi-threaded context.
    AC rate limit: https://www.activecampaign.com/api/overview.php
    `With our hosted service we have a API rate limit of 5 requests per second per account.`
    Args:
        limit (int): Defines the max number of times the function can be called in a given time window.
        every (int): The time window within which the function can be called up to the limit.
                     Expressed in second
    """
    def limitdecorator(func):
        times = collections.deque()
        lock = threading.Lock()

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            with lock:
                if len(times) >= limit:
                    tim0 = times.pop()
                    tim = time.time()
                    sleep_time = every - (tim - tim0)
                    if sleep_time > 0:
                        time.sleep(sleep_time)

                times.appendleft(time.time())
            return func(*args, **kwargs)

        return wrapper

    return limitdecorator


class ActiveCampaignClientV1(object):
    def __init__(self,
                 api_url,
                 api_token,
                 user_agent=None,
                 request_timeout=None,
                 retry_settings=None):
        self.__api_url = api_url
        self.__api_token = api_token
        self.__user_agent = user_agent
        self.__session = requests.Session()
        self.__verified = False
        self.base_url = f'{self.__api_url}'

        # if request_timeout is other than 0, "0" or "" then use request_timeout
        if request_timeout and float(request_timeout):
            self.request_timeout = float(request_timeout)
        else: # If value is 0, "0" or "" then set default to 300 seconds.
            self.request_timeout = REQUEST_TIMEOUT
        retry_settings = retry_settings or {}
        adapter = HTTPAdapter(
            max_retries=Retry(
                total=retry_settings.get('retry_count', 2),
                backoff_factor=retry_settings.get('backoff_factor', 0.1),
                status_forcelist=retry_settings.get('status_forcelist', [500, 502, 503, 504, 403])
            )
        )
        self.__session.mount("http://", adapter)
        self.__session.mount("https://", adapter)

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

    def check_api_token(self):
        if self.__api_token is None:
            raise Exception('Error: Missing api_token.')
        headers = {}
        if self.__user_agent:
            headers['User-Agent'] = self.__user_agent
        headers['Api-Token'] = self.__api_token
        headers['Accept'] = 'application/json'
        
        url = f'{self.base_url}/admin/api.php?api_action=user_me&api_output=json'

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
    # Rate limit: https://developers.activecampaign.com/reference#rate-limits
    @ratelimit_mthreading(5, 1)
    def request(self, method, path=None, url=None, **kwargs):
        if not self.__verified:
            self.__verified = self.check_api_token()

        if not url and path:
            url = f'{self.__api_url}/admin/api.php?api_action={path}&api_output=json'

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

        with metrics.http_request_timer(endpoint) as timer:
            response = self.__session.request(method, url, stream=True, timeout=self.request_timeout, **kwargs)
            timer.tags[metrics.Tag.http_status_code] = response.status_code

        if response.status_code != 200:
            LOGGER.error(f'method: {method}; '
                         f'requested url: {url}; '
                         f'params: {kwargs.get("params")}; '
                         f'data: {kwargs.get("data")}')
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

    def get(self, path, **kwargs):
        return self.request('GET', path=path, **kwargs)
