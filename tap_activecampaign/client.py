import backoff
import requests
from requests.exceptions import ConnectionError
from singer import metrics, utils
import singer

LOGGER = singer.get_logger()

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

def get_exception_for_status_code(status_code):
    # Map the status code with `STATUS_CODE_EXCEPTION_MAPPING` dictionary and accordingly return the error.
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
    # Class for each error defined above which extends `ActiveCampaignError`. If response contain `errors` 
    # object with multiple errors perpare error message containing title of all error  in `errors` object.
    # Otherwise perpare custom default message and raise the exception.

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
            exc = get_exception_for_status_code(status_code)
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
                 user_agent=None):
        self.__api_url = api_url
        self.__api_token = api_token
        self.__user_agent = user_agent
        self.__session = requests.Session()
        self.__verified = False
        self.base_url = '{}/api/{}/'.format(self.__api_url, DEFAULT_API_VERSION)

    # Backoff for ConnectionError and 429 rate limit error.
    @backoff.on_exception(backoff.expo,
                          (ConnectionError, Server429Error),
                          max_tries=5,
                          factor=2)
    def __enter__(self):
        self.__verified = self.check_api_token()
        return self

    def __exit__(self, exception_type, exception_value, traceback):
        self.__session.close()

    @backoff.on_exception(backoff.expo,
                          Server5xxError,
                          max_tries=5,
                          factor=2)
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
            headers=headers)
        if response.status_code != 200:
            raise_for_error(response)
        else:
            return True


    @backoff.on_exception(backoff.expo,
                          (Server5xxError, ConnectionError, Server429Error, OSError),
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
            response = self.__session.request(method, url, stream=True, **kwargs)
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
