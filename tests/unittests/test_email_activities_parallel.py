import threading
import time
import unittest
from unittest.mock import MagicMock, patch

from singer.catalog import Catalog, CatalogEntry, Schema

from tap_activecampaign.client import RateLimiter
from tap_activecampaign.exceptions import ActiveCampaignNotFoundError
from tap_activecampaign.schema import get_schemas
from tap_activecampaign.streams import EmailActivities, MAX_WORKERS

START_DATE = '2025-01-01T00:00:00Z'


def _catalog():
    schemas, field_metadata = get_schemas()
    mdata = field_metadata['email_activities']
    for entry in mdata:
        entry['metadata']['selected'] = True
    return Catalog([CatalogEntry(
        stream='email_activities', tap_stream_id='email_activities', key_properties=['id'],
        schema=Schema.from_dict(schemas['email_activities']), metadata=mdata)])


class FakeApi:
    """Thread-safe fake: contacts by keyset, emails per contact, optional latency and failures."""

    def __init__(self, contact_ids, emails_per_contact=2, latency=0.0, not_found=(), fail=None):
        self.contact_ids = list(contact_ids)
        self.emails_per_contact = emails_per_contact
        self.latency = latency
        self.not_found = set(not_found)
        self.fail = fail or {}
        self.calls = []
        self.in_flight = 0
        self.max_in_flight = 0
        self._lock = threading.Lock()

    def get(self, path, params=None, endpoint=None, **kwargs):
        with self._lock:
            self.calls.append((path, params))
            self.in_flight += 1
            self.max_in_flight = max(self.max_in_flight, self.in_flight)
        try:
            time.sleep(self.latency)
            if path == 'contacts':
                last = int(params.split('id_greater=')[1])
                page = [c for c in self.contact_ids if c > last][:100]
                return {'contacts': [{'id': str(c)} for c in page], 'meta': {'total': str(len(self.contact_ids))}}
            contact = int(params.split('filters[subscriberid]=')[1])
            if contact in self.fail:
                raise self.fail[contact]
            if contact in self.not_found:
                raise ActiveCampaignNotFoundError('404')
            offset = int(params.split('offset=')[1].split('&')[0])
            rows = [{'id': str(contact * 1000 + i), 'subscriberid': str(contact),
                     'tstamp': '2026-06-15T05:11:33-05:00'} for i in range(self.emails_per_contact)]
            return {'emailActivities': rows[offset:offset + 100], 'meta': {'total': str(len(rows))}}
        finally:
            with self._lock:
                self.in_flight -= 1

    def email_calls(self):
        return [p for path, p in self.calls if path == 'emailActivities']


def _run(api, workers=None):
    client = MagicMock()
    client.base_url = 'https://example.api-us1.com/api/3/'
    client.get.side_effect = api.get
    stream = EmailActivities(client)
    written = []
    with patch('singer.messages.write_record', side_effect=lambda s, r, **kw: written.append(int(r['id']))), \
            patch('singer.write_state'):
        total = stream.sync_for_all_contacts(_catalog(), {}, START_DATE, workers=workers)
    return total, written


class TestParallelContactRequests(unittest.TestCase):

    def test_same_records_in_same_order_as_one_worker(self):
        ids = range(1, 251)
        total_1, written_1 = _run(FakeApi(ids), workers=1)
        total_4, written_4 = _run(FakeApi(ids), workers=4)

        self.assertEqual(written_4, written_1)
        self.assertEqual(total_4, total_1)
        self.assertEqual(total_4, 500)

    def test_every_contact_is_requested_exactly_once(self):
        api = FakeApi(range(1, 251))
        _run(api, workers=4)

        calls = api.email_calls()
        self.assertEqual(len(calls), 250)
        self.assertEqual(len(set(calls)), 250)

    def test_requests_overlap_only_up_to_the_worker_count(self):
        api = FakeApi(range(1, 61), latency=0.02)
        _run(api, workers=4)
        self.assertGreater(api.max_in_flight, 1)
        self.assertLessEqual(api.max_in_flight, 4)

        api = FakeApi(range(1, 21), latency=0.01)
        _run(api, workers=1)
        self.assertEqual(api.max_in_flight, 1)

    def test_workers_are_capped_and_empty_string_means_default(self):
        api = FakeApi(range(1, 31), latency=0.01)
        _run(api, workers=500)
        self.assertLessEqual(api.max_in_flight, MAX_WORKERS)

        api = FakeApi(range(1, 31), latency=0.01)
        _, written = _run(api, workers='')
        self.assertEqual(len(written), 60)

    def test_contact_with_more_than_one_page_is_paged_in_order(self):
        api = FakeApi([1, 2, 3], emails_per_contact=230)
        _, written = _run(api, workers=4)

        self.assertEqual(len(written), 690)
        self.assertEqual(len(set(written)), 690)
        self.assertEqual(written, sorted(written))
        self.assertEqual(len([p for p in api.email_calls() if 'filters[subscriberid]=2' in p]), 3)

    def test_deleted_contact_is_skipped_and_others_still_written(self):
        api = FakeApi(range(1, 21), not_found={5})
        _, written = _run(api, workers=4)

        self.assertEqual(len(written), 38)
        self.assertFalse(any(w // 1000 == 5 for w in written))

    def test_error_is_raised_at_that_contact_after_earlier_contacts_were_written(self):
        api = FakeApi(range(1, 21), fail={7: RuntimeError('boom')})
        written = []
        client = MagicMock()
        client.base_url = 'https://example.api-us1.com/api/3/'
        client.get.side_effect = api.get
        stream = EmailActivities(client)

        with patch('singer.messages.write_record', side_effect=lambda s, r, **kw: written.append(int(r['id']))), \
                patch('singer.write_state'):
            with self.assertRaises(RuntimeError):
                stream.sync_for_all_contacts(_catalog(), {}, START_DATE, workers=4)

        self.assertEqual({w // 1000 for w in written}, {1, 2, 3, 4, 5, 6})
        self.assertIs(stream.client, client)

    def test_parallel_requests_are_faster_than_sequential(self):
        ids = range(1, 41)
        start = time.perf_counter()
        _run(FakeApi(ids, latency=0.02), workers=1)
        sequential = time.perf_counter() - start

        start = time.perf_counter()
        _run(FakeApi(ids, latency=0.02), workers=4)
        parallel = time.perf_counter() - start

        self.assertLess(parallel, sequential / 2)

    def test_all_contacts_are_requested_with_the_same_query_as_before(self):
        api = FakeApi(range(1, 4))
        _run(api, workers=4)
        self.assertEqual(
            sorted(api.email_calls()),
            ['offset=0&limit=100&filters[subscriberid]=%d' % i for i in (1, 2, 3)])


class TestRateLimiter(unittest.TestCase):

    def test_never_exceeds_the_limit_across_threads(self):
        window = 0.5
        limiter = RateLimiter(5, window)
        starts = []
        lock = threading.Lock()

        def worker():
            for _ in range(5):
                limiter.wait()
                with lock:
                    starts.append(time.monotonic())

        threads = [threading.Thread(target=worker) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        starts.sort()
        self.assertEqual(len(starts), 20)
        # Any 6 consecutive starts must span about the window. The tolerance covers sleep and timer
        # granularity (about 15 ms on Windows); an unlimited limiter would measure close to 0.
        for i in range(len(starts) - 5):
            self.assertGreaterEqual(starts[i + 5] - starts[i], window - 0.06)

    def test_does_not_delay_below_the_limit(self):
        limiter = RateLimiter(5, 1)
        start = time.monotonic()
        for _ in range(5):
            limiter.wait()
        self.assertLess(time.monotonic() - start, 0.1)


if __name__ == '__main__':
    unittest.main()
