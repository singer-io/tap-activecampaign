from datetime import timedelta
import pytz
import math
import singer
from singer import metrics, metadata, Transformer, utils
from singer.utils import strptime_to_utc, strftime
from tap_activecampaign.transform import transform_json
from tap_activecampaign.streams import STREAMS

LOGGER = singer.get_logger()

def write_schema(catalog, stream_name):
    stream = catalog.get_stream(stream_name)
    schema = stream.schema.to_dict()
    try:
        singer.write_schema(stream_name, schema, stream.key_properties)
    except OSError as err:
        LOGGER.error('OS Error writing schema for: {}'.format(stream_name))
        raise err


def write_record(stream_name, record, time_extracted):
    try:
        singer.messages.write_record(stream_name, record, time_extracted=time_extracted)
    except OSError as err:
        LOGGER.error('OS Error writing record for: {}'.format(stream_name))
        LOGGER.error('Stream: {}, record: {}'.format(stream_name, record))
        raise err
    except TypeError as err:
        LOGGER.error('Type Error writing record for: {}'.format(stream_name))
        LOGGER.error('Stream: {}, record: {}'.format(stream_name, record))
        raise err


def get_bookmark(state, stream, default):
    if (state is None) or ('bookmarks' not in state):
        return default
    return (
        state
        .get('bookmarks', {})
        .get(stream, default)
    )


def write_bookmark(state, stream, value):
    if 'bookmarks' not in state:
        state['bookmarks'] = {}
    state['bookmarks'][stream] = value
    LOGGER.info('Write state for stream: {}, value: {}'.format(stream, value))
    singer.write_state(state)


def transform_datetime(this_dttm):
    with Transformer() as transformer:
        new_dttm = transformer._transform_datetime(this_dttm)
    return new_dttm


def process_records(catalog, #pylint: disable=too-many-branches
                    stream_name,
                    records,
                    time_extracted,
                    bookmark_field=None,
                    max_bookmark_value=None,
                    last_datetime=None,
                    parent=None,
                    parent_id=None):
    stream = catalog.get_stream(stream_name)
    schema = stream.schema.to_dict()
    stream_metadata = metadata.to_map(stream.metadata)

    with metrics.record_counter(stream_name) as counter:
        for record in records:
            # If child object, add parent_id to record
            if parent_id and parent:
                record[parent + '_id'] = parent_id

            # Transform record for Singer.io
            with Transformer() as transformer:
                try:
                    transformed_record = transformer.transform(
                        record,
                        schema,
                        stream_metadata)
                except Exception as err:
                    LOGGER.error('Transformer Error: {}'.format(err))
                    LOGGER.error('Stream: {}, record: {}'.format(stream_name, record))
                    raise err

                # Reset max_bookmark_value to new value if higher
                if transformed_record.get(bookmark_field):
                    if max_bookmark_value is None or \
                        transformed_record[bookmark_field] > transform_datetime(max_bookmark_value):
                        max_bookmark_value = transformed_record[bookmark_field]

                if bookmark_field and (bookmark_field in transformed_record):
                    last_dttm = transform_datetime(last_datetime)
                    bookmark_dttm = transform_datetime(transformed_record[bookmark_field])
                    # Keep only records whose bookmark is after the last_datetime
                    if bookmark_dttm:
                        if bookmark_dttm >= last_dttm:
                            write_record(stream_name, transformed_record, \
                                time_extracted=time_extracted)
                            counter.increment()
                else:
                    write_record(stream_name, transformed_record, time_extracted=time_extracted)
                    counter.increment()

        return max_bookmark_value, counter.value


# Sync a specific parent or child endpoint.
def sync_endpoint(
        client,
        catalog,
        state,
        start_date,
        stream_name,
        path,
        endpoint_config,
        bookmark_field,
        selected_streams=None,
        parent=None,
        parent_id=None):

    static_params = endpoint_config.get('params', {})
    data_key = endpoint_config.get('data_key', stream_name)
    id_fields = endpoint_config.get('key_properties')
    bookmark_query_field = endpoint_config.get('bookmark_query_field')
    created_timestamp_field = endpoint_config.get('created_timestamp')

    # Get the latest bookmark for the stream and set the last_integer/datetime
    last_datetime = None
    max_bookmark_value = None

    last_datetime = get_bookmark(state, stream_name, start_date)
    max_bookmark_value = last_datetime
    LOGGER.info('stream: {}, bookmark_field: {}, last_datetime: {}'.format(
         stream_name, bookmark_field, last_datetime))
    now_datetime = utils.now()
    last_dttm = strptime_to_utc(last_datetime)
    endpoint_total = 0

    # pagination: loop thru all pages of data
    # Pagination reference: https://developers.activecampaign.com/reference#pagination
    # Each page has an offset (starting value) and a limit (batch size, number of records)
    # Increase the "offset" by the "limit" for each batch.
    # Continue until the "record_count" returned < "limit" is null/zero or 
    offset = 0 # Starting offset value for each batch API call
    limit = 100 # Batch size; Number of records per API call; Max = 100
    total_records = 0 # Initialize total
    record_count = limit # Initialize, reset for each API call
    page = 1

    while offset <= total_records: # break out of loop when record_count < limit (or not data returned)
        params = {
            'offset': offset,
            'limit': limit,
            **static_params # adds in endpoint specific, sort, filter params
        }

        if bookmark_query_field:
            params[bookmark_query_field] = last_datetime

        # Need URL querystring for 1st page; subsequent pages provided by next_url
        # querystring: Squash query params into string
        querystring = None
        querystring = '&'.join(['%s=%s' % (key, value) for (key, value) in params.items()])

        LOGGER.info('URL for Stream {}: {}{}{}'.format(
            stream_name,
            client.base_url,
            path,
            '?{}'.format(querystring) if params else ''))

        # API request data
        data = {}
        data = client.get(
            path=path,
            params=querystring,
            endpoint=stream_name)

        # time_extracted: datetime when the data was extracted from the API
        time_extracted = utils.now()
        if not data or data is None or data == {}:
            break # No data results

        # Transform data with transform_json from transform.py
        # The data_key identifies the array/list of records below the <root> element
        # LOGGER.info('data = {}'.format(data)) # TESTING, comment out
        transformed_data = [] # initialize the record list
        data_list = []
        data_dict = {}
        if data_key in data:
            if isinstance(data[data_key], list):
                transformed_data = transform_json(data, stream_name, data_key)
            elif isinstance(data[data_key], dict):
                data_list.append(data[data_key])
                data_dict[data_key] = data_list
                transformed_data = transform_json(data_dict, stream_name, data_key)
        else: # data_key not in data
            if isinstance(data, list):
                data_list = data
                data_dict[data_key] = data_list
                transformed_data = transform_json(data_dict, stream_name, data_key)
            elif isinstance(data, dict):
                data_list.append(data)
                data_dict[data_key] = data_list
                transformed_data = transform_json(data_dict, stream_name, data_key)

        # LOGGER.info('transformed_data = {}'.format(transformed_data)) # TESTING, comment out
        if not transformed_data or transformed_data is None:
            LOGGER.info('No transformed data for data = {}'.format(data))
            break # No data results

        i = 0
        for record in transformed_data:
            # Some endpoints update date is null upon creation
            if bookmark_field:
                created_value = None
                if created_timestamp_field:
                    created_value = record.get(created_timestamp_field)
                bookmark_value = record.get(bookmark_field)
                if not bookmark_value:
                    transformed_data[i][bookmark_field] = created_value
            # Verify key id_fields are present
            for key in id_fields:
                if not record.get(key):
                    LOGGER.error('Stream: {}, Missing key {} in record: {}'.format(
                        stream_name, key, record))
                    raise RuntimeError
            i = i + 1

        # Process records and get the max_bookmark_value and record_count for the set of records
        max_bookmark_value, record_count = process_records(
            catalog=catalog,
            stream_name=stream_name,
            records=transformed_data,
            time_extracted=time_extracted,
            bookmark_field=bookmark_field,
            max_bookmark_value=max_bookmark_value,
            last_datetime=last_datetime,
            parent=parent,
            parent_id=parent_id)
        LOGGER.info('Stream {}, batch processed {} records'.format(
            stream_name, record_count))
        endpoint_total = endpoint_total + record_count

        # Loop thru parent batch records for each children objects (if should stream)
        children = endpoint_config.get('children')
        if children:
            for child_stream_name, child_endpoint_config in children.items():
                if child_stream_name in selected_streams:
                    LOGGER.info('START Syncing: {}'.format(child_stream_name))
                    write_schema(catalog, child_stream_name)
                    # For each parent record
                    for record in transformed_data:
                        i = 0
                        # Set parent_id
                        for id_field in id_fields:
                            if i == 0:
                                parent_id_field = id_field
                            if id_field == 'id':
                                parent_id_field = id_field
                            i = i + 1
                        parent_id = record.get(parent_id_field)

                        # sync_endpoint for child
                        LOGGER.info(
                            'START Sync for Stream: {}, parent_stream: {}, parent_id: {}'\
                                .format(child_stream_name, stream_name, parent_id))
                        child_path = child_endpoint_config.get(
                            'path', child_stream_name).format(str(parent_id))
                        child_bookmark_field = next(iter(child_endpoint_config.get(
                            'replication_keys', [])), None)
                        child_total_records = sync_endpoint(
                            client=client,
                            catalog=catalog,
                            state=state,
                            start_date=start_date,
                            stream_name=child_stream_name,
                            path=child_path,
                            endpoint_config=child_endpoint_config,
                            bookmark_field=child_bookmark_field,
                            selected_streams=selected_streams,
                            parent=child_endpoint_config.get('parent'),
                            parent_id=parent_id)
                        LOGGER.info(
                            'FINISHED Sync for Stream: {}, parent_id: {}, total_records: {}'\
                                .format(child_stream_name, parent_id, child_total_records))
                        # End transformed data record loop
                    # End if child in selected streams
                # End child streams for parent
            # End if children

        # Parent record batch
        # Get pagination details
        api_total = int(data.get('meta', {}).get('total', 0))
        if api_total == 0:
            total_records = record_count
        else:
            total_records = api_total

        # to_rec: to record; ending record for the batch page
        to_rec = offset + limit
        if to_rec > total_records:
            to_rec = total_records

        LOGGER.info('Synced Stream: {}, page: {}, {} to {} of total records: {}'.format(
            stream_name,
            page,
            offset,
            to_rec,
            total_records))
        # Pagination: increment the offset by the limit (batch-size) and page
        offset = offset + limit
        page = page + 1
        # End page/batch - while next URL loop

    # Update the state with the max_bookmark_value for the endpoint
    # ActiveCampaign API does not allow page/batch sorting; bookmark written for endpoint
    if bookmark_field:
        write_bookmark(state, stream_name, max_bookmark_value)

    # Return total_records (for all pages and date windows)
    return endpoint_total


# Currently syncing sets the stream currently being delivered in the state.
# If the integration is interrupted, this state property is used to identify
#  the starting point to continue from.
# Reference: https://github.com/singer-io/singer-python/blob/master/singer/bookmarks.py#L41-L46
def update_currently_syncing(state, stream_name):
    if (stream_name is None) and ('currently_syncing' in state):
        del state['currently_syncing']
    else:
        singer.set_currently_syncing(state, stream_name)
    singer.write_state(state)


def sync(client, config, catalog, state):
    start_date = config.get('start_date')

    # Get selected_streams from catalog, based on state last_stream
    #   last_stream = Previous currently synced stream, if the load was interrupted
    last_stream = singer.get_currently_syncing(state)
    LOGGER.info('last/currently syncing stream: {}'.format(last_stream))
    selected_streams = []
    for stream in catalog.get_selected_streams(state):
        selected_streams.append(stream.stream)
    LOGGER.info('selected_streams: {}'.format(selected_streams))

    if not selected_streams or selected_streams == []:
        return

    # Loop through endpoints in selected_streams
    for stream_name, endpoint_config in STREAMS.items():
        if stream_name in selected_streams:
            LOGGER.info('START Syncing: {}'.format(stream_name))
            write_schema(catalog, stream_name)
            update_currently_syncing(state, stream_name)
            path = endpoint_config.get('path', stream_name)
            bookmark_field = next(iter(endpoint_config.get('replication_keys', [])), None)
            total_records = sync_endpoint(
                client=client,
                catalog=catalog,
                state=state,
                start_date=start_date,
                stream_name=stream_name,
                path=path,
                endpoint_config=endpoint_config,
                bookmark_field=bookmark_field,
                selected_streams=selected_streams)

            update_currently_syncing(state, None)
            LOGGER.info('FINISHED Syncing: {}, total_records: {}'.format(
                stream_name,
                total_records))
