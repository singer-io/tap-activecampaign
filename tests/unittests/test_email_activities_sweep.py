import copy
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from singer import utils
from singer.catalog import Catalog, CatalogEntry, Schema

from tap_activecampaign.exceptions import ActiveCampaignForbiddenError
from tap_activecampaign.schema import get_schemas
from tap_activecampaign.streams import EmailActivities

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
        return [int(p.split('filters[subscriberid]=')[1].split('&')[0]) for p in self._calls('emailActivities')]

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


if __name__ == '__main__':
    unittest.main()
