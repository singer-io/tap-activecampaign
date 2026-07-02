import singer
from singer.catalog import Catalog, CatalogEntry, Schema
from tap_activecampaign.schema import get_schemas
from tap_activecampaign.streams import STREAMS, flatten_streams
from tap_activecampaign.exceptions import ActiveCampaignDiscoveryForbiddenError

LOGGER = singer.get_logger()


def _prune_inaccessible_children(schemas: dict, field_metadata: dict) -> None:
    """
    Remove child streams from the catalog whose parent stream was excluded.
    Mutates schemas and field_metadata in place.
    """
    for name, stream_cls in list(STREAMS.items()):
        if name in schemas and stream_cls.parent and stream_cls.parent not in schemas:
            LOGGER.warning(
                "Stream '%s' excluded from catalog because its parent stream '%s' is not accessible.",
                name, stream_cls.parent,
            )
            schemas.pop(name)
            field_metadata.pop(name)


def _apply_access_checks(client, schemas: dict, field_metadata: dict) -> None:
    """
    Probe each parent stream for read access and remove inaccessible streams
    (and their children) from schemas and field_metadata in place.
    Raises ActiveCampaignDiscoveryForbiddenError if no parent streams are accessible.
    """
    inaccessible_streams = [
        stream_name
        for stream_name, stream_obj in STREAMS.items()
        if stream_name in schemas
        and not stream_obj(client=client).check_access()
    ]

    for stream_name in inaccessible_streams:
        schemas.pop(stream_name, None)
        field_metadata.pop(stream_name, None)

    _prune_inaccessible_children(schemas, field_metadata)

    if inaccessible_streams:
        total_parent_streams = len([s for s in STREAMS.values() if not s.parent])
        if len(inaccessible_streams) == total_parent_streams:
            raise ActiveCampaignDiscoveryForbiddenError(
                "HTTP-error-code: 403, Error: The credentials do not have 'read' access to any supported streams."
            )
        LOGGER.warning(
            "Unauthorized streams have been excluded: %s",
            ", ".join(inaccessible_streams),
        )


def discover(client):
    schemas, field_metadata = get_schemas()
    _apply_access_checks(client, schemas, field_metadata)

    catalog = Catalog([])
    flat_streams = flatten_streams()

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
