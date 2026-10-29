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

    def test_repeated_full_pages_fail_instead_of_looping(self):
        # A server that ignores offset keeps returning the same 100 records.
        self.client.get.return_value = _activities(1, 100)

        with self.assertRaises(RuntimeError):
            _sync_child(self.client)

        self.assertEqual(self.client.get.call_count, 2)

    def test_page_overlapping_only_seen_records_fails(self):
        self.client.get.side_effect = [_activities(1, 100), _activities(1, 100), _activities(101, 40)]

        with self.assertRaises(RuntimeError):
            _sync_child(self.client)

    def test_page_with_some_new_records_is_accepted(self):
        self.client.get.side_effect = [_activities(1, 100), _activities(91, 100), _activities(191, 10)]

        total, _ = _sync_child(self.client)

        self.assertEqual(total, 210)

    def test_malformed_activities_response_fails(self):
        for response in ({}, {'meta': {'total': '0'}}, {'emailActivities': None}):
            with self.subTest(response=response):
                self.client.get.reset_mock()
                self.client.get.return_value = response
                with self.assertRaises(RuntimeError):
                    _sync_child(self.client)
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

    @staticmethod
    def _keyset_server(contact_ids, after_page=None):
        """Serve /contacts with orders[id]=ASC and id_greater; after_page(n) runs after the n-th page."""
        served = {'pages': 0}

        def serve(params):
            last_id = int(params.split('id_greater=')[1].split('&')[0])
            ids = sorted(i for i in contact_ids if i > last_id)[:100]
            served['pages'] += 1
            if after_page:
                after_page(served['pages'])
            return {'contacts': [{'id': str(i)} for i in ids]}

        return serve

    def _run(self, contacts_response):
        """contacts_response: callable(params) returning the /contacts response."""
        def fake_get(path, params=None, endpoint=None):
            if path == 'contacts':
                return contacts_response(params)
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
        self._run(self._keyset_server({11, 12}))

        emails = self._email_calls()
        self.assertEqual(len(emails), 2)
        self.assertIn('filters[subscriberid]=11', emails[0])
        self.assertIn('filters[subscriberid]=12', emails[1])
        for params in self._contact_calls():
            self.assertNotIn('updated_after', params)

    def test_contacts_use_keyset_paging(self):
        self._run(self._keyset_server(set(range(1, 103))))

        calls = self._contact_calls()
        self.assertEqual(len(calls), 2)
        self.assertIn('orders[id]=ASC', calls[0])
        self.assertIn('id_greater=0', calls[0])
        self.assertIn('id_greater=100', calls[1])
        self.assertNotIn('offset', calls[1])
        self.assertEqual(len(self._email_calls()), 102)

    def test_contact_deleted_between_pages_does_not_skip_later_contacts(self):
        contacts = set(range(1, 102))
        # Contact 1 was already processed; deleting it must not push contact 101 out of range.
        server = self._keyset_server(contacts, after_page=lambda n: contacts.discard(1) if n == 1 else None)

        self._run(server)

        requested = [p.split('filters[subscriberid]=')[1].split('&')[0] for p in self._email_calls()]
        self.assertIn('101', requested)
        self.assertEqual(len(requested), 101)

    def test_no_contacts(self):
        self.assertEqual(self._run(self._keyset_server(set())), 0)
        self.assertEqual(self._email_calls(), [])

    def test_malformed_contacts_response_fails(self):
        for response in ({}, None, {'meta': {'total': '0'}}, {'contacts': None}, {'contacts': {}}):
            with self.subTest(response=response):
                self.client.get.reset_mock()
                with self.assertRaises(RuntimeError):
                    self._run(lambda params, r=response: r)
                self.assertEqual(self._email_calls(), [])

    def test_contacts_pagination_without_progress_fails(self):
        # A server that ignores id_greater keeps returning the same full page.
        page = {'contacts': [{'id': str(i)} for i in range(1, 101)]}

        with self.assertRaises(RuntimeError):
            self._run(lambda params: page)

        self.assertEqual(len(self._contact_calls()), 2)


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
