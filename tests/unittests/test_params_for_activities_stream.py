import requests
from tap_activecampaign.streams import Activities
from tap_activecampaign.client import ActiveCampaignClient
import unittest
from unittest import mock

# mocked response class
class Mockresponse:
    def __init__(self, status_code, json, raise_error, headers=None):
        self.status_code = status_code
        self.raise_error = raise_error
        self.text = json
        self.headers = headers

    def raise_for_status(self):
        """
            Raise error if 'raise_error' is True
        """
        if not self.raise_error:
            return self.status_code

        raise requests.HTTPError("Sample message")

    def json(self):
        """
            Return mocked response
        """
        return self.text

# function to get mocked response
def get_response(status_code, json={}, raise_error=False, headers=None):
    return Mockresponse(status_code, json, raise_error, headers)

class TestActivitiesStreamParams(unittest.TestCase):
    """
        Test case to verify the param `after` is set as expected for activities during API call
    """

    @mock.patch('requests.Session.request')
    @mock.patch('tap_activecampaign.streams.Activities.process_records')
    def test_activities_stream_params(self, mocked_process_records, mocked_request):
        # mock request and return value
        mocked_request.return_value = get_response(200, {
            "activities": [],
            "meta": {
                "total": "0"
            }
        })
        # mock 'process_records' and return value
        mocked_process_records.return_value = "2022-04-01", 0

        # create client
        client = ActiveCampaignClient("test_client_id", "test_client_secret", "test_refresh_token")
        # create 'Activities' stream object
        activities = Activities(client=client)
        # function call
        activities.sync(client, {}, {}, "2022-04-01", activities.path, ["activities"])

        # get arguments passed during calling "requests.Session.request"
        args, kwargs = mocked_request.call_args
        # get 'params' value from passed arguments
        params = kwargs.get("params")

        # verify the 'after' param is used with start date
        self.assertTrue('after=2022-04-01' in params)
