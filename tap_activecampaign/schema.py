import os
import json
import singer
from singer import metadata
from tap_activecampaign.streams import flatten_streams

LOGGER = singer.get_logger()

# Reference:
# https://github.com/singer-io/getting-started/blob/master/docs/DISCOVERY_MODE.md#Metadata

def get_abs_path(path):
    return os.path.join(os.path.dirname(os.path.realpath(__file__)), path)

def get_schemas():
    schemas = {}
    field_metadata = {}

    flat_streams = flatten_streams()
    for stream_name, stream_metadata in flat_streams.items():
        schema_path = get_abs_path('schemas/{}.json'.format(stream_name))
        with open(schema_path) as file:
            schema = json.load(file)
        schemas[stream_name] = schema
        mdata = metadata.new()

        # Documentation:
        # https://github.com/singer-io/getting-started/blob/master/docs/DISCOVERY_MODE.md#singer-python-helper-functions
        # Reference:
        # https://github.com/singer-io/singer-python/blob/master/singer/metadata.py#L25-L44
        mdata = metadata.get_standard_metadata(
            schema=schema,
            key_properties=stream_metadata.get('key_properties', None),
            valid_replication_keys=stream_metadata.get('replication_keys', None),
            replication_method=stream_metadata.get('replication_method', None)
        )
        mdata = metadata.to_map(mdata)
        # Loop through all keys and make replication keys of automatic inclusion
        for field_name in schema['properties'].keys():
            automatic_keys = ((stream_metadata.get('replication_keys') or []) +
                              (stream_metadata.get('additional_automatic_keys') or []))
            if field_name in automatic_keys:
                mdata = metadata.write(mdata, ('properties', field_name), 'inclusion', 'automatic')

        mdata = metadata.to_list(mdata)
        field_metadata[stream_name] = mdata

    return schemas, field_metadata
