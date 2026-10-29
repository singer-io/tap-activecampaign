import unittest
from unittest.mock import MagicMock, patch

from singer.catalog import Catalog, CatalogEntry, Schema

from tap_activecampaign.exceptions import ActiveCampaignNotFoundError
from tap_activecampaign.schema import get_schemas
from tap_activecampaign.sync import sync as tap_sync
from tap_activecampaign.streams import (
    STREAMS,
    SUB_STREAMS,
    Contacts,
    EmailActivities,
    Tags,
)

START_DATE = '2025-01-01T00:00:00Z'


def _catalog_for(stream_name):
    schemas, field_metadata = get_schemas()
    mdata = field_metadata[stream_name]
    for entry in mdata:
        entry['metadata']['selected'] = True
    return Catalog([CatalogEntry(
        stream=stream_name,
        tap_stream_id=stream_name,
        key_properties=['id'],
        schema=Schema.from_dict(schemas[stream_name]),
        metadata=mdata)])


def _activities(first_id, count):
    return {
        'emailActivities': [
            {'id': str(first_id + i), 'subscriberid': '7', 'tstamp': '2026-01-01T00:00:00-05:00'}
            for i in range(count)
        ],
        'meta': {'total': str(count)},
    }


def _sync_child(client, parent_id=7):
    stream = EmailActivities(client)
    with patch('singer.messages.write_record') as write_record:
        total = stream.sync(
            client=client,
            catalog=_catalog_for('email_activities'),
            state={},
            start_date=START_DATE,
            path=stream.path,
            selected_streams=['email_activities'],
            parent=stream.parent,
            parent_id=parent_id)
    return total, write_record


class TestEmailActivitiesRegistration(unittest.TestCase):

    def test_stream_is_child_of_contacts(self):
        self.assertEqual(EmailActivities.parent, 'contacts')
        self.assertEqual(EmailActivities.parent_query_field, 'filters[subscriberid]')
        self.assertEqual(EmailActivities.replication_method, 'FULL_TABLE')
        self.assertNotIn('email_activities', Contacts.children)
        self.assertEqual(SUB_STREAMS['contacts'], 'email_activities')
        self.assertIs(STREAMS['email_activities'], EmailActivities)

    def test_discovery_metadata_names_parent(self):
        _, field_metadata = get_schemas()
        root = next(m for m in field_metadata['email_activities'] if m['breadcrumb'] == ())
        self.assertEqual(root['metadata']['parent-tap-stream-id'], 'contacts')


class TestEmailActivitiesSync(unittest.TestCase):

    def setUp(self):
        self.client = MagicMock()
        self.client.base_url = 'https://example.api-us1.com/api/3/'

    def test_filters_by_parent_contact_id(self):
        self.client.get.return_value = _activities(1, 3)

        total, write_record = _sync_child(self.client, parent_id=7)

        self.assertEqual(total, 3)
        self.assertEqual(write_record.call_count, 3)
        self.client.get.assert_called_once()
        params = self.client.get.call_args.kwargs['params']
        self.assertIn('filters[subscriberid]=7', params)
        self.assertEqual(self.client.get.call_args.kwargs['path'], 'emailActivities')

    def test_paginates_full_pages(self):
        self.client.get.side_effect = [_activities(1, 100), _activities(101, 40)]

        total, _ = _sync_child(self.client)

        self.assertEqual(total, 140)
        offsets = [c.kwargs['params'] for c in self.client.get.call_args_list]
        self.assertIn('offset=0', offsets[0])
        self.assertIn('offset=100', offsets[1])

    def test_keeps_paging_when_meta_total_is_page_local(self):
        # 250 records, but each response reports only its own page size as the total.
        self.client.get.side_effect = [_activities(1, 100), _activities(101, 100), _activities(201, 50)]

        total, write_record = _sync_child(self.client)

        self.assertEqual(total, 250)
        self.assertEqual(write_record.call_count, 250)
        self.assertEqual(self.client.get.call_count, 3)

    def test_keeps_paging_when_meta_total_is_missing(self):
        pages = [_activities(1, 100), _activities(101, 100), _activities(201, 50)]
        for page in pages:
            del page['meta']
        self.client.get.side_effect = pages

        total, _ = _sync_child(self.client)

        self.assertEqual(total, 250)
        self.assertEqual(self.client.get.call_count, 3)

    def test_exact_multiple_of_page_size_ends_on_empty_page(self):
        self.client.get.side_effect = [_activities(1, 100), {'emailActivities': [], 'meta': {'total': '0'}}]

        total, _ = _sync_child(self.client)

        self.assertEqual(total, 100)
        self.assertEqual(self.client.get.call_count, 2)

    def test_short_page_ends_pagination_even_if_meta_total_is_global(self):
        page = _activities(1, 5)
        page['meta']['total'] = '8295'
        self.client.get.return_value = page

        total, _ = _sync_child(self.client)

        self.assertEqual(total, 5)
        self.assertEqual(self.client.get.call_count, 1)

    def test_empty_result_ends_pagination(self):
        self.client.get.return_value = {'emailActivities': [], 'meta': {'total': '0'}}

        total, write_record = _sync_child(self.client)

        self.assertEqual(total, 0)
        write_record.assert_not_called()
        self.assertEqual(self.client.get.call_count, 1)

    def test_missing_contact_is_skipped(self):
        self.client.get.side_effect = ActiveCampaignNotFoundError('404')

        with patch('tap_activecampaign.streams.LOGGER') as logger:
            total, write_record = _sync_child(self.client, parent_id=999)

        self.assertEqual(total, 0)
        write_record.assert_not_called()
        self.assertEqual(self.client.get.call_count, 1)
        logger.warning.assert_called_once()
        self.assertIn('999', str(logger.warning.call_args))

    def test_not_found_still_raises_for_streams_without_parent_filter(self):
        self.client.base_url = 'https://example.api-us1.com/api/3/'
        self.client.get.side_effect = ActiveCampaignNotFoundError('404')
        stream = Tags(self.client)

        with patch('singer.write_schema'), patch('singer.messages.write_record'):
            with self.assertRaises(ActiveCampaignNotFoundError):
                stream.sync(
                    client=self.client,
                    catalog=_catalog_for('tags'),
                    state={},
                    start_date=START_DATE,
                    path=stream.path,
                    selected_streams=['tags'])


class TestEmailActivitiesFullContactPass(unittest.TestCase):

    def setUp(self):
        self.client = MagicMock()
        self.client.base_url = 'https://example.api-us1.com/api/3/'

    def _run(self, contact_pages):
        """contact_pages: list of contact-id lists, one per /contacts page."""
        pages = iter(contact_pages)

        def fake_get(path, params=None, endpoint=None):
            if path == 'contacts':
                return {'contacts': [{'id': str(i)} for i in next(pages)]}
            return {'emailActivities': [], 'meta': {'total': '0'}}

        self.client.get.side_effect = fake_get
        with patch('singer.write_schema'), patch('singer.messages.write_record'), \
                patch('singer.write_state'):
            return EmailActivities(self.client).sync_for_all_contacts(
                _catalog_for('email_activities'), {}, START_DATE)

    def _contact_calls(self):
        return [c.kwargs['params'] for c in self.client.get.call_args_list
                if c.kwargs['path'] == 'contacts']

    def _email_calls(self):
        return [c.kwargs['params'] for c in self.client.get.call_args_list
                if c.kwargs['path'] == 'emailActivities']

    def test_every_contact_is_queried_without_updated_after_filter(self):
        self._run([[11, 12]])

        emails = self._email_calls()
        self.assertEqual(len(emails), 2)
        self.assertIn('filters[subscriberid]=11', emails[0])
        self.assertIn('filters[subscriberid]=12', emails[1])
        for params in self._contact_calls():
            self.assertNotIn('updated_after', params)

    def test_contacts_are_paginated(self):
        self._run([list(range(1, 101)), [101, 102]])

        self.assertEqual(len(self._contact_calls()), 2)
        self.assertIn('offset=100', self._contact_calls()[1])
        self.assertEqual(len(self._email_calls()), 102)

    def test_no_contacts(self):
        self.assertEqual(self._run([[]]), 0)
        self.assertEqual(self._email_calls(), [])


class TestSyncEntryPoint(unittest.TestCase):

    def _run_sync(self, selected):
        catalog = MagicMock()
        catalog.get_selected_streams.return_value = [MagicMock(stream=s) for s in selected]
        with patch('tap_activecampaign.sync.EmailActivities') as email_cls, \
                patch('tap_activecampaign.sync.update_currently_syncing'), \
                patch.dict('tap_activecampaign.sync.STREAMS', {'contacts': MagicMock()}):
            email_cls.return_value.sync_for_all_contacts.return_value = 0
            tap_sync(MagicMock(), {'start_date': START_DATE}, catalog, {})
        return email_cls

    def test_runs_when_parent_not_selected(self):
        email_cls = self._run_sync(['email_activities'])
        email_cls.return_value.sync_for_all_contacts.assert_called_once()

    def test_runs_once_when_parent_selected(self):
        email_cls = self._run_sync(['contacts', 'email_activities'])
        email_cls.return_value.sync_for_all_contacts.assert_called_once()

    def test_skipped_when_not_selected(self):
        email_cls = self._run_sync(['contacts'])
        email_cls.return_value.sync_for_all_contacts.assert_not_called()


if __name__ == '__main__':
    unittest.main()
