import unittest
from unittest.mock import MagicMock, patch

from singer.catalog import Catalog, CatalogEntry, Schema

from tap_activecampaign.exceptions import ActiveCampaignNotFoundError
from tap_activecampaign.schema import get_schemas
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
        self.assertIn('email_activities', Contacts.children)
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


class TestContactsSyncsEmailActivities(unittest.TestCase):

    def test_each_contact_is_queried_for_its_email_activities(self):
        client = MagicMock()
        client.base_url = 'https://example.api-us1.com/api/3/'
        contacts = {
            'contacts': [
                {'id': '11', 'udate': '2026-01-01T00:00:00-05:00', 'cdate': '2026-01-01T00:00:00-05:00'},
                {'id': '12', 'udate': '2026-01-02T00:00:00-05:00', 'cdate': '2026-01-02T00:00:00-05:00'},
            ],
            'meta': {'total': '2'},
        }
        client.get.side_effect = lambda path, params=None, endpoint=None: (
            contacts if path == 'contacts' else {'emailActivities': [], 'meta': {'total': '0'}})

        schemas, field_metadata = get_schemas()
        entries = []
        for name in ('contacts', 'email_activities'):
            mdata = field_metadata[name]
            for entry in mdata:
                entry['metadata']['selected'] = True
            entries.append(CatalogEntry(
                stream=name, tap_stream_id=name, key_properties=['id'],
                schema=Schema.from_dict(schemas[name]), metadata=mdata))

        with patch('singer.write_schema'), patch('singer.messages.write_record'), \
                patch('singer.write_state'):
            Contacts(client).sync(
                client=client,
                catalog=Catalog(entries),
                state={},
                start_date=START_DATE,
                path='contacts',
                selected_streams=['contacts', 'email_activities'])

        child_queries = [c.kwargs['params'] for c in client.get.call_args_list
                         if c.kwargs['path'] == 'emailActivities']
        self.assertEqual(len(child_queries), 2)
        self.assertIn('filters[subscriberid]=11', child_queries[0])
        self.assertIn('filters[subscriberid]=12', child_queries[1])


if __name__ == '__main__':
    unittest.main()
