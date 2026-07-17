import unittest
from unittest.mock import MagicMock, patch
from tap_activecampaign.exceptions import (
    ActiveCampaignForbiddenError,
    ActiveCampaignUnauthorizedError,
    ActiveCampaignDiscoveryForbiddenError,
)
from tap_activecampaign.streams import ActiveCampaign
from tap_activecampaign.discover import (
    _prune_inaccessible_children,
    _apply_access_checks,
    discover,
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


def _make_stream_instance(stream_name, path, parent=None, client=None):
    """Return an ActiveCampaign base instance with the given attributes set."""
    instance = ActiveCampaign(client=client or _make_client())
    instance.stream_name = stream_name
    instance.path = path
    instance.parent = parent
    return instance


def _make_stream_cls(parent=None, accessible=True):
    """Return a mock stream *class* with a .parent attribute and check_access() behaviour."""
    inst = MagicMock()
    inst.check_access.return_value = accessible
    inst.parent = parent
    cls = MagicMock(return_value=inst)
    cls.parent = parent
    return cls


# ---------------------------------------------------------------------------
# TestCheckAccess
# ---------------------------------------------------------------------------

class TestCheckAccess(unittest.TestCase):
    """Unit tests for ActiveCampaign.check_access()."""

    def test_returns_true_when_accessible(self):
        """A successful GET returns True."""
        client = _make_client(return_value={})
        stream = _make_stream_instance('contacts', 'contacts', client=client)
        self.assertTrue(stream.check_access())
        client.get.assert_called_once_with(
            path='contacts', params={'limit': 1}, endpoint='contacts'
        )

    def test_child_stream_always_returns_true_without_calling_api(self):
        """Child streams always return True; the API is never called."""
        client = _make_client()
        stream = _make_stream_instance(
            'ecommerce_order_products',
            'ecomOrders/{}/orderProducts',
            parent='ecommerce_orders',
            client=client,
        )
        self.assertTrue(stream.check_access())
        client.get.assert_not_called()

    def test_returns_false_on_forbidden_error(self):
        """A 403 ForbiddenError returns False without re-raising."""
        client = _make_client(side_effect=ActiveCampaignForbiddenError('403 Forbidden'))
        stream = _make_stream_instance('contacts', 'contacts', client=client)
        self.assertFalse(stream.check_access())

    def test_returns_false_on_unauthorized_error(self):
        """A 401 UnauthorizedError returns False without re-raising."""
        client = _make_client(side_effect=ActiveCampaignUnauthorizedError('401 Unauthorized'))
        stream = _make_stream_instance('contacts', 'contacts', client=client)
        self.assertFalse(stream.check_access())

    def test_reraises_unexpected_exception(self):
        """Non-auth exceptions are re-raised to the caller."""
        client = _make_client(side_effect=RuntimeError('network failure'))
        stream = _make_stream_instance('contacts', 'contacts', client=client)
        with self.assertRaises(RuntimeError):
            stream.check_access()

    def test_warning_logged_on_forbidden(self):
        """A WARNING is emitted containing the stream name when access is denied."""
        client = _make_client(side_effect=ActiveCampaignForbiddenError('403'))
        stream = _make_stream_instance('contacts', 'contacts', client=client)
        with patch('tap_activecampaign.streams.LOGGER') as mock_logger:
            stream.check_access()
            mock_logger.warning.assert_called_once()
            self.assertIn('contacts', mock_logger.warning.call_args[0][1])


# ---------------------------------------------------------------------------
# TestPruneInaccessibleChildren
# ---------------------------------------------------------------------------

_MOCK_STREAMS_PRUNE = {
    'parent_a': _make_stream_cls(parent=None),
    'parent_b': _make_stream_cls(parent=None),
    'child_of_a': _make_stream_cls(parent='parent_a'),
    'child_of_b': _make_stream_cls(parent='parent_b'),
}


@patch('tap_activecampaign.discover.STREAMS', _MOCK_STREAMS_PRUNE)
class TestPruneInaccessibleChildren(unittest.TestCase):
    """Unit tests for _prune_inaccessible_children(schemas, field_metadata)."""

    def test_child_included_when_parent_accessible(self):
        """Child stays in schemas when its parent is still present."""
        schemas = {'parent_a': {}, 'parent_b': {}, 'child_of_a': {}, 'child_of_b': {}}
        field_metadata = {'parent_a': [], 'parent_b': [], 'child_of_a': [], 'child_of_b': []}
        _prune_inaccessible_children(schemas, field_metadata)
        self.assertIn('child_of_a', schemas)
        self.assertIn('child_of_b', schemas)

    def test_child_excluded_when_parent_already_popped(self):
        """Child is popped from schemas and field_metadata when its parent is absent."""
        # Simulate parent_a already removed by _apply_access_checks
        schemas = {'parent_b': {}, 'child_of_a': {}, 'child_of_b': {}}
        field_metadata = {'parent_b': [], 'child_of_a': [], 'child_of_b': []}
        _prune_inaccessible_children(schemas, field_metadata)
        self.assertNotIn('child_of_a', schemas)
        self.assertNotIn('child_of_a', field_metadata)
        self.assertIn('child_of_b', schemas)

    def test_warning_logged_for_excluded_child(self):
        """A WARNING names both the excluded child and the inaccessible parent."""
        schemas = {'parent_b': {}, 'child_of_a': {}, 'child_of_b': {}}
        field_metadata = {'parent_b': [], 'child_of_a': [], 'child_of_b': []}
        with patch('tap_activecampaign.discover.LOGGER') as mock_logger:
            _prune_inaccessible_children(schemas, field_metadata)
            mock_logger.warning.assert_called_once()
            args = mock_logger.warning.call_args[0]
            self.assertIn('child_of_a', args[1])
            self.assertIn('parent_a', args[2])

    def test_no_warning_when_all_parents_accessible(self):
        """No WARNING is emitted when every parent is present in schemas."""
        schemas = {'parent_a': {}, 'parent_b': {}, 'child_of_a': {}, 'child_of_b': {}}
        field_metadata = {'parent_a': [], 'parent_b': [], 'child_of_a': [], 'child_of_b': []}
        with patch('tap_activecampaign.discover.LOGGER') as mock_logger:
            _prune_inaccessible_children(schemas, field_metadata)
            mock_logger.warning.assert_not_called()


# ---------------------------------------------------------------------------
# TestApplyAccessChecks
# ---------------------------------------------------------------------------

_MOCK_STREAMS_APPLY = {
    'stream_a': _make_stream_cls(parent=None, accessible=True),
    'stream_b': _make_stream_cls(parent=None, accessible=True),
}


@patch('tap_activecampaign.discover.STREAMS', _MOCK_STREAMS_APPLY)
class TestApplyAccessChecks(unittest.TestCase):
    """Unit tests for _apply_access_checks(client, schemas, field_metadata)."""

    def _schemas_and_meta(self, names):
        return {n: {} for n in names}, {n: [] for n in names}

    def test_accessible_streams_remain_in_schemas(self):
        """All streams stay in schemas when all return check_access() == True."""
        schemas, field_metadata = self._schemas_and_meta(['stream_a', 'stream_b'])
        _apply_access_checks(_make_client(), schemas, field_metadata)
        self.assertIn('stream_a', schemas)
        self.assertIn('stream_b', schemas)

    def test_inaccessible_stream_popped_from_schemas(self):
        """Inaccessible stream is removed from both schemas and field_metadata."""
        mock_streams = {
            'stream_a': _make_stream_cls(parent=None, accessible=False),
            'stream_b': _make_stream_cls(parent=None, accessible=True),
        }
        schemas, field_metadata = self._schemas_and_meta(['stream_a', 'stream_b'])
        with patch('tap_activecampaign.discover.STREAMS', mock_streams):
            _apply_access_checks(_make_client(), schemas, field_metadata)
        self.assertNotIn('stream_a', schemas)
        self.assertNotIn('stream_a', field_metadata)
        self.assertIn('stream_b', schemas)

    def test_all_inaccessible_raises_forbidden(self):
        """Raises ActiveCampaignDiscoveryForbiddenError when all parent streams are inaccessible."""
        mock_streams = {
            'stream_a': _make_stream_cls(parent=None, accessible=False),
            'stream_b': _make_stream_cls(parent=None, accessible=False),
        }
        schemas, field_metadata = self._schemas_and_meta(['stream_a', 'stream_b'])
        with patch('tap_activecampaign.discover.STREAMS', mock_streams):
            with self.assertRaises(ActiveCampaignDiscoveryForbiddenError):
                _apply_access_checks(_make_client(), schemas, field_metadata)

    def test_child_excluded_when_parent_inaccessible(self):
        """Child stream is pruned from schemas when its parent is inaccessible."""
        mock_streams = {
            'stream_a': _make_stream_cls(parent=None, accessible=False),
            'stream_b': _make_stream_cls(parent=None, accessible=True),
            'child_of_a': _make_stream_cls(parent='stream_a', accessible=True),
        }
        schemas = {'stream_a': {}, 'stream_b': {}, 'child_of_a': {}}
        field_metadata = {'stream_a': [], 'stream_b': [], 'child_of_a': []}
        with patch('tap_activecampaign.discover.STREAMS', mock_streams):
            _apply_access_checks(_make_client(), schemas, field_metadata)
        self.assertNotIn('stream_a', schemas)
        self.assertNotIn('child_of_a', schemas)
        self.assertIn('stream_b', schemas)

    def test_schemas_mutated_in_place(self):
        """Return value is None; the same dict object is mutated (not replaced)."""
        mock_streams = {
            'stream_a': _make_stream_cls(parent=None, accessible=False),
            'stream_b': _make_stream_cls(parent=None, accessible=True),
        }
        schemas, field_metadata = self._schemas_and_meta(['stream_a', 'stream_b'])
        original_id = id(schemas)
        with patch('tap_activecampaign.discover.STREAMS', mock_streams):
            result = _apply_access_checks(_make_client(), schemas, field_metadata)
        self.assertIsNone(result)
        self.assertEqual(id(schemas), original_id)
        self.assertNotIn('stream_a', schemas)
        self.assertIn('stream_b', schemas)

    def test_warning_logged_for_inaccessible_stream(self):
        """A WARNING listing inaccessible streams is emitted when some are excluded."""
        mock_streams = {
            'stream_a': _make_stream_cls(parent=None, accessible=False),
            'stream_b': _make_stream_cls(parent=None, accessible=True),
        }
        schemas, field_metadata = self._schemas_and_meta(['stream_a', 'stream_b'])
        with patch('tap_activecampaign.discover.STREAMS', mock_streams):
            with patch('tap_activecampaign.discover.LOGGER') as mock_logger:
                _apply_access_checks(_make_client(), schemas, field_metadata)
                warning_messages = [str(c) for c in mock_logger.warning.call_args_list]
                self.assertTrue(any('stream_a' in m for m in warning_messages))


# ---------------------------------------------------------------------------
# TestDiscover
# ---------------------------------------------------------------------------

_MINIMAL_SCHEMA_DICT = {'type': 'object', 'properties': {'id': {'type': 'integer'}}}
_MINIMAL_FLAT_STREAMS = {'contacts': {'key_properties': ['id'], 'parent_tap_stream_id': None}}


class TestDiscover(unittest.TestCase):
    """Unit tests for discover()."""

    @patch('tap_activecampaign.discover.flatten_streams', return_value=_MINIMAL_FLAT_STREAMS)
    @patch('tap_activecampaign.discover.get_schemas',
           return_value=({'contacts': _MINIMAL_SCHEMA_DICT}, {'contacts': []}))
    @patch('tap_activecampaign.discover._apply_access_checks')
    def test_accessible_stream_appears_in_catalog(self, mock_access, mock_schemas, mock_flat):
        """Stream not popped by _apply_access_checks appears in catalog."""
        # _apply_access_checks is a no-op: schemas unchanged
        catalog = discover(client=_make_client())
        stream_ids = [s.tap_stream_id for s in catalog.streams]
        self.assertIn('contacts', stream_ids)

    @patch('tap_activecampaign.discover.flatten_streams', return_value=_MINIMAL_FLAT_STREAMS)
    @patch('tap_activecampaign.discover.get_schemas',
           return_value=({'contacts': _MINIMAL_SCHEMA_DICT}, {'contacts': []}))
    def test_inaccessible_stream_excluded_from_catalog(self, mock_schemas, mock_flat):
        """Stream popped by _apply_access_checks is excluded from catalog."""
        def pop_contacts(client, schemas, field_metadata):
            schemas.pop('contacts', None)
            field_metadata.pop('contacts', None)
        with patch('tap_activecampaign.discover._apply_access_checks', side_effect=pop_contacts):
            catalog = discover(client=_make_client())
        stream_ids = [s.tap_stream_id for s in catalog.streams]
        self.assertNotIn('contacts', stream_ids)

    @patch('tap_activecampaign.discover.flatten_streams', return_value=_MINIMAL_FLAT_STREAMS)
    @patch('tap_activecampaign.discover.get_schemas',
           return_value=({'contacts': _MINIMAL_SCHEMA_DICT}, {'contacts': []}))
    def test_all_inaccessible_raises(self, mock_schemas, mock_flat):
        """Raises ActiveCampaignDiscoveryForbiddenError propagated from _apply_access_checks."""
        with patch('tap_activecampaign.discover._apply_access_checks',
                   side_effect=ActiveCampaignDiscoveryForbiddenError('no access')):
            with self.assertRaises(ActiveCampaignDiscoveryForbiddenError):
                discover(client=_make_client())

    @patch('tap_activecampaign.discover.flatten_streams', return_value=_MINIMAL_FLAT_STREAMS)
    @patch('tap_activecampaign.discover.get_schemas',
           return_value=({'contacts': _MINIMAL_SCHEMA_DICT}, {'contacts': []}))
    def test_apply_access_checks_called_with_client_schemas_and_metadata(self, mock_schemas, mock_flat):
        """discover() calls _apply_access_checks(client, schemas, field_metadata)."""
        client = _make_client()
        with patch('tap_activecampaign.discover._apply_access_checks') as mock_access:
            discover(client=client)
            args = mock_access.call_args[0]
            self.assertIs(args[0], client)
            self.assertIsInstance(args[1], dict)
            self.assertIsInstance(args[2], dict)
