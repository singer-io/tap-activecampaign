import singer
from singer.catalog import Catalog, CatalogEntry, Schema
from tap_activecampaign.schema import get_schemas
from tap_activecampaign.streams import STREAMS, flatten_streams
from tap_activecampaign.client import ActiveCampaignForbiddenError, ActiveCampaignUnauthorizedError

LOGGER = singer.get_logger()


class ActiveCampaignDiscoveryForbiddenError(Exception):
    pass


def check_stream_access(client, stream_name, path):
    """
    Return True if the stream endpoint is accessible with the current credentials,
    False if a 403 or 401 response is received.
    Re-raises any other exception.
    """
    try:
        client.get(path=path, params='limit=1', endpoint=stream_name)
        return True
    except (ActiveCampaignForbiddenError, ActiveCampaignUnauthorizedError):
        return False


def _get_accessible_streams(client, schemas, flat_streams):
    """
    Probe each parent stream endpoint to determine which streams the API token
    can access. Returns a filtered copy of `schemas` that excludes inaccessible
    parent streams and any child streams whose parent is inaccessible.

    Raises ActiveCampaignDiscoveryForbiddenError if no streams are accessible.
    """
    inaccessible_streams = []

    for stream_name in list(schemas.keys()):
        # Skip child streams — their paths require a parent record id
        if flat_streams.get(stream_name, {}).get('parent_tap_stream_id'):
            continue

        stream_cls = STREAMS[stream_name]
        if not check_stream_access(client, stream_name, stream_cls.path):
            inaccessible_streams.append(stream_name)

    if inaccessible_streams:
        LOGGER.warning(
            'The following streams are not accessible and will be excluded '
            'from the catalog: %s', ', '.join(inaccessible_streams)
        )

    # Exclude inaccessible parent streams and their child streams
    filtered_schemas = {
        name: schema
        for name, schema in schemas.items()
        if name not in inaccessible_streams
        and flat_streams.get(name, {}).get('parent_tap_stream_id') not in inaccessible_streams
    }

    if not filtered_schemas:
        raise ActiveCampaignDiscoveryForbiddenError(
            'Access denied: no streams are accessible with the provided credentials.'
        )

    return filtered_schemas


def discover(client):
    schemas, field_metadata = get_schemas()
    catalog = Catalog([])

    flat_streams = flatten_streams()
    schemas = _get_accessible_streams(client, schemas, flat_streams)

    for stream_name, schema_dict in schemas.items():
        try:
            schema = Schema.from_dict(schema_dict)
            mdata = field_metadata[stream_name]
        except Exception as err:
            LOGGER.error(err)
            LOGGER.error('stream_name: {}'.format(stream_name))
            LOGGER.error('type schema_dict: {}'.format(type(schema_dict)))
            raise err

        catalog.streams.append(CatalogEntry(
            stream=stream_name,
            tap_stream_id=stream_name,
            key_properties=flat_streams.get(stream_name, {}).get('key_properties', None),
            schema=schema,
            metadata=mdata
        ))

    return catalog
