import unittest
from unittest.mock import MagicMock, patch
from tap_activecampaign.client import ActiveCampaignForbiddenError, ActiveCampaignUnauthorizedError
from tap_activecampaign.discover import (
    check_stream_access,
    _get_accessible_streams,
    discover,
    ActiveCampaignDiscoveryForbiddenError,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_client(side_effect=None, return_value=None):
    """Return a MagicMock client whose .get() behaves as requested."""
    client = MagicMock()
    if side_effect is not None:
        client.get.side_effect = side_effect
    elif return_value is not None:
        client.get.return_value = return_value
    else:
        client.get.return_value = {}
    return client


def _make_stream_cls(path):
    """Return a minimal mock stream class with a path attribute."""
    cls = MagicMock()
    cls.path = path
    return cls


# ---------------------------------------------------------------------------
# TestCheckStreamAccess
# ---------------------------------------------------------------------------

class TestCheckStreamAccess(unittest.TestCase):
    """Unit tests for check_stream_access()."""

    def test_returns_true_when_accessible(self):
        """A successful GET returns True."""
        client = _make_client(return_value={'contacts': []})
        result = check_stream_access(client, 'contacts', 'contacts')
        self.assertTrue(result)
        client.get.assert_called_once_with(path='contacts', params='limit=1', endpoint='contacts')

    def test_returns_false_on_forbidden_error(self):
        """A 403 ForbiddenError returns False without re-raising."""
        client = _make_client(side_effect=ActiveCampaignForbiddenError('403 Forbidden'))
        result = check_stream_access(client, 'contacts', 'contacts')
        self.assertFalse(result)

    def test_returns_false_on_unauthorized_error(self):
        """A 401 UnauthorizedError returns False without re-raising."""
        client = _make_client(side_effect=ActiveCampaignUnauthorizedError('401 Unauthorized'))
        result = check_stream_access(client, 'contacts', 'contacts')
        self.assertFalse(result)

    def test_reraises_unexpected_exception(self):
        """Any other exception is re-raised to the caller."""
        client = _make_client(side_effect=RuntimeError('unexpected'))
        with self.assertRaises(RuntimeError):
            check_stream_access(client, 'contacts', 'contacts')


# ---------------------------------------------------------------------------
# TestGetAccessibleStreams
# ---------------------------------------------------------------------------

# Minimal schema fixture: two parent streams + one child stream
SCHEMAS = {
    'stream_a': {'type': 'object', 'properties': {}},
    'stream_b': {'type': 'object', 'properties': {}},
    'child_of_a': {'type': 'object', 'properties': {}},
}

FLAT_STREAMS = {
    'stream_a':   {'key_properties': ['id'], 'parent_tap_stream_id': None},
    'stream_b':   {'key_properties': ['id'], 'parent_tap_stream_id': None},
    'child_of_a': {'key_properties': ['id'], 'parent_tap_stream_id': 'stream_a'},
}

MOCK_STREAMS = {
    'stream_a':   _make_stream_cls('path/a'),
    'stream_b':   _make_stream_cls('path/b'),
    'child_of_a': _make_stream_cls('path/a/{}/child'),
}


@patch('tap_activecampaign.discover.STREAMS', MOCK_STREAMS)
class TestGetAccessibleStreams(unittest.TestCase):
    """Unit tests for _get_accessible_streams()."""

    def test_all_parent_streams_accessible(self):
        """Returns all schemas (including child) when all parent streams are accessible."""
        client = _make_client(return_value={})
        result = _get_accessible_streams(client, SCHEMAS, FLAT_STREAMS)
        self.assertEqual(set(result.keys()), {'stream_a', 'stream_b', 'child_of_a'})

    def test_child_stream_not_probed(self):
        """Child streams are skipped during probing (their path requires a parent id)."""
        client = _make_client(return_value={})
        _get_accessible_streams(client, SCHEMAS, FLAT_STREAMS)
        probe_paths = [c.kwargs.get('path') or c.args[0] for c in client.get.call_args_list]
        self.assertNotIn('path/a/{}/child', probe_paths)

    def test_inaccessible_parent_excluded_from_catalog(self):
        """An inaccessible parent stream is removed from the returned schemas."""
        def selective_forbidden(path, **kwargs):
            if path == 'path/b':
                raise ActiveCampaignForbiddenError('403')
            return {}
        client = _make_client(side_effect=selective_forbidden)
        result = _get_accessible_streams(client, SCHEMAS, FLAT_STREAMS)
        self.assertNotIn('stream_b', result)
        self.assertIn('stream_a', result)

    def test_child_excluded_when_parent_inaccessible(self):
        """Child stream is excluded when its parent is inaccessible."""
        def block_stream_a(path, **kwargs):
            if path == 'path/a':
                raise ActiveCampaignForbiddenError('403')
            return {}
        client = _make_client(side_effect=block_stream_a)
        result = _get_accessible_streams(client, SCHEMAS, FLAT_STREAMS)
        self.assertNotIn('stream_a', result)
        self.assertNotIn('child_of_a', result)
        self.assertIn('stream_b', result)

    def test_warning_logged_for_inaccessible_streams(self):
        """A warning is logged listing the inaccessible streams."""
        client = _make_client(side_effect=ActiveCampaignForbiddenError('403'))
        # stream_b is the only accessible one; stream_a blocked → that means all are blocked
        # Use only stream_b accessible to verify warning content
        schemas_two = {'stream_a': SCHEMAS['stream_a'], 'stream_b': SCHEMAS['stream_b']}
        flat_two = {'stream_a': FLAT_STREAMS['stream_a'], 'stream_b': FLAT_STREAMS['stream_b']}

        def block_a_only(path, **kwargs):
            if path == 'path/a':
                raise ActiveCampaignForbiddenError('403')
            return {}

        client = _make_client(side_effect=block_a_only)
        with patch('tap_activecampaign.discover.LOGGER') as mock_logger:
            _get_accessible_streams(client, schemas_two, flat_two)
            warning_call = mock_logger.warning.call_args
            self.assertIn('stream_a', warning_call[0][1])

    def test_raises_when_all_streams_inaccessible(self):
        """Raises ActiveCampaignDiscoveryForbiddenError when no streams are accessible."""
        client = _make_client(side_effect=ActiveCampaignForbiddenError('403'))
        # Only parent streams in schemas (no children that could survive)
        schemas_parents = {
            'stream_a': SCHEMAS['stream_a'],
            'stream_b': SCHEMAS['stream_b'],
        }
        flat_parents = {
            'stream_a': FLAT_STREAMS['stream_a'],
            'stream_b': FLAT_STREAMS['stream_b'],
        }
        with self.assertRaises(ActiveCampaignDiscoveryForbiddenError):
            _get_accessible_streams(client, schemas_parents, flat_parents)


# ---------------------------------------------------------------------------
# TestDiscover
# ---------------------------------------------------------------------------

# Minimal schema returned by get_schemas() for discover() tests
_MINIMAL_SCHEMA_DICT = {'type': 'object', 'properties': {'id': {'type': 'integer'}}}
_MINIMAL_SCHEMAS = {'contacts': _MINIMAL_SCHEMA_DICT}
_MINIMAL_FIELD_METADATA = {'contacts': []}
_MINIMAL_FLAT_STREAMS = {'contacts': {'key_properties': ['id'], 'parent_tap_stream_id': None}}


class TestDiscover(unittest.TestCase):
    """Unit tests for discover()."""

    @patch('tap_activecampaign.discover.flatten_streams', return_value=_MINIMAL_FLAT_STREAMS)
    @patch('tap_activecampaign.discover.get_schemas',
           return_value=(_MINIMAL_SCHEMAS, _MINIMAL_FIELD_METADATA))
    def test_discover_with_client_calls_get_accessible_streams(self, mock_schemas, mock_flat):
        """When a client is provided, _get_accessible_streams is called."""
        client = _make_client()
        with patch('tap_activecampaign.discover._get_accessible_streams',
                   return_value=_MINIMAL_SCHEMAS) as mock_access:
            discover(client=client)
            mock_access.assert_called_once_with(client, _MINIMAL_SCHEMAS, _MINIMAL_FLAT_STREAMS)

    @patch('tap_activecampaign.discover.STREAMS',
           {'contacts': _make_stream_cls('contacts')})
    @patch('tap_activecampaign.discover.flatten_streams', return_value=_MINIMAL_FLAT_STREAMS)
    @patch('tap_activecampaign.discover.get_schemas',
           return_value=(_MINIMAL_SCHEMAS, _MINIMAL_FIELD_METADATA))
    def test_discover_with_client_accessible_stream_in_catalog(self, mock_schemas, mock_flat):
        """Accessible stream appears in catalog when client is provided."""
        client = _make_client(return_value={})
        catalog = discover(client=client)
        stream_ids = [s.tap_stream_id for s in catalog.streams]
        self.assertIn('contacts', stream_ids)

    @patch('tap_activecampaign.discover.STREAMS',
           {'contacts': _make_stream_cls('contacts')})
    @patch('tap_activecampaign.discover.flatten_streams', return_value=_MINIMAL_FLAT_STREAMS)
    @patch('tap_activecampaign.discover.get_schemas',
           return_value=(_MINIMAL_SCHEMAS, _MINIMAL_FIELD_METADATA))
    def test_discover_with_client_inaccessible_stream_raises(self, mock_schemas, mock_flat):
        """Raises ActiveCampaignDiscoveryForbiddenError when the only stream is inaccessible."""
        client = _make_client(side_effect=ActiveCampaignForbiddenError('403'))
        with self.assertRaises(ActiveCampaignDiscoveryForbiddenError):
            discover(client=client)
