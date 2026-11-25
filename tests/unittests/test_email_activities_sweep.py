import copy
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from singer import utils
from singer.catalog import Catalog, CatalogEntry, Schema

from tap_activecampaign.exceptions import ActiveCampaignForbiddenError
from tap_activecampaign.schema import get_schemas
from tap_activecampaign.streams import DEFAULT_MAX_RUNTIME_MINUTES, EmailActivities

START_DATE = '2025-01-01T00:00:00Z'
NOW = datetime(2026, 11, 19, 12, 0, 0, tzinfo=timezone.utc)
KEY = 'email_activities_sweep'


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


def _ts(delta):
    return utils.strftime(NOW - delta)


class TestEmailActivitiesSweep(unittest.TestCase):

    def setUp(self):
        self.client = MagicMock()
        self.client.base_url = 'https://example.api-us1.com/api/3/'
        self.all_contacts = [1, 2, 3, 4, 5]
        self.changed_contacts = []
        self.activities = []
        self.activities_error = None
        self.states = []

    def _fake_get(self, path, params=None, endpoint=None):
        if path == 'contacts':
            last_id = int(params.split('id_greater=')[1].split('&')[0])
            source = self.changed_contacts if 'updated_after' in params else self.all_contacts
            ids = sorted(i for i in source if i > last_id)[:100]
            return {'contacts': [{'id': str(i)} for i in ids]}
        if path == 'activities':
            if self.activities_error:
                raise self.activities_error
            offset = int(params.split('offset=')[1].split('&')[0])
            return {'activities': self.activities[offset:offset + 100]}
        return {'emailActivities': [], 'meta': {'total': '0'}}

    def _run(self, state, **kwargs):
        self.client.get.side_effect = self._fake_get
        with patch('singer.write_schema'), patch('singer.messages.write_record'), \
                patch('singer.write_state', side_effect=lambda s: self.states.append(copy.deepcopy(s))), \
                patch('singer.utils.now', return_value=NOW):
            return EmailActivities(self.client).sync_for_all_contacts(
                _catalog_for('email_activities'), state, START_DATE, **kwargs)

    def _calls(self, path):
        return [c.kwargs['params'] for c in self.client.get.call_args_list if c.kwargs['path'] == path]

    def _requested_contacts(self):
        # Sorted: contacts of one page are requested in parallel, so call order is not fixed.
        return sorted(int(p.split('filters[subscriberid]=')[1].split('&')[0])
                      for p in self._calls('emailActivities'))

    def test_first_run_is_a_full_sweep_and_records_it(self):
        state = {}

        self._run(state)

        self.assertEqual(self._requested_contacts(), [1, 2, 3, 4, 5])
        self.assertEqual(state['bookmarks'][KEY], {'last_full_sweep': _ts(timedelta()), 'last_sync': _ts(timedelta())})
        self.assertEqual(self._calls('activities'), [])

    def test_full_sweep_checkpoints_each_contact_page(self):
        self.all_contacts = list(range(1, 151))
        state = {}

        self._run(state)

        checkpoints = [s['bookmarks'][KEY].get('resume_contact_id') for s in self.states]
        self.assertEqual(checkpoints, [100, 150, None])

    def test_interrupted_full_sweep_resumes_after_checkpoint(self):
        started = _ts(timedelta(hours=20))
        state = {'bookmarks': {KEY: {'full_sweep_started': started, 'resume_contact_id': 3}}}

        self._run(state)

        self.assertEqual(self._requested_contacts(), [4, 5])
        self.assertIn('id_greater=3', self._calls('contacts')[0])
        self.assertEqual(state['bookmarks'][KEY], {'last_full_sweep': started, 'last_sync': started})

    def test_recent_full_sweep_requests_only_changed_contacts(self):
        full = _ts(timedelta(days=1))
        state = {'bookmarks': {KEY: {'last_full_sweep': full, 'last_sync': _ts(timedelta(hours=2))}}}
        self.changed_contacts = [5]
        self.activities = [{'id': '10', 'subscriberid': '2'}, {'id': '11', 'subscriberid': '5'}]

        self._run(state)

        self.assertEqual(self._requested_contacts(), [2, 5])
        self.assertIn('filters[updated_after]=' + _ts(timedelta(hours=3)), self._calls('contacts')[0])
        self.assertIn('after=' + _ts(timedelta(hours=3)), self._calls('activities')[0])
        self.assertEqual(state['bookmarks'][KEY], {'last_full_sweep': full, 'last_sync': _ts(timedelta())})

    def test_incremental_with_nothing_changed_makes_no_email_requests(self):
        state = {'bookmarks': {KEY: {'last_full_sweep': _ts(timedelta(days=1)), 'last_sync': _ts(timedelta(hours=2))}}}

        total = self._run(state)

        self.assertEqual(total, 0)
        self.assertEqual(self._calls('emailActivities'), [])

    def test_activities_without_a_contact_are_ignored(self):
        state = {'bookmarks': {KEY: {'last_full_sweep': _ts(timedelta(days=1)), 'last_sync': _ts(timedelta(hours=2))}}}
        self.activities = [{'id': '1', 'subscriberid': '0'}, {'id': '2', 'subscriberid': None}, {'id': '3'}]

        self._run(state)

        self.assertEqual(self._calls('emailActivities'), [])

    def test_activities_are_paged(self):
        state = {'bookmarks': {KEY: {'last_full_sweep': _ts(timedelta(days=1)), 'last_sync': _ts(timedelta(hours=2))}}}
        self.activities = [{'id': str(i), 'subscriberid': '3'} for i in range(1, 101)] + \
                          [{'id': '101', 'subscriberid': '4'}]

        self._run(state)

        self.assertEqual(self._requested_contacts(), [3, 4])
        self.assertEqual(len(self._calls('activities')), 2)

    def test_full_sweep_when_last_one_is_too_old(self):
        state = {'bookmarks': {KEY: {'last_full_sweep': _ts(timedelta(days=8)), 'last_sync': _ts(timedelta(hours=2))}}}

        self._run(state)

        self.assertEqual(self._requested_contacts(), [1, 2, 3, 4, 5])
        self.assertEqual(state['bookmarks'][KEY]['last_full_sweep'], _ts(timedelta()))

    def test_full_sweep_days_is_configurable(self):
        state = {'bookmarks': {KEY: {'last_full_sweep': _ts(timedelta(days=2)), 'last_sync': _ts(timedelta(hours=2))}}}

        self._run(state, full_sweep_days='1')

        self.assertEqual(self._requested_contacts(), [1, 2, 3, 4, 5])

    def test_zero_days_always_sweeps_every_contact(self):
        state = {'bookmarks': {KEY: {'last_full_sweep': _ts(timedelta(minutes=5)), 'last_sync': _ts(timedelta(minutes=5))}}}

        self._run(state, full_sweep_days=0)

        self.assertEqual(self._requested_contacts(), [1, 2, 3, 4, 5])
        self.assertEqual(self._calls('activities'), [])

    def test_duplicate_activities_do_not_force_a_full_sweep(self):
        state = {'bookmarks': {KEY: {'last_full_sweep': _ts(timedelta(days=1)), 'last_sync': _ts(timedelta(hours=2))}}}
        self.activities = [{'id': str(i), 'subscriberid': '1'} for i in range(1, 100)] + \
                          [{'id': '1', 'subscriberid': '2'}, {'id': '200', 'subscriberid': '3'}]

        self._run(state)

        self.assertEqual(self._requested_contacts(), [1, 2, 3])
        self.assertEqual(state['bookmarks'][KEY]['last_full_sweep'], _ts(timedelta(days=1)))

    def test_activities_paging_that_makes_no_progress_stops(self):
        state = {'bookmarks': {KEY: {'last_full_sweep': _ts(timedelta(days=1)), 'last_sync': _ts(timedelta(hours=2))}}}
        page = [{'id': str(i), 'subscriberid': '4'} for i in range(1, 101)]
        self.client.get.side_effect = lambda path, params=None, endpoint=None: \
            {'activities': page} if path == 'activities' else self._fake_get(path, params, endpoint)

        with patch('singer.write_schema'), patch('singer.messages.write_record'), \
                patch('singer.write_state'), patch('singer.utils.now', return_value=NOW):
            EmailActivities(self.client).sync_for_all_contacts(
                _catalog_for('email_activities'), state, START_DATE)

        self.assertEqual(len(self._calls('activities')), 2)
        self.assertEqual(self._requested_contacts(), [4])

    def test_inaccessible_activities_fall_back_to_full_sweep(self):
        state = {'bookmarks': {KEY: {'last_full_sweep': _ts(timedelta(days=1)), 'last_sync': _ts(timedelta(hours=2))}}}
        self.activities_error = ActiveCampaignForbiddenError('403')

        self._run(state)

        self.assertEqual(self._requested_contacts(), [1, 2, 3, 4, 5])

    def test_malformed_activities_response_fails(self):
        state = {'bookmarks': {KEY: {'last_full_sweep': _ts(timedelta(days=1)), 'last_sync': _ts(timedelta(hours=2))}}}
        self.client.get.side_effect = lambda path, params=None, endpoint=None: \
            {'activities': None} if path == 'activities' else self._fake_get(path, params, endpoint)

        with patch('singer.write_schema'), patch('singer.messages.write_record'), \
                patch('singer.write_state'), patch('singer.utils.now', return_value=NOW):
            with self.assertRaises(RuntimeError):
                EmailActivities(self.client).sync_for_all_contacts(
                    _catalog_for('email_activities'), state, START_DATE)

        self.assertEqual(state['bookmarks'][KEY]['last_sync'], _ts(timedelta(hours=2)))

    def test_failed_incremental_pass_does_not_advance_last_sync(self):
        last_sync = _ts(timedelta(hours=2))
        state = {'bookmarks': {KEY: {'last_full_sweep': _ts(timedelta(days=1)), 'last_sync': last_sync}}}
        self.changed_contacts = [5]
        self.client.get.side_effect = lambda path, params=None, endpoint=None: \
            (_ for _ in ()).throw(RuntimeError('boom')) if path == 'emailActivities' \
            else self._fake_get(path, params, endpoint)

        with patch('singer.write_schema'), patch('singer.messages.write_record'), \
                patch('singer.write_state'), patch('singer.utils.now', return_value=NOW):
            with self.assertRaises(RuntimeError):
                EmailActivities(self.client).sync_for_all_contacts(
                    _catalog_for('email_activities'), state, START_DATE)

        self.assertEqual(state['bookmarks'][KEY]['last_sync'], last_sync)

    def _run_with_clock(self, state, readings, **kwargs):
        """Run with `time.monotonic` returning `readings` in order, then the last reading."""
        values = iter(readings)
        last = [readings[-1]]

        def clock():
            last[0] = next(values, last[0])
            return last[0]

        with patch('tap_activecampaign.streams.time.monotonic', side_effect=clock):
            return self._run(state, **kwargs)

    def test_full_sweep_stops_at_time_limit_and_keeps_checkpoint(self):
        self.all_contacts = list(range(1, 251))
        state = {}

        # Readings: deadline start, then the check before the second page.
        self._run_with_clock(state, [0, 100], max_runtime_minutes=1)

        self.assertEqual(self._requested_contacts(), list(range(1, 101)))
        self.assertEqual(state['bookmarks'][KEY]['resume_contact_id'], 100)
        self.assertNotIn('last_full_sweep', state['bookmarks'][KEY])

    def test_capped_full_sweep_completes_over_several_syncs(self):
        self.all_contacts = list(range(1, 251))
        state = {}

        for _ in range(3):
            self.client.get.reset_mock()
            self._run_with_clock(state, [0, 100], max_runtime_minutes=1)

        self.assertEqual(state['bookmarks'][KEY],
                         {'last_full_sweep': _ts(timedelta()), 'last_sync': _ts(timedelta())})
        self.assertEqual(self._requested_contacts(), list(range(201, 251)))

    def test_time_limit_still_processes_one_page_per_sync(self):
        self.all_contacts = list(range(1, 251))
        state = {}

        self._run_with_clock(state, [0, 10 ** 9], max_runtime_minutes=0.0001)

        self.assertEqual(self._requested_contacts(), list(range(1, 101)))

    def test_zero_minutes_means_no_time_limit(self):
        self.all_contacts = list(range(1, 251))
        state = {}

        self._run_with_clock(state, [0, 10 ** 9], max_runtime_minutes=0)

        self.assertEqual(self._requested_contacts(), list(range(1, 251)))
        self.assertNotIn('resume_contact_id', state['bookmarks'][KEY])

    def test_time_limit_does_not_apply_to_incremental_pass(self):
        state = {'bookmarks': {KEY: {'last_full_sweep': _ts(timedelta(days=1)), 'last_sync': _ts(timedelta(hours=2))}}}
        self.changed_contacts = [1, 2, 3]

        self._run_with_clock(state, [0, 10 ** 9], max_runtime_minutes=1)

        self.assertEqual(self._requested_contacts(), [1, 2, 3])

    def test_default_time_limit_is_applied(self):
        self.all_contacts = list(range(1, 251))
        state = {}
        minutes = DEFAULT_MAX_RUNTIME_MINUTES

        self._run_with_clock(state, [0, minutes * 60 - 1, minutes * 60], max_runtime_minutes=None)

        self.assertEqual(self._requested_contacts(), list(range(1, 201)))
        self.assertEqual(state['bookmarks'][KEY]['resume_contact_id'], 200)

    def test_parallel_workers_request_each_contact_exactly_once(self):
        self.all_contacts = list(range(1, 251))

        self._run({}, workers=4)

        # A duplicate request would mean the prefetched first page was not reused.
        self.assertEqual(len(self._calls('emailActivities')), 250)
        self.assertEqual(self._requested_contacts(), list(range(1, 251)))

    def test_one_worker_requests_contacts_in_order(self):
        self._run({}, workers=1)

        requested = [int(p.split('filters[subscriberid]=')[1]) for p in self._calls('emailActivities')]
        self.assertEqual(requested, [1, 2, 3, 4, 5])

    def test_parallel_workers_process_contacts_in_order(self):
        self.all_contacts = list(range(1, 41))
        processed = []
        real_sync = EmailActivities.sync

        def spy(stream, *args, **kwargs):
            processed.append(int(kwargs['parent_id']))
            return real_sync(stream, *args, **kwargs)

        with patch.object(EmailActivities, 'sync', spy):
            self._run({}, workers=4)

        self.assertEqual(processed, list(range(1, 41)))

    def test_parallel_workers_skip_a_deleted_contact(self):
        from tap_activecampaign.exceptions import ActiveCampaignNotFoundError
        base = self._fake_get

        def get(path, params=None, endpoint=None):
            if path == 'emailActivities' and 'filters[subscriberid]=2' in params:
                raise ActiveCampaignNotFoundError('404')
            return base(path, params, endpoint)

        self._fake_get = get
        self._run({}, workers=3)

        self.assertEqual(self._requested_contacts(), [1, 2, 3, 4, 5])

    def test_parallel_workers_raise_an_error_at_its_contact_and_keep_earlier_work(self):
        processed = []
        real_sync = EmailActivities.sync
        base = self._fake_get

        def get(path, params=None, endpoint=None):
            if path == 'emailActivities' and 'filters[subscriberid]=3' in params:
                raise RuntimeError('boom')
            return base(path, params, endpoint)

        def spy(stream, *args, **kwargs):
            processed.append(int(kwargs['parent_id']))
            return real_sync(stream, *args, **kwargs)

        self._fake_get = get
        state = {}
        with patch.object(EmailActivities, 'sync', spy), self.assertRaises(RuntimeError):
            self._run(state, workers=3)

        self.assertEqual(processed, [1, 2, 3])
        self.assertNotIn('last_full_sweep', state['bookmarks'][KEY])

    def test_parallel_workers_emit_the_same_records_in_the_same_order(self):
        self.all_contacts = list(range(1, 31))
        base = self._fake_get

        def get(path, params=None, endpoint=None):
            if path == 'emailActivities':
                contact = params.split('filters[subscriberid]=')[1]
                rows = [{'id': '{}{}'.format(contact, n), 'subscriberid': contact} for n in range(int(contact) % 4)]
                return {'emailActivities': rows, 'meta': {'total': str(len(rows))}}
            return base(path, params, endpoint)

        self._fake_get = get
        emitted = {}
        for workers in (1, 4):
            with patch('singer.write_schema'), patch('singer.write_state'), \
                    patch('singer.messages.write_record') as write_record, \
                    patch('singer.utils.now', return_value=NOW):
                self.client.get.side_effect = self._fake_get
                EmailActivities(self.client).sync_for_all_contacts(
                    _catalog_for('email_activities'), {}, START_DATE, workers=workers)
            emitted[workers] = [call.args[1]['id'] for call in write_record.call_args_list]

        self.assertTrue(emitted[1])
        self.assertEqual(emitted[4], emitted[1])

    def test_empty_string_settings_use_the_defaults(self):
        state = {}

        self._run(state, full_sweep_days='', max_runtime_minutes='', workers='')

        self.assertEqual(self._requested_contacts(), [1, 2, 3, 4, 5])
        self.assertIn('last_full_sweep', state['bookmarks'][KEY])

    def test_stream_client_is_restored_after_parallel_sync(self):
        stream = EmailActivities(self.client)
        self.client.get.side_effect = self._fake_get

        with patch('singer.write_schema'), patch('singer.messages.write_record'), \
                patch('singer.write_state'), patch('singer.utils.now', return_value=NOW):
            stream.sync_for_all_contacts(_catalog_for('email_activities'), {}, START_DATE, workers=3)

        self.assertIs(stream.client, self.client)


class TestRateLimiter(unittest.TestCase):

    def test_limits_request_starts_across_threads(self):
        import threading
        from tap_activecampaign.client import RateLimiter

        limiter = RateLimiter(5, 1)
        sleeps = []
        with patch('tap_activecampaign.client.time.monotonic', return_value=100.0), \
                patch('tap_activecampaign.client.time.sleep', side_effect=sleeps.append):
            threads = [threading.Thread(target=limiter.wait) for _ in range(12)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()

        # 5 may start immediately, the next 5 one second later, the last 2 two seconds later.
        self.assertEqual(sorted(sleeps), [1.0] * 5 + [2.0] * 2)

    def test_does_not_sleep_below_the_limit(self):
        from tap_activecampaign.client import RateLimiter

        limiter = RateLimiter(5, 1)
        with patch('tap_activecampaign.client.time.sleep') as sleep:
            for _ in range(5):
                limiter.wait()

        sleep.assert_not_called()
