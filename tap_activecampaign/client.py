import backoff
import requests
from singer import metrics, utils
import singer

LOGGER = singer.get_logger()
REQUEST_TIMEOUT = 300

DEFAULT_API_VERSION = '3'


class Server5xxError(Exception):
    pass


class Server429Error(Exception):
    pass


class ActiveCampaignError(Exception):
    pass
class ActiveCampaignBadRequestError(ActiveCampaignError):
    pass

class ActiveCampaignUnauthorizedError(ActiveCampaignError):
    pass

class ActiveCampaignForbiddenError(ActiveCampaignError):
    pass

class ActiveCampaignNotFoundError(ActiveCampaignError):
    pass

class ActiveCampaignUnprocessableEntityError(ActiveCampaignError):
    pass

class ActiveCampaignRateLimitError(Server429Error):
    pass

class ActiveCampaignInternalServerError(Server5xxError):
    pass


# Errors Reference: https://developers.activecampaign.com/reference#errors
STATUS_CODE_EXCEPTION_MAPPING = {
    400: {
        "raise_exception": ActiveCampaignBadRequestError,
        "message": "A validation exception has occurred."
    },
    401: {
        "raise_exception": ActiveCampaignUnauthorizedError,
        "message": "Invalid authorization credentials."
    },
    403: {
        "raise_exception": ActiveCampaignForbiddenError,
        "message": "The request could not be authenticated or the authenticated user is not authorized to access the requested resource."
    },
    404: {
        "raise_exception": ActiveCampaignNotFoundError,
        "message": "The requested resource does not exist."
    },
    422: {
        "raise_exception": ActiveCampaignUnprocessableEntityError,
        "message": "The request could not be processed, usually due to a missing or invalid parameter."
    },
    429: {
        "raise_exception": ActiveCampaignRateLimitError,
        "message": "The user has sent too many requests in a given amount of time ('rate limiting') - contact support or account manager for more details."
    },
    500: {
        "raise_exception": ActiveCampaignInternalServerError,
        "message": "The server encountered an unexpected condition which prevented" \
            " it from fulfilling the request."
    }
}

def should_retry_error(exception):
    """ 
        Return true if exception is required to retry otherwise return false
    """

    if isinstance(exception, OSError) or isinstance(exception, Server5xxError) or isinstance(exception, Server429Error):
        # Retry Server5xxError and Server429Error exception. Retry exception if it is child class of OSError.
        # OSError is Parent class of ConnectionError, ConnectionResetError, TimeoutError and other errors mentioned in https://docs.python.org/3/library/exceptions.html#os-exceptions
        return True
    elif type(exception) == Exception and type(exception.args[0][1]) == ConnectionResetError:
        # Tap raises Exception: ConnectionResetError(104, 'Connection reset by peer'). That's why we are retrying this error also.
        # Reference: https://app.circleci.com/pipelines/github/singer-io/tap-activecampaign/554/workflows/d448258e-20df-4e66-b2aa-bc8bd1f08912/jobs/558
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
    errors = response_json.get('errors', [])
    status_code = response.status_code
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

    raise exc(message) from None


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

    def check_api_token(self):
        if self.__api_token is None:
            raise Exception('Error: Missing api_token.')
        headers = {}
        if self.__user_agent:
            headers['User-Agent'] = self.__user_agent
        headers['Api-Token'] = self.__api_token
        headers['Accept'] = 'application/json'
        url = self.base_url
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
    @utils.ratelimit(5, 1)
    def request(self, method, path=None, url=None, api_version=None, **kwargs):
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
            raise Exception(err)

        return response_json

    def get(self, path, api_version=None, **kwargs):
        return self.request('GET', path=path, api_version=api_version, **kwargs)

    def post(self, path, api_version=None, **kwargs):
        return self.request('POST', path=path, api_version=api_version, **kwargs)