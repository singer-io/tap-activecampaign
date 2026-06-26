import requests
import unittest
from unittest import mock

from tap_activecampaign.streams import ContactCustomFieldValues
from tap_activecampaign.client import ActiveCampaignClient


class MockResponse:
    def __init__(self, status_code, json_data):
        self.status_code = status_code
        self._json_data = json_data
        self.headers = {}
        self.content = b'...'

    def raise_for_status(self):
        if self.status_code != 200:
            raise requests.HTTPError('HTTP {}'.format(self.status_code))

    def json(self):
        return self._json_data


START_DATE = '2022-04-01T00:00:00.000000Z'
OLDER_CONTACT_UDATE = '2023-09-01T10:00:00-05:00'
NEWER_CONTACT_UDATE = '2023-09-02T10:00:00-05:00'
FIELD_VALUE_UDATE = '2023-08-01T00:00:00-05:00'

CONTACTS_PAGE = {
    'contacts': [
        {'id': '1', 'udate': OLDER_CONTACT_UDATE},
        {'id': '2', 'udate': NEWER_CONTACT_UDATE},
    ],
    'fieldValues': [
        {
            'id': '10',
            'contact': '1',
            'field': '5',
            'value': 'v1',
            'udate': FIELD_VALUE_UDATE,
            'cdate': FIELD_VALUE_UDATE,
        },
        {
            'id': '11',
            'contact': '2',
            'field': '5',
            'value': 'v2',
            'udate': FIELD_VALUE_UDATE,
            'cdate': FIELD_VALUE_UDATE,
        },
    ],
    'meta': {'total': '2'},
}


class TestContactCustomFieldValuesParams(unittest.TestCase):

    @mock.patch('tap_activecampaign.client.ActiveCampaignClient.check_api_token')
    @mock.patch('tap_activecampaign.client.requests.Session.request')
    @mock.patch('tap_activecampaign.streams.ContactCustomFieldValues.process_records')
    def test_params_include_fieldvalues_and_updated_after(
        self, mock_process_records, mock_request, mock_check_token
    ):
        """API call must include include=fieldValues and filters[updated_after] params."""
        mock_check_token.return_value = True
        mock_request.return_value = MockResponse(200, CONTACTS_PAGE)
        mock_process_records.return_value = (None, 2)

        client = ActiveCampaignClient('https://www.activecampaign.com', 'dummy_token')
        stream = ContactCustomFieldValues(client=client)
        stream.sync(client, {}, {}, START_DATE, stream.path, [stream.stream_name])

        _, kwargs = mock_request.call_args
        params = kwargs.get('params', '')
        self.assertIn('include=fieldValues', params)
        self.assertIn('filters[updated_after]={}'.format(START_DATE), params)

    @mock.patch('tap_activecampaign.client.ActiveCampaignClient.check_api_token')
    @mock.patch('tap_activecampaign.client.requests.Session.request')
    @mock.patch('tap_activecampaign.streams.ContactCustomFieldValues.process_records')
    def test_bookmark_uses_max_contact_udate_not_field_value_udate(
        self, mock_process_records, mock_request, mock_check_token
    ):
        """Bookmark must advance to the max contact udate, not the field value udate.

        Contact udates (NEWER_CONTACT_UDATE) are newer than field value udates
        (FIELD_VALUE_UDATE). If we incorrectly used field value udate as the bookmark,
        contacts updated for non-field-value reasons would be re-fetched on every sync.
        """
        mock_check_token.return_value = True
        mock_request.return_value = MockResponse(200, CONTACTS_PAGE)
        mock_process_records.return_value = (None, 2)

        state = {}
        client = ActiveCampaignClient('https://www.activecampaign.com', 'dummy_token')
        stream = ContactCustomFieldValues(client=client)
        stream.sync(client, {}, state, START_DATE, stream.path, [stream.stream_name])

        self.assertEqual(
            state.get('bookmarks', {}).get('contact_custom_field_values'),
            NEWER_CONTACT_UDATE,
        )

    @mock.patch('tap_activecampaign.client.ActiveCampaignClient.check_api_token')
    @mock.patch('tap_activecampaign.client.requests.Session.request')
    @mock.patch('tap_activecampaign.streams.ContactCustomFieldValues.process_records')
    def test_uses_contacts_path(
        self, mock_process_records, mock_request, mock_check_token
    ):
        """Stream must query the contacts endpoint, not the fieldValues endpoint."""
        mock_check_token.return_value = True
        mock_request.return_value = MockResponse(200, CONTACTS_PAGE)
        mock_process_records.return_value = (None, 2)

        client = ActiveCampaignClient('https://www.activecampaign.com', 'dummy_token')
        stream = ContactCustomFieldValues(client=client)

        self.assertEqual(stream.path, 'contacts')

        stream.sync(client, {}, {}, START_DATE, stream.path, [stream.stream_name])

        _, kwargs = mock_request.call_args
        url = kwargs.get('url') or (mock_request.call_args[0][1] if mock_request.call_args[0] else '')
        self.assertIn('/contacts', url)
