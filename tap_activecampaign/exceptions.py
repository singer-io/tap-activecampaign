class Server5xxError(Exception):
    pass

class Server429Error(Exception):
    pass

class ActiveCampaignError(Exception):
    """Generic ActiveCampaign API error."""

    def __init__(self, message=None, response=None):
        super().__init__(message)
        self.message = message
        self.response = response

class ActiveCampaignBadRequestError(ActiveCampaignError):
    """HTTP 400 - Bad Request."""
    pass

class ActiveCampaignUnauthorizedError(ActiveCampaignError):
    """HTTP 401 - Unauthorized."""
    pass

class ActiveCampaignForbiddenError(ActiveCampaignError):
    """HTTP 403 - Forbidden."""
    pass

class ActiveCampaignNotFoundError(ActiveCampaignError):
    """HTTP 404 - Not Found."""
    pass

class ActiveCampaignUnprocessableEntityError(ActiveCampaignError):
    """HTTP 422 - Unprocessable Entity."""
    pass

class ActiveCampaignRateLimitError(Server429Error):
    """HTTP 429 - Rate Limit Exceeded."""
    pass

class ActiveCampaignInternalServerError(Server5xxError):
    """HTTP 500+ - Server Error."""
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
        "message": "The server encountered an unexpected condition which prevented"
            " it from fulfilling the request."
    }
}
