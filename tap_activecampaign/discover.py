import singer
from singer.catalog import Catalog, CatalogEntry, Schema
from tap_activecampaign.schema import get_schemas
from tap_activecampaign.streams import flatten_streams

LOGGER = singer.get_logger()

def discover():
    schemas, field_metadata = get_schemas()
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
