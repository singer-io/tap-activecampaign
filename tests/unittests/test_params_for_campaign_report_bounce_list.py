import requests
from tap_activecampaign.streams import Campaign_report_bounce_list
from tap_activecampaign.client_v1 import ActiveCampaignClientV1
import unittest
from unittest import mock


class Mockresponse:
    def __init__(self, status_code, json, raise_error, headers=None):
        self.status_code = status_code
        self.raise_error = raise_error
        self.text = json
        self.headers = headers

    def raise_for_status(self):
        if not self.raise_error:
            return self.status_code
        raise requests.HTTPError("Sample message")

    def json(self):
        return self.text


def get_response(status_code, json={}, raise_error=False, headers=None):
    return Mockresponse(status_code, json, raise_error, headers)


class TestCampaignReportBounceListParams(unittest.TestCase):
    @mock.patch("requests.Session.request")
    @mock.patch("tap_activecampaign.streams.Campaign_report_bounce_list.process_records")
    def test_stream_params(self, mocked_process_records, mocked_request):
        mocked_request.side_effect = [
            get_response(
                200,
                """<?xml version='1.0' encoding='utf-8'?>
                    <not_allowed><error>You are not authorized to access this file</error></not_allowed>
                """
            ),
            get_response(
                200,
                {
                    "0": {
                        "id": "1",
                        "subscriberid": "111",
                        "email": "test01@gmail.com",
                        "campaignid": "123",
                        "messageid": "10",
                        "listid": "5",
                        "tstamp": "2023-08-28",
                        "type": "hard",
                        "code": "5.1.1",
                        "counted": "1",
                        "reason": "user_unknown",
                        "descript": "User unknown",
                    },
                    "1": {
                        "id": "2",
                        "subscriberid": "222",
                        "email": "test02@gmail.com",
                        "campaignid": "123",
                        "messageid": "10",
                        "listid": "5",
                        "tstamp": "2023-08-29",
                        "type": "soft",
                        "code": "4.2.2",
                        "counted": "1",
                        "reason": "mailbox_full",
                        "descript": "Mailbox full",
                    },
                    "result_code": 1,
                    "result_message": "Success: Something is returned",
                    "result_output": "json",
                },
            ),
            get_response(
                200,
                {
                    "0": {
                        "id": "3",
                        "subscriberid": "333",
                        "email": "test03@gmail.com",
                        "campaignid": "123",
                        "messageid": "10",
                        "listid": "5",
                        "tstamp": "2023-08-30",
                        "type": "hard",
                        "code": "5.1.1",
                        "counted": "1",
                        "reason": "user_unknown",
                        "descript": "User unknown",
                    },
                    "1": {
                        "id": "4",
                        "subscriberid": "444",
                        "email": "test04@gmail.com",
                        "campaignid": "123",
                        "messageid": "10",
                        "listid": "5",
                        "tstamp": "2023-08-31",
                        "type": "soft",
                        "code": "4.2.2",
                        "counted": "0",
                        "reason": "mailbox_full",
                        "descript": "Mailbox full",
                    },
                    "result_code": 1,
                    "result_message": "Success: Something is returned",
                    "result_output": "json",
                },
            ),
            get_response(
                200,
                {
                    "result_code": 0,
                    "result_message": "Failed: Nothing is returned",
                    "result_output": "json",
                },
            ),
        ]

        mocked_process_records.side_effect = [("2023-08-28", 2), ("2023-08-28", 2)]

        client = ActiveCampaignClientV1("test_client_id", "test_client_secret", "test_refresh_token")
        stream = Campaign_report_bounce_list(client=client)
        total_extracted_entries = stream.sync(
            client,
            {},
            {},
            "2022-04-01",
            stream.path,
            ["campaign_report_bounce_list"],
            campaigns=[123],
        )

        args, kwargs = mocked_request.call_args
        params = kwargs.get("params")

        self.assertTrue("page=3&campaignid=123" in params)
        self.assertEqual(total_extracted_entries, 4)
