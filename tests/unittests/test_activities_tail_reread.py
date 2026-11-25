import unittest
from unittest.mock import MagicMock, patch

from singer.catalog import Catalog, CatalogEntry, Schema

from tap_activecampaign.schema import get_schemas
from tap_activecampaign.streams import Activities

START_DATE = '2025-01-01T00:00:00Z'
TSTAMP = '2026-06-15T00:00:00-05:00'


def _catalog():
    schemas, field_metadata = get_schemas()
    mdata = field_metadata['activities']
    for entry in mdata:
        entry['metadata']['selected'] = True
    return Catalog([CatalogEntry(
        stream='activities',
        tap_stream_id='activities',
        key_properties=['id'],
        schema=Schema.from_dict(schemas['activities']),
        metadata=mdata)])


def _row(i):
    return {'id': str(i), 'tstamp': TSTAMP}


class FakeFeed:
    """
    Activities feed with ids ascending by offset. Requests with `after` return `filtered_pages`
    (which may repeat rows); requests without it page the id-ordered feed.
    """

    def __init__(self, ids, filtered_pages):
        self.ids = list(ids)
        self.filtered_pages = filtered_pages
        self.unfiltered_requests = []

    def get(self, path, params=None, endpoint=None):
        offset = int(params.split('offset=')[1].split('&')[0])
        if 'after=' in params:
            rows = self.filtered_pages[offset // 100]
            total = sum(len(p) for p in self.filtered_pages)
            return {'activities': [_row(i) for i in rows], 'meta': {'total': str(total)}}
        limit = int(params.split('limit=')[1].split('&')[0])
        self.unfiltered_requests.append((offset, limit))
        page = self.ids[offset:offset + limit]
        return {'activities': [_row(i) for i in page], 'meta': {'total': str(len(self.ids))}}


class TestActivitiesTailReRead(unittest.TestCase):

    def setUp(self):
        self.client = MagicMock()
        self.client.base_url = 'https://example.api-us1.com/api/3/'

    def _sync(self, feed, state):
        self.client.get.side_effect = feed.get
        stream = Activities(self.client)
        with patch('singer.messages.write_record') as write_record, patch('singer.write_state'):
            total = stream.sync(
                client=self.client, catalog=_catalog(), state=state, start_date=START_DATE,
                path=stream.path, selected_streams=['activities'])
        written = [int(c.args[1]['id']) for c in write_record.call_args_list]
        return total, written

    def test_re_read_starts_after_the_last_synced_id(self):
        # Ids 1-250 were synced before. 251-400 are new; the filtered pass repeats 341-350 and skips 391-400.
        feed = FakeFeed(range(1, 401), [list(range(251, 351)), list(range(341, 391))])
        state = {'bookmarks': {'activities_max_id': 250}}

        total, written = self._sync(feed, state)

        self.assertEqual(set(written), set(range(251, 401)))
        self.assertEqual(len(written), 150)
        self.assertEqual(total, 150)
        # The re-read begins at offset 250 (after the binary search probes), never at 0.
        tail = [r for r in feed.unfiltered_requests if r[1] == 100]
        self.assertEqual(tail[0][0], 250)
        self.assertEqual(state['bookmarks']['activities_max_id'], 400)

    def test_binary_search_uses_few_requests(self):
        ids = list(range(1, 10001))
        feed = FakeFeed(ids, [])
        stream = Activities(self.client)
        self.client.get.side_effect = feed.get

        offset = stream._first_offset_after_id(7777)

        self.assertEqual(offset, 7777)
        self.assertLessEqual(len(feed.unfiltered_requests), 16)

    def test_binary_search_with_gaps_in_ids(self):
        feed = FakeFeed([10, 20, 30, 40, 50], [])
        stream = Activities(self.client)
        self.client.get.side_effect = feed.get

        self.assertEqual(stream._first_offset_after_id(30), 3)
        self.assertEqual(stream._first_offset_after_id(5), 0)

    def test_no_newer_rows_means_no_re_read(self):
        feed = FakeFeed([10, 20, 30], [])
        stream = Activities(self.client)
        self.client.get.side_effect = feed.get

        self.assertIsNone(stream._first_offset_after_id(30))
        self.assertEqual(stream._first_offset_after_id(0), 0)

    def test_without_stored_id_the_whole_feed_is_re_read(self):
        ids = list(range(1, 141))
        feed = FakeFeed(ids, [list(range(1, 101)), list(range(91, 131))])

        total, written = self._sync(feed, {})

        self.assertEqual(set(written), set(ids))
        self.assertEqual(len(written), 140)
        self.assertEqual(feed.unfiltered_requests[0], (0, 100))

    def test_max_id_is_stored_after_a_normal_pass(self):
        ids = list(range(1, 51))
        feed = FakeFeed(ids, [list(range(1, 51))])

        _, written = self._sync(feed, state := {})

        self.assertEqual(len(written), 50)
        self.assertEqual(state['bookmarks']['activities_max_id'], 50)
        self.assertEqual(feed.unfiltered_requests, [])

    def test_stored_id_never_moves_back(self):
        feed = FakeFeed(list(range(1, 11)), [list(range(1, 11))])
        state = {'bookmarks': {'activities_max_id': 500}}

        self._sync(feed, state)

        self.assertEqual(state['bookmarks']['activities_max_id'], 500)


if __name__ == '__main__':
    unittest.main()
