
import singer

from tap_activecampaign.streams import STREAMS, SUB_STREAMS

LOGGER = singer.get_logger()

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
    for stream_name in selected_streams:

        # parent stream will sync sub stream
        if stream_name in SUB_STREAMS.values():
            continue
        LOGGER.info('START Syncing: {}'.format(stream_name))
        
        stream_obj = STREAMS[stream_name](client)
        stream_obj.write_schema(catalog, stream_name)
        update_currently_syncing(state, stream_name)
        
        total_records = stream_obj.sync(
            client=client,
            catalog=catalog,
            state=state,
            start_date=start_date,
            path=stream_obj.path,
            selected_streams=selected_streams)

        update_currently_syncing(state, None)
        LOGGER.info('FINISHED Syncing: {}, total_records: {}'.format(
            stream_name,
            total_records))
