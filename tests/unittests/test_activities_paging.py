import unittest
from unittest.mock import MagicMock, patch

from singer.catalog import Catalog, CatalogEntry, Schema

from tap_activecampaign.schema import get_schemas
from tap_activecampaign.streams import Activities

START_DATE = '2025-01-01T00:00:00Z'


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


def _page(ids, total, tstamps=None):
    tstamps = tstamps or {}
    return {
        'activities': [
            {'id': str(i), 'tstamp': tstamps.get(i, '2026-06-{:02d}T00:00:00-05:00'.format(i % 28 + 1))}
            for i in ids
        ],
        'meta': {'total': str(total)},
    }


def _fake_get(filtered_pages, unfiltered_pages):
    """Serve pre-built pages, picking the set by whether the request carries `after`."""
    def get(path, params=None, endpoint=None):
        pages = filtered_pages if 'after=' in params else unfiltered_pages
        offset = int(params.split('offset=')[1].split('&')[0])
        return pages[offset // 100]
    return get


class TestActivitiesUnstablePaging(unittest.TestCase):

    def setUp(self):
        self.client = MagicMock()
        self.client.base_url = 'https://example.api-us1.com/api/3/'

    def _sync(self):
        stream = Activities(self.client)
        with patch('singer.messages.write_record') as write_record, \
                patch('singer.write_state') as write_state:
            total = stream.sync(
                client=self.client, catalog=_catalog(), state={}, start_date=START_DATE,
                path=stream.path, selected_streams=['activities'])
        return total, write_record, write_state

    def _requests(self):
        return [c.kwargs['params'] for c in self.client.get.call_args_list]

    def test_consistent_paging_is_read_once(self):
        pages = [_page(range(1, 101), 140), _page(range(101, 141), 140)]
        self.client.get.side_effect = _fake_get(pages, [])

        total, write_record, write_state = self._sync()

        self.assertEqual(total, 140)
        self.assertEqual(write_record.call_count, 140)
        self.assertEqual(len(self._requests()), 2)
        for params in self._requests():
            self.assertIn('after=', params)
        write_state.assert_called_once()

    def test_duplicates_trigger_a_re_read_without_after(self):
        # Page 2 repeats ids 91-100, so ids 131-140 were skipped.
        filtered = [_page(range(1, 101), 140), _page(range(91, 131), 140)]
        unfiltered = [_page(range(1, 101), 140), _page(range(101, 141), 140)]
        self.client.get.side_effect = _fake_get(filtered, unfiltered)

        with patch('tap_activecampaign.streams.LOGGER') as logger:
            total, write_record, _ = self._sync()

        written_ids = {c.args[1]['id'] for c in write_record.call_args_list}
        self.assertTrue(set(range(131, 141)) <= written_ids)
        self.assertEqual(len(written_ids), 140)
        self.assertEqual(total, 140)
        self.assertEqual(['after=' in p for p in self._requests()], [True, True, False, False])
        logger.warning.assert_called_once()

    def test_bookmark_is_written_once_after_the_re_read(self):
        filtered = [_page(range(1, 101), 140), _page(range(91, 131), 140)]
        unfiltered = [_page(range(1, 101), 140), _page(range(101, 141), 140)]
        self.client.get.side_effect = _fake_get(filtered, unfiltered)

        _, _, write_state = self._sync()

        write_state.assert_called_once()
        state = write_state.call_args.args[0]
        self.assertIn('activities', state['bookmarks'])

    def test_re_read_keeps_records_older_than_the_first_pass_bookmark(self):
        # The re-read must filter on the bookmark from before the sync, not the one the first pass found.
        filtered = [_page(range(1, 101), 140), _page(range(91, 131), 140)]
        unfiltered = [_page(range(1, 101), 140), _page(range(101, 141), 140)]
        self.client.get.side_effect = _fake_get(filtered, unfiltered)
        stream = Activities(self.client)

        with patch('singer.messages.write_record') as write_record, patch('singer.write_state'):
            stream.sync(
                client=self.client, catalog=_catalog(), state={'bookmarks': {'activities': '2026-06-01T00:00:00.000000Z'}},
                start_date=START_DATE, path=stream.path, selected_streams=['activities'])

        written_ids = {c.args[1]['id'] for c in write_record.call_args_list}
        self.assertTrue(set(range(131, 141)) <= written_ids)

    def test_each_record_is_written_once_across_both_passes(self):
        # Ids 91-100 repeat in the filtered pass, and ids 1-130 were already written before the re-read.
        filtered = [_page(range(1, 101), 140), _page(range(91, 131), 140)]
        unfiltered = [_page(range(1, 101), 140), _page(range(101, 141), 140)]
        self.client.get.side_effect = _fake_get(filtered, unfiltered)

        total, write_record, _ = self._sync()

        written_ids = [c.args[1]['id'] for c in write_record.call_args_list]
        self.assertEqual(len(written_ids), 140)
        self.assertEqual(set(written_ids), set(range(1, 141)))
        self.assertEqual(total, 140)

    def test_bookmark_is_the_highest_across_both_passes(self):
        # The newest record (id 5) is written by the filtered pass and skipped in the re-read.
        newest = {5: '2026-06-30T12:00:00-05:00'}
        filtered = [_page(range(1, 101), 140, newest), _page(range(91, 131), 140)]
        unfiltered = [_page(range(1, 101), 140, newest), _page(range(101, 141), 140)]
        self.client.get.side_effect = _fake_get(filtered, unfiltered)

        _, _, write_state = self._sync()

        state = write_state.call_args.args[0]
        self.assertEqual(state['bookmarks']['activities'], '2026-06-30T17:00:00.000000Z')

    def test_ids_are_not_retained_during_the_unfiltered_re_read(self):
        filtered = [_page(range(1, 101), 140), _page(range(91, 131), 140)]
        unfiltered = [_page(range(1, 101), 140), _page(range(101, 141), 140)]
        self.client.get.side_effect = _fake_get(filtered, unfiltered)
        stream = Activities(self.client)

        with patch('singer.messages.write_record'), patch('singer.write_state'):
            stream.sync(
                client=self.client, catalog=_catalog(), state={}, start_date=START_DATE,
                path=stream.path, selected_streams=['activities'])

        # Counters restart for the re-read and must stay empty while the filter is off.
        self.assertEqual(stream._rows_seen, 0)
        self.assertEqual(stream._ids_seen, set())


if __name__ == '__main__':
    unittest.main()
