import asyncio
import threading
import time
import unittest
from unittest.mock import MagicMock, patch

from aiohttp import web
from singer.catalog import Catalog, CatalogEntry, Schema

from tap_activecampaign.client import AsyncActiveCampaignClient, RateLimiter
from tap_activecampaign.exceptions import (
    ActiveCampaignNotFoundError,
    ActiveCampaignUnprocessableEntityError,
    Server5xxError,
)
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
    """Contacts by keyset, emails per contact, optional latency and failures; served sync or async."""

    def __init__(self, contact_ids, emails_per_contact=2, latency=0.0, not_found=(), fail=None,
                 repeat_pages=(), contacts_fail_after=None):
        self.contact_ids = list(contact_ids)
        self.emails_per_contact = emails_per_contact
        self.latency = latency
        self.not_found = set(not_found)
        self.fail = fail or {}
        self.repeat_pages = set(repeat_pages)  # contacts whose every page repeats the first one
        self.contacts_fail_after = contacts_fail_after
        self.calls = []
        self.sync_calls = []
        self.in_flight = 0
        self.max_in_flight = 0
        self._lock = threading.Lock()

    def _respond(self, path, params):
        if path == 'contacts':
            last = int(params.split('id_greater=')[1])
            if self.contacts_fail_after is not None and last >= self.contacts_fail_after:
                return {'unexpected': True}
            page = [c for c in self.contact_ids if c > last][:100]
            return {'contacts': [{'id': str(c)} for c in page], 'meta': {'total': str(len(self.contact_ids))}}
        contact = int(params.split('filters[subscriberid]=')[1])
        if contact in self.fail:
            raise self.fail[contact]
        if contact in self.not_found:
            raise ActiveCampaignNotFoundError('404')
        offset = int(params.split('offset=')[1].split('&')[0])
        if contact in self.repeat_pages:
            offset = 0
        rows = [{'id': str(contact * 1000 + i), 'subscriberid': str(contact),
                 'tstamp': '2026-06-15T05:11:33-05:00'} for i in range(self.emails_per_contact)]
        return {'emailActivities': rows[offset:offset + 100], 'meta': {'total': str(len(rows))}}

    def _enter(self, path, params):
        with self._lock:
            self.calls.append((path, params))
            self.in_flight += 1
            self.max_in_flight = max(self.max_in_flight, self.in_flight)

    def _exit(self):
        with self._lock:
            self.in_flight -= 1

    def get(self, path, params=None, endpoint=None, **kwargs):
        self._enter(path, params)
        self.sync_calls.append((path, params))
        try:
            time.sleep(self.latency)
            return self._respond(path, params)
        finally:
            self._exit()

    async def get_async(self, path, params=None, endpoint=None, **kwargs):
        self._enter(path, params)
        try:
            await asyncio.sleep(self.latency)
            return self._respond(path, params)
        finally:
            self._exit()

    def email_calls(self):
        return [p for path, p in self.calls if path == 'emailActivities']


class FakeAsyncClient:

    def __init__(self, api):
        self.api = api
        self.closed = False

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        self.closed = True

    async def get(self, path, params=None, endpoint=None, **kwargs):
        return await self.api.get_async(path, params=params, endpoint=endpoint)


def _client(api):
    client = MagicMock()
    client.base_url = 'https://example.api-us1.com/api/3/'
    client.get.side_effect = api.get
    client.async_client.side_effect = lambda max_connections: FakeAsyncClient(api)
    return client


def _run(api, workers=None):
    stream = EmailActivities(_client(api))
    written = []
    with patch('singer.messages.write_record', side_effect=lambda s, r, **kw: written.append(int(r['id']))), \
            patch('singer.write_state'):
        total = stream.sync_for_all_contacts(_catalog(), {}, START_DATE, workers=workers)
    return total, written


class TestAsyncContactRequests(unittest.TestCase):

    def test_same_records_in_same_order_as_one_worker(self):
        ids = range(1, 251)
        total_1, written_1 = _run(FakeApi(ids), workers=1)
        total_4, written_4 = _run(FakeApi(ids), workers=4)

        self.assertEqual(written_4, written_1)
        self.assertEqual(total_4, total_1)
        self.assertEqual(total_4, 500)

    def test_one_worker_uses_only_the_requests_client(self):
        api = FakeApi(range(1, 21))
        client = _client(api)
        with patch('singer.messages.write_record'), patch('singer.write_state'):
            EmailActivities(client).sync_for_all_contacts(_catalog(), {}, START_DATE, workers=1)
        client.async_client.assert_not_called()
        self.assertEqual(len(api.sync_calls), len(api.calls))

    def test_several_workers_use_only_the_async_client(self):
        api = FakeApi([1, 2, 3], emails_per_contact=230)
        _run(api, workers=4)
        self.assertEqual(api.sync_calls, [])

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

    def test_exactly_full_last_page_requests_one_empty_page(self):
        api = FakeApi([1, 2], emails_per_contact=200)
        _, written = _run(api, workers=4)
        self.assertEqual(len(written), 400)
        self.assertEqual(len([p for p in api.email_calls() if 'filters[subscriberid]=1' in p]), 3)

    def test_repeated_page_stops_prefetching_and_raises_in_order(self):
        api = FakeApi(range(1, 6), emails_per_contact=150, repeat_pages={3})
        written = []
        stream = EmailActivities(_client(api))
        with patch('singer.messages.write_record', side_effect=lambda s, r, **kw: written.append(int(r['id']))), \
                patch('singer.write_state'):
            with self.assertRaisesRegex(RuntimeError, 'no new records'):
                stream.sync_for_all_contacts(_catalog(), {}, START_DATE, workers=4)

        self.assertEqual(len([p for p in api.email_calls() if 'filters[subscriberid]=3' in p]), 2)
        self.assertEqual({w // 1000 for w in written}, {1, 2, 3})

    def test_deleted_contact_is_skipped_and_others_still_written(self):
        api = FakeApi(range(1, 21), not_found={5})
        _, written = _run(api, workers=4)

        self.assertEqual(len(written), 38)
        self.assertFalse(any(w // 1000 == 5 for w in written))

    def test_error_is_raised_at_that_contact_after_earlier_contacts_were_written(self):
        api = FakeApi(range(1, 21), fail={7: RuntimeError('boom')})
        written = []
        client = _client(api)
        stream = EmailActivities(client)

        with patch('singer.messages.write_record', side_effect=lambda s, r, **kw: written.append(int(r['id']))), \
                patch('singer.write_state'):
            with self.assertRaisesRegex(RuntimeError, 'boom'):
                stream.sync_for_all_contacts(_catalog(), {}, START_DATE, workers=4)

        self.assertEqual({w // 1000 for w in written}, {1, 2, 3, 4, 5, 6})
        self.assertIs(stream.client, client)

    def test_malformed_contacts_page_is_raised_after_earlier_contacts_were_written(self):
        api = FakeApi(range(1, 151), contacts_fail_after=1)
        written = []
        stream = EmailActivities(_client(api))
        with patch('singer.messages.write_record', side_effect=lambda s, r, **kw: written.append(int(r['id']))), \
                patch('singer.write_state'):
            with self.assertRaisesRegex(RuntimeError, 'Malformed contacts response'):
                stream.sync_for_all_contacts(_catalog(), {}, START_DATE, workers=4)

        self.assertEqual({w // 1000 for w in written}, set(range(1, 101)))

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


class TestAsyncClient(unittest.TestCase):
    """AsyncActiveCampaignClient against a local aiohttp server."""

    def _serve(self, handler, coro_factory):
        async def main():
            app = web.Application()
            app.router.add_get('/api/3/{path}', handler)
            runner = web.AppRunner(app)
            await runner.setup()
            site = web.TCPSite(runner, '127.0.0.1', 0)
            await site.start()
            port = site._server.sockets[0].getsockname()[1]
            try:
                client = AsyncActiveCampaignClient('http://127.0.0.1:%d' % port, 'token', 'agent', 30, 4)
                async with client:
                    return await coro_factory(client)
            finally:
                await runner.cleanup()
        return asyncio.run(main())

    def test_sends_headers_and_unencoded_brackets(self):
        seen = {}

        async def handler(request):
            seen['headers'] = request.headers
            seen['query'] = request.raw_path.split('?', 1)[1]
            return web.json_response({'emailActivities': []})

        result = self._serve(handler, lambda c: c.get(
            'emailActivities', params='offset=0&limit=100&filters[subscriberid]=7', endpoint='email_activities'))

        self.assertEqual(result, {'emailActivities': []})
        self.assertEqual(seen['query'], 'offset=0&limit=100&filters[subscriberid]=7')
        self.assertEqual(seen['headers']['Api-Token'], 'token')
        self.assertEqual(seen['headers']['User-Agent'], 'agent')
        self.assertEqual(seen['headers']['Accept'], 'application/json')

    def test_empty_body_is_an_empty_dict(self):
        async def handler(request):
            return web.Response(body=b'')
        self.assertEqual(self._serve(handler, lambda c: c.get('contacts')), {})

    def test_404_raises_not_found_without_retry(self):
        calls = []

        async def handler(request):
            calls.append(1)
            return web.json_response({'message': 'No Result found'}, status=404)

        with self.assertRaises(ActiveCampaignNotFoundError):
            self._serve(handler, lambda c: c.get('contacts'))
        self.assertEqual(len(calls), 1)

    def test_422_message_lists_error_titles(self):
        async def handler(request):
            return web.json_response({'errors': [{'title': 'a'}, {'title': 'b'}]}, status=422)

        with self.assertRaisesRegex(ActiveCampaignUnprocessableEntityError, 'HTTP-error-code: 422, Error: a b'):
            self._serve(handler, lambda c: c.get('contacts'))

    @patch('backoff._async.asyncio.sleep')
    def test_429_and_5xx_are_retried(self, _sleep):
        statuses = [429, 503]

        async def handler(request):
            if statuses:
                return web.json_response({}, status=statuses.pop(0))
            return web.json_response({'ok': 1})

        self.assertEqual(self._serve(handler, lambda c: c.get('contacts')), {'ok': 1})
        self.assertEqual(statuses, [])

    @patch('backoff._async.asyncio.sleep')
    def test_gives_up_after_five_tries(self, _sleep):
        calls = []

        async def handler(request):
            calls.append(1)
            return web.json_response({}, status=502)

        with self.assertRaises(Server5xxError):
            self._serve(handler, lambda c: c.get('contacts'))
        self.assertEqual(len(calls), 5)


class TestRateLimiter(unittest.TestCase):

    def _assert_within_limit(self, starts, window):
        starts.sort()
        self.assertEqual(len(starts), 20)
        # Any 6 consecutive starts must span about the window. The tolerance covers sleep and timer
        # granularity (about 15 ms on Windows); an unlimited limiter would measure close to 0.
        for i in range(len(starts) - 5):
            self.assertGreaterEqual(starts[i + 5] - starts[i], window - 0.06)

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
        self._assert_within_limit(starts, window)

    def test_never_exceeds_the_limit_across_tasks(self):
        window = 0.5
        limiter = RateLimiter(5, window)
        starts = []

        async def worker():
            for _ in range(5):
                await limiter.wait_async()
                starts.append(time.monotonic())

        async def main():
            await asyncio.gather(*(worker() for _ in range(4)))

        asyncio.run(main())
        self._assert_within_limit(starts, window)

    def test_threads_and_tasks_share_the_limit(self):
        window = 0.5
        limiter = RateLimiter(5, window)
        starts = []
        lock = threading.Lock()

        def thread_worker():
            for _ in range(10):
                limiter.wait()
                with lock:
                    starts.append(time.monotonic())

        async def task_worker():
            for _ in range(5):
                await limiter.wait_async()
                with lock:
                    starts.append(time.monotonic())

        thread = threading.Thread(target=thread_worker)
        thread.start()

        async def main():
            await asyncio.gather(task_worker(), task_worker())

        asyncio.run(main())
        thread.join()
        self._assert_within_limit(starts, window)

    def test_does_not_delay_below_the_limit(self):
        limiter = RateLimiter(5, 1)
        start = time.monotonic()
        for _ in range(5):
            limiter.wait()
        self.assertLess(time.monotonic() - start, 0.1)


if __name__ == '__main__':
    unittest.main()
