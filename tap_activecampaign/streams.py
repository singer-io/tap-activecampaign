import singer
from singer import metrics, metadata, Transformer, utils
from singer.utils import strptime_to_utc
from tap_activecampaign.transform import transform_json
from tap_activecampaign.client import ActiveCampaignClient

LOGGER = singer.get_logger()
# streams: API URL endpoints to be called
# properties:
#   <root node>: Plural stream name for the endpoint
#   path: API endpoint relative path, when added to the base URL, creates the full path
#   key_properties: Primary key field(s) for the object endpoint
#   replication_method: FULL_TABLE or INCREMENTAL
#   replication_keys: bookmark_field(s), typically a date-time, used for filtering the results
#        and setting the state
#   params: Query, sort, and other endpoint specific parameters
#   data_key: JSON element containing the records for the endpoint
#   bookmark_query_field: Typically a date-time field used for filtering the query
#   bookmark_type: Data type for bookmark, integer or datetime
#   children: A collection of child endpoints (where the endpoint path includes the parent id)
#   parent: On each of the children, the singular stream name for parent element

class ActiveCampaign:
    """
    A base class representing singer streams.
    :param client: The API client used to extract records from external source
    """
    
    stream_name = None
    replication_method = 'INCREMENTAL'
    replication_keys = None
    key_properties = ['id']
    path = None
    params = {}
    parent = None
    data_key = None
    created_timestamp = None
    bookmark_query_field = None
    links = []
    children = []
    
    def __init__(self, client: ActiveCampaignClient = None):
        self.client = client

    def write_schema(self, catalog, stream_name):
        """ 
        Write a schema message.
        """
        stream = catalog.get_stream(stream_name)
        schema = stream.schema.to_dict()
        try:
            # Example:
            # stream = 'test'
            # schema = {'properties': {'id': {'type': 'integer'}, 'email': {'type': 'string'}}}
            # key_properties = ['id']
            # write_schema(stream, schema, key_properties)
            singer.write_schema(stream_name, schema, stream.key_properties)
        except OSError as err:
            LOGGER.error('OS Error while writing schema for: {}'.format(stream_name))
            raise err
        
    def write_record(self, stream_name, record, time_extracted):
        """
        Write a single record for the given stream.
        Example: write_record("users", {"id": 2, "email": "mike@stitchdata.com"})
        """
        try:
            singer.messages.write_record(stream_name, record, time_extracted=time_extracted)
        except OSError as err:
            LOGGER.error('OS Error while writing record for: {}'.format(stream_name))
            LOGGER.error('Stream: {}, record: {}'.format(stream_name, record))
            raise err
        except TypeError as err:
            LOGGER.error('Type Error while writing record for: {}'.format(stream_name))
            LOGGER.error('Stream: {}, record: {}'.format(stream_name, record))
            raise err

    def get_bookmark(self, state, stream, default):
        """ 
        Return bookmark value present in state or return a default value if no bookmark
        present in the state for provided stream
        """
        if (state is None) or ('bookmarks' not in state):
            return default
        return (
            state
            .get('bookmarks', {})
            .get(stream, default)
        )


    def write_bookmark(self, state, stream, value):
        """ Write bookmark in state. """
        if 'bookmarks' not in state:
            state['bookmarks'] = {}
        state['bookmarks'][stream] = value
        LOGGER.info('Write state for stream: {}, value: {}'.format(stream, value))
        singer.write_state(state)

    def transform_datetime(self, this_dttm):
        """
        Transform the datetime to standard datetime format "%Y-%m%dT%H:%M:%S.000000Z"
        """
        with Transformer() as transformer:
            new_dttm = transformer._transform_datetime(this_dttm)
        return new_dttm

    def process_records(self,
                        catalog, #pylint: disable=too-many-branches
                        stream_name,
                        records,
                        time_extracted,
                        bookmark_field=None,
                        max_bookmark_value=None,
                        last_datetime=None,
                        parent=None,
                        parent_id=None):
        """
        This function perform following operation,
        • Transform all the records
        • Update bookmark value to replication key value of record if it is greater than last bookmark value
        • Write only those records of which replication key value is after bookmark value of the last sync for incremental stream.
        • Write all records for FULL_TABLE stream
        • Return updated maximum bookmark value and total count of records
        """
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
                            transformed_record[bookmark_field] > self.transform_datetime(max_bookmark_value):
                            max_bookmark_value = transformed_record[bookmark_field]

                    # If bookmark_field is not none that means stream is incremental.
                    # So, in that case, the tap writes only those records of which the replication key value is greater than last saved bookmark key value
                    # For, FULL_TABLE stream bookmark_field is none. So, in the `else` part it writes all records for the FULL_TABLE stream
                    if bookmark_field and (bookmark_field in transformed_record):
                        last_dttm = self.transform_datetime(last_datetime)
                        bookmark_dttm = self.transform_datetime(transformed_record[bookmark_field])
                        # Keep only records whose bookmark is after the last_datetime
                        if bookmark_dttm:
                            if bookmark_dttm > last_dttm:
                                self.write_record(stream_name, transformed_record, \
                                    time_extracted=time_extracted)
                                counter.increment()
                    else:
                        self.write_record(stream_name, transformed_record, time_extracted=time_extracted)
                        counter.increment()

            # return maximum bookmark value and total no of records
            return max_bookmark_value, counter.value


    # Sync a specific parent or child endpoint.
    def sync(
            self,
            client,
            catalog,
            state,
            start_date,
            path,
            selected_streams=None,
            parent=None,
            parent_id=None):

        static_params = self.params
        bookmark_query_field = self.bookmark_query_field
        bookmark_field = next(iter(self.replication_keys or []), None)
        # Get the latest bookmark for the stream and set the last_integer/datetime
        last_datetime = None
        max_bookmark_value = None

        last_datetime = self.get_bookmark(state, self.stream_name, start_date)
        max_bookmark_value = last_datetime
        LOGGER.info('stream: {}, bookmark_field: {}, last_datetime: {}'.format(
            self.stream_name, bookmark_field, last_datetime))
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
                self.stream_name,
                self.client.base_url,
                path,
                '?{}'.format(querystring) if params else ''))

            # API request data
            endpoint_total, total_records, record_count, page, offset, max_bookmark_value = self.get_and_transform_records(
                                querystring, path, max_bookmark_value, state, catalog, start_date, last_datetime, endpoint_total, 
                                  limit, total_records, record_count, page, offset, parent, parent_id, selected_streams)

        # Update the state with the max_bookmark_value for the endpoint
        # ActiveCampaign API does not allow page/batch sorting; bookmark written for endpoint
        if bookmark_field:
            self.write_bookmark(state, self.stream_name, max_bookmark_value)

        # Return total_records (for all pages and date windows)
        return endpoint_total

    def transform_data(self, data):
        """
        Transform data with transform_json from transform.py
        """
        data_key = self.data_key
        
        # The data_key identifies the array/list of records below the <root> element
        transformed_data = [] # initialize the record list
        data_list = []
        data_dict = {}
        if data_key in data:
            if isinstance(data[data_key], list):
                transformed_data = transform_json(data, self.stream_name, data_key)
            elif isinstance(data[data_key], dict):
                data_list.append(data[data_key])
                data_dict[data_key] = data_list
                transformed_data = transform_json(data_dict, self.stream_name, data_key)
        else: # data_key not in data
            if isinstance(data, list):
                data_list = data
                data_dict[data_key] = data_list
                transformed_data = transform_json(data_dict, self.stream_name, data_key)
            elif isinstance(data, dict):
                data_list.append(data)
                data_dict[data_key] = data_list
                transformed_data = transform_json(data_dict, self.stream_name, data_key)
        
        return transformed_data

    def sync_child_stream(self, children, transformed_data, catalog, state, start_date, selected_streams):
        """
        sync the child stream. Loop through all children and if it is selected then collect data based on parent_id.
        """
        id_fields = self.key_properties
        
        for child_stream_name in children:
            if child_stream_name in selected_streams:
                LOGGER.info('START Syncing: {}'.format(child_stream_name))
                child_stream_obj = STREAMS[child_stream_name](self.client)
                child_stream_obj.write_schema(catalog, child_stream_name)
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
                            .format(child_stream_name, self.stream_name, parent_id))
                    child_path = child_stream_obj.path.format(str(parent_id))

                    child_total_records = child_stream_obj.sync(
                        client=self.client,
                        catalog=catalog,
                        state=state,
                        start_date=start_date,
                        path=child_path,
                        selected_streams=selected_streams,
                        parent=child_stream_obj.parent,
                        parent_id=parent_id)
                    LOGGER.info(
                        'FINISHED Sync for Stream: {}, parent_id: {}, total_records: {}'\
                            .format(child_stream_name, parent_id, child_total_records))
                    # End transformed data record loop
                # End if child in selected streams
            # End child streams for parent
        # End if children

    def get_and_transform_records(self, querystring, path, max_bookmark_value, state, catalog, start_date, last_datetime, endpoint_total, 
                                  limit, total_records, record_count, page, offset, parent, parent_id, selected_streams):
        
        """
        Get the records using the client get request and transform it using transform_records
        """
        
        bookmark_field = next(iter(self.replication_keys or []), None)
        created_timestamp_field = self.created_timestamp
        id_fields = self.key_properties

        # API request data
        data = {}
        data = self.client.get(
            path=path,
            params=querystring,
            endpoint=self.stream_name)
        
        # time_extracted: datetime when the data was extracted from the API
        time_extracted = utils.now()
        
        if not data or data is None or data == {}:
            LOGGER.info('No data for URL {}{}{}'.format(self.client.base_url, path, querystring)) # No data results
        else: # has data
            transformed_data = self.transform_data(data)
            
            if not transformed_data or transformed_data is None:
                LOGGER.info('No transformed data for data = {}'.format(data)) # No data results

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
                            self.stream_name, key, record))
                        raise RuntimeError
                i = i + 1
        
            # Process records and get the max_bookmark_value and record_count for the set of records
            max_bookmark_value, record_count = self.process_records(
                catalog=catalog,
                stream_name=self.stream_name,
                records=transformed_data,
                time_extracted=time_extracted,
                bookmark_field=bookmark_field,
                max_bookmark_value=max_bookmark_value,
                last_datetime=last_datetime,
                parent=parent,
                parent_id=parent_id)
            LOGGER.info('Stream {}, batch processed {} records'.format(
                self.stream_name, record_count))
            endpoint_total = endpoint_total + record_count

            # Loop thru parent batch records for each children objects (if should stream)
            children = self.children

            if children:
                # sync child stream
                self.sync_child_stream(children, transformed_data, catalog, state, start_date, selected_streams)

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
                self.stream_name,
                page,
                offset,
                to_rec,
                total_records))
            # Pagination: increment the offset by the limit (batch-size) and page
            offset = offset + limit
            page = page + 1
            # End page/batch - while next URL loop

        return endpoint_total, total_records, record_count, page, offset, max_bookmark_value

class Accounts(ActiveCampaign):
    """
    Get data for accounts. 
    Reference : https://developers.activecampaign.com/reference#list-all-accounts
    """
    stream_name = 'accounts'
    replication_keys = ['updated_timestamp']
    path = 'accounts'
    data_key = 'accounts'
    created_timestamp = 'created_timestamp'

class AccountContact(ActiveCampaign):
    """
    Get data for account contact. 
    Reference : https://developers.activecampaign.com/reference#list-all-associations-1
    """
    stream_name = 'account_contacts'
    replication_keys = ['updated_timestamp']
    path = 'accountContacts'
    data_key = 'accountContacts'
    created_timestamp = 'created_timestamp'

class AccountCustomFields(ActiveCampaign):
    """
    Get data for account custom fields. 
    Reference : https://developers.activecampaign.com/reference#list-all-custom-fields
    """
    stream_name = 'account_custom_fields'
    replication_keys = ['updated_timestamp']
    path = 'accountCustomFieldMeta'
    data_key = 'accountCustomFieldMeta'
    created_timestamp = 'created_timestamp'

class AccountCustomFieldValues(ActiveCampaign):
    """
    Get data for account custom field values. 
    Reference : https://developers.activecampaign.com/reference#list-all-custom-field-values-2
    """
    stream_name = 'account_custom_field_values'
    replication_keys = ['updated_timestamp']
    path = 'accountCustomFieldData'
    data_key = 'accountCustomFieldData'
    created_timestamp = 'created_timestamp'

class Addresses(ActiveCampaign):
    """
    Get data for addresses. 
    Reference : https://developers.activecampaign.com/reference#list-all-addresses
    """
    stream_name = 'addresses'
    replication_method = 'FULL_TABLE'
    path = 'addresses'
    data_key = 'addresses'
    links = ['addressGroup', 'addressList']

class Automations(ActiveCampaign):
    """
    Get data for automations. 
    Reference : https://developers.activecampaign.com/reference#list-all-automations
    """
    stream_name = 'automations'
    replication_keys = ['mdate']
    path = 'automations'
    data_key = 'automations'
    created_timestamp = 'cdate'
    links = ['contactGoals', 'blocks']

class Brandings(ActiveCampaign):
    """
    Get data for brandings. 
    Reference : https://developers.activecampaign.com/reference#brandings
    """
    stream_name = 'brandings'
    replication_method = 'FULL_TABLE'
    path = 'brandings'
    data_key = 'brandings'

class Calendars(ActiveCampaign):
    """
    Get data for calendars. 
    Reference : https://developers.activecampaign.com/reference#list-all-calendar-feeds
    """
    stream_name = 'calendars'
    replication_keys = ['mdate']
    path = 'calendars'
    data_key = 'calendars'
    created_timestamp = 'cdate'
    links = ['calendarRels', 'calendarUsers']

class Campaigns(ActiveCampaign):
    """
    Get data for campaigns. 
    Reference : https://developers.activecampaign.com/reference#list-all-campaigns
    """
    stream_name = 'campaigns'
    replication_keys = ['updated_timestamp']
    path = 'campaigns'
    data_key = 'campaigns'
    created_timestamp = 'created_timestamp'

class CampaignLinks(ActiveCampaign):
    """
    Get data for campaign_links. 
    Reference : https://developers.activecampaign.com/reference#retrieve-links-associated-campaign
    """
    stream_name = 'campaign_links'
    replication_keys = ['updated_timestamp']
    path = 'links'
    data_key = 'links'
    created_timestamp = 'created_timestamp'

class Contacts(ActiveCampaign):
    """
    Get data for contacts. 
    Reference : https://developers.activecampaign.com/reference#list-all-contacts
    """
    stream_name = 'contacts'
    replication_keys = ['updated_timestamp']
    path = 'contacts'
    data_key = 'contacts'
    created_timestamp = 'created_timestamp'
    bookmark_query_field = 'filters[updated_after]'
    links = ['contactGoals', 'contactLogs', 'geoIps', 'trackingLogs']

class ContactAutomations(ActiveCampaign):
    """
    Get data for contactAutomations. 
    Reference : https://developers.activecampaign.com/reference#list-all-contact-automations
    """
    stream_name = 'contact_automations'
    replication_keys = ['lastdate']
    path = 'contactAutomations'
    data_key = 'contactAutomations'
    created_timestamp = 'adddate'

class ContactCustomFields(ActiveCampaign):
    """
    Get data for contact_custom_fields. 
    Reference : https://developers.activecampaign.com/reference#retrieve-fields-1
    """
    stream_name = 'contact_custom_fields'
    replication_method = 'FULL_TABLE'
    path = 'fields'
    data_key = 'fields'

class ContactCustomFieldOptions(ActiveCampaign):
    """
    Get data for contact_custom_field_options. 
    Reference : https://developers.activecampaign.com/reference#retrieve-fields-1
    """
    stream_name = 'contact_custom_field_options'
    replication_method = 'FULL_TABLE'
    path = 'fields'
    data_key = 'fieldOptions'

class ContactCustomFieldRels(ActiveCampaign):
    """
    Get data for contact_custom_field_rels. 
    Reference : https://developers.activecampaign.com/reference#retrieve-fields-1
    """
    stream_name = 'contact_custom_field_rels'
    replication_method = 'FULL_TABLE'
    path = 'fields'
    data_key = 'fieldRels'

class ContactCustomFieldValues(ActiveCampaign):
    """
    Get data for contact_custom_field_values. 
    Reference : https://developers.activecampaign.com/reference#list-all-custom-field-values-1
    """
    stream_name = 'contact_custom_field_values'
    replication_keys = ['udate']
    path = 'fieldValues'
    data_key = 'fieldValues'
    created_timestamp = 'cdate'

class ContactDeals(ActiveCampaign):
    """
    Get data for contact_deals. 
    Reference : https://developers.activecampaign.com/reference#list-all-secondary-contacts
    """
    stream_name = 'contact_deals'
    replication_keys = ['updated_timestamp']
    path = 'contactDeals'
    data_key = 'contactDeals'
    created_timestamp = 'created_timestamp'

class DealStages(ActiveCampaign):
    """
    Get data for deal_stages. 
    Reference : https://developers.activecampaign.com/reference#list-all-deal-stages
    """
    stream_name = 'deal_stages'
    replication_keys = ['udate']
    path = 'dealStages'
    data_key = 'dealStages'
    created_timestamp = 'cdate'
    
class DealGroups(ActiveCampaign):
    """
    Get data for deal_groups. 
    Reference : https://developers.activecampaign.com/reference#list-all-pipelines
    Also known as: pipelines
    """
    stream_name = 'deal_groups'
    replication_keys = ['udate']
    path = 'dealGroups'
    data_key = 'dealGroups'
    created_timestamp = 'cdate'
    links = ['dealGroupGroups']

class DealCustomFields(ActiveCampaign):
    """
    Get data for deal_custom_fields. 
    Reference : https://developers.activecampaign.com/reference#retrieve-all-dealcustomfielddata-resources
    """
    stream_name = 'deal_custom_fields'
    replication_keys = ['updated_timestamp']
    path = 'dealCustomFieldMeta'
    data_key = 'dealCustomFieldMeta'
    created_timestamp = 'created_timestamp'

class DealCustomFieldValues(ActiveCampaign):
    """
    Get data for deal_custom_field_values. 
    Reference : https://developers.activecampaign.com/reference#list-all-custom-field-values
    """
    stream_name = 'deal_custom_field_values'
    replication_keys = ['updated_timestamp']
    path = 'dealCustomFieldData'
    data_key = 'dealCustomFieldData'
    created_timestamp = 'created_timestamp'
    
class Deals(ActiveCampaign):
    """
    Get data for deals. 
    Reference : https://developers.activecampaign.com/reference#list-all-deals
    """
    stream_name = 'deals'
    replication_keys = ['mdate']
    path = 'deals'
    data_key = 'deals'
    created_timestamp = 'cdate'

class EcommerceConnections(ActiveCampaign):
    """
    Get data for ecommerce_connections. 
    Reference : https://developers.activecampaign.com/reference#list-all-connections
    """
    stream_name = 'ecommerce_connections'
    
    replication_keys = ['udate']
    path = 'connections'
    data_key = 'connections'
    created_timestamp = 'cdate'
    
class EcommerceCustomers(ActiveCampaign):
    """
    Get data for ecommerce_customers. 
    Reference : https://developers.activecampaign.com/reference#list-all-customers
    """
    stream_name = 'ecommerce_customers'
    replication_keys = ['tstamp']
    path = 'ecomCustomers'
    data_key = 'ecomCustomers'

class EcommerceOrders(ActiveCampaign):
    """
    Get data for ecommerce orders. 
    Reference : https://developers.activecampaign.com/reference#list-all-customers
    """
    stream_name = 'ecommerce_orders'
    replication_keys = ['updated_date']
    path = 'ecomOrders'
    data_key = 'ecomOrders'
    created_timestamp = 'created_timestamp'
    links= ['orderDiscounts']
    children= ['ecommerce_order_products']

class EcommerceOrderProducts(ActiveCampaign):
    """
    Get data for ecommerce order products. 
    Reference : https://developers.activecampaign.com/reference#list-products-for-order
    """
    stream_name = 'ecommerce_order_products'
    replication_method = 'FULL_TABLE'
    path = 'ecomOrders/{}/orderProducts'
    data_key = 'ecomOrderProducts'
    parent = 'ecommerce_orders'

class Forms(ActiveCampaign):
    """
    Get data for forms. 
    Reference : https://developers.activecampaign.com/reference#forms-1
    """
    stream_name = 'forms'
    replication_keys = ['udate']
    path = 'forms'
    data_key = 'forms'
    created_timestamp = 'cdate'

class Groups(ActiveCampaign):
    """
    Get data for groups. 
    Reference : https://developers.activecampaign.com/reference#list-all-groups
    """
    stream_name = 'groups'
    replication_method = 'FULL_TABLE'
    path = 'groups'
    data_key = 'groups'
    
class Lists(ActiveCampaign):
    """
    Get data for lists. 
    Reference : https://developers.activecampaign.com/reference#retrieve-all-lists
    """
    stream_name = 'lists'
    replication_keys = ['updated_timestamp']
    path = 'lists'
    data_key = 'lists'
    created_timestamp = 'created_timestamp'
    links =  ['addressLists', 'contactGoalLists']

class Messages(ActiveCampaign):
    """
    Get data for messages. 
    Reference : https://developers.activecampaign.com/reference#list-all-messages
    """
    stream_name = 'messages'
    replication_keys = ['mdate']
    path = 'messages'
    data_key = 'messages'
    created_timestamp = 'cdate'

class SavedResponses(ActiveCampaign):
    """
    Get data for saved_responses. 
    Reference : https://developers.activecampaign.com/reference#list-all-saved-responses
    """
    stream_name = 'saved_responses'
    replication_keys = ['mdate']
    path = 'savedResponses'
    data_key = 'savedResponses'
    created_timestamp = 'cdate' 

class Scores(ActiveCampaign):
    """
    Get data for scores. 
    Reference : https://developers.activecampaign.com/reference#retrieve-a-score
    """
    stream_name = 'scores'
    replication_keys = ['mdate']
    path = 'scores'
    data_key = 'scores'
    created_timestamp = 'cdate' 

class Segments(ActiveCampaign):
    """
    Get data for segments. 
    Reference : https://developers.activecampaign.com/reference#list-all-segments
    """
    stream_name = 'segments'
    replication_method = 'FULL_TABLE'
    path = 'segments'
    data_key = 'segments'

class Tags(ActiveCampaign):
    """
    Get data for tags. 
    Reference : https://developers.activecampaign.com/reference#list-all-tags
    """
    stream_name = 'tags'
    replication_method = 'FULL_TABLE'
    path = 'tags'
    data_key = 'tags'

class TaskTypes(ActiveCampaign):
    """
    Get data for task_types. 
    Reference : https://developers.activecampaign.com/reference#list-all-deal-task-types
    """
    stream_name = 'task_types'
    replication_method = 'FULL_TABLE'
    path = 'dealTasktypes'
    data_key = 'dealTasktypes'

class Tasks(ActiveCampaign):
    """
    Get data for tasks. 
    Reference : https://developers.activecampaign.com/reference#list-all-tasks
    """
    stream_name = 'tasks'
    replication_keys = ['udate']
    path = 'dealTasks'
    data_key = 'dealTasks'
    created_timestamp = 'cdate'
    links= ['activities', 'taskNotifications']

class Templates(ActiveCampaign):
    """
    Get data for templates. 
    Reference : https://developers.activecampaign.com/reference#templates
    """
    stream_name = 'templates'
    replication_keys = ['mdate']
    path = 'templates'
    data_key = 'templates'

class Users(ActiveCampaign):
    """
    Get data for users. 
    Reference : https://developers.activecampaign.com/reference#users
    """
    stream_name = 'users'
    replication_method = 'FULL_TABLE'
    path = 'users'
    data_key = 'users'

class Webhooks(ActiveCampaign):
    """
    Get data for webhooks. 
    Reference : https://developers.activecampaign.com/reference#webhooks
    """
    stream_name = 'webhooks'
    replication_method = 'FULL_TABLE'
    path = 'webhooks'
    data_key = 'webhooks'

#Undocumented Endpoints

class Activities(ActiveCampaign):
    """
    Get data for activities. 
    """
    stream_name = 'activities'
    replication_keys = ['tstamp']
    path = 'activities'
    data_key = 'activities'

class AutomationBlocks(ActiveCampaign):
    """
    Get data for automation_blocks. 
    """
    stream_name = 'automation_blocks'
    replication_keys = ['mdate']
    path = 'automationBlocks'
    data_key = 'automationBlocks'
    created_timestamp = 'cdate'

class BounceLogs(ActiveCampaign):
    """
    Get data for bounce_logs. 
    """
    stream_name = 'bounce_logs'
    replication_keys = ['updated_timestamp']
    path = 'bounceLogs'
    data_key = 'bounceLogs'
    created_timestamp = 'created_timestamp'

class CampaignLists(ActiveCampaign):
    """
    Get data for campaign_lists. 
    """
    stream_name = 'campaign_lists'
    replication_method = 'FULL_TABLE'
    path = 'campaignLists'
    data_key = 'campaignLists'

class CampaignMessages(ActiveCampaign):
    """
    Get data for campaign_messages. 
    """
    stream_name = 'campaign_messages'
    replication_method = 'FULL_TABLE'
    path = 'campaignMessages'
    data_key = 'campaignMessages'
    
class Configs(ActiveCampaign):
    """
    Get data for configs. 
    """
    stream_name = 'configs'
    replication_keys = ['updated_timestamp']
    path = 'configs'
    data_key = 'configs'
    created_timestamp = 'created_timestamp'

class ContactData(ActiveCampaign):
    """
    Get data for contact_data. 
    """
    stream_name = 'contact_data'
    replication_keys = ['tstamp']
    path = 'contactData'
    data_key = 'contactData'

class ContactEmails(ActiveCampaign):
    """
    Get data for contact_emails. 
    """
    stream_name = 'contact_emails'
    replication_keys = ['sdate']
    path = 'contactEmails'
    data_key = 'contactEmails'


class ContactLists(ActiveCampaign):
    """
    Get data for contact_lists. 
    """
    stream_name = 'contact_lists'
    replication_keys = ['updated_timestamp']
    path = 'contactLists'
    data_key = 'contactLists'
    created_timestamp = 'created_timestamp'

class ContactTags(ActiveCampaign):
    """
    Get data for contact_tags. 
    """
    stream_name = 'contact_tags'
    replication_keys = ['updated_timestamp']
    path = 'contactTags'
    data_key = 'contactTags'
    created_timestamp = 'created_timestamp'

class ContactConversions(ActiveCampaign):
    """
    Get data for contact_conversions. 
    """
    stream_name = 'contact_conversions'
    replication_keys = ['cdate']
    path = 'contactConversions'
    data_key = 'contactConversions'

class Conversions(ActiveCampaign):
    """
    Get data for conversions. 
    """
    stream_name = 'conversions'
    replication_keys = ['udate']
    path = 'conversions'
    data_key = 'conversions'
    created_timestamp = 'cdate'
    links= ['contactConversions']
 
class ConversionTriggers(ActiveCampaign):
    """
    Get data for conversion_triggers. 
    """
    stream_name = 'conversion_triggers'
    replication_keys = ['udate']
    path = 'conversionTriggers'
    data_key = 'conversionTriggers'
    created_timestamp = 'cdate'

class DealActivities(ActiveCampaign):
    """
    Get data for deal_activities. 
    """
    stream_name = 'deal_activities'
    replication_keys = ['cdate']
    path = 'dealActivities'
    data_key = 'dealActivities'

class DealGroupUsers(ActiveCampaign):
    """
    Get data for deal_group_users. 
    """
    stream_name = 'deal_group_users'
    replication_method = 'FULL_TABLE'
    path = 'dealGroupUsers'
    data_key = 'dealGroupUsers'

class EcommerceOrderActivities(ActiveCampaign):
    """
    Get data for ecommerce_order_activities. 
    """
    stream_name = 'ecommerce_order_activities'
    replication_keys = ['updated_date']
    path = 'ecomOrderActivities'
    data_key = 'ecomOrderActivities'
    created_timestamp= 'created_date',

class EmailActivities(ActiveCampaign):
    """
    Get data for email_activities. 
    """
    stream_name = 'email_activities'
    replication_keys = ['tstamp']
    path = 'emailActivities'
    data_key = 'emailActivities'

class Goals(ActiveCampaign):
    """
    Get data for goals. 
    """
    stream_name = 'goals'
    replication_method = 'FULL_TABLE'
    path = 'goals'
    data_key = 'goals'

class SiteMessages(ActiveCampaign):
    """
    Get data for site_messages. 
    """
    stream_name = 'site_messages'
    replication_keys = ['ldate']
    path = 'siteMessages'
    data_key = 'siteMessages'

class Sms(ActiveCampaign):
    """
    Get data for sms. 
    """
    stream_name = 'sms'
    replication_keys = ['tstamp']
    path = 'sms'
    data_key = 'sms'

STREAMS = {
  'accounts': Accounts,
  'account_contacts': AccountContact,
  'account_custom_fields': AccountCustomFields,
  'account_custom_field_values': AccountCustomFieldValues,
  'addresses': Addresses,
  'automations': Automations,
  'brandings': Brandings,
  'calendars': Calendars,
  'campaigns': Campaigns,
  'campaign_links': CampaignLinks,
  'contacts': Contacts,
  'contact_automations': ContactAutomations,
  'contact_custom_fields': ContactCustomFields,
  'contact_custom_field_options': ContactCustomFieldOptions,
  'contact_custom_field_rels': ContactCustomFieldRels,
  'contact_custom_field_values': ContactCustomFieldValues,
  'contact_deals': ContactDeals,
  'deal_stages': DealStages,
  'deal_groups': DealGroups,
  'deal_custom_fields': DealCustomFields,
  'deal_custom_field_values': DealCustomFieldValues,
  'deals': Deals,
  'ecommerce_connections': EcommerceConnections,
  'ecommerce_customers': EcommerceCustomers,
  'ecommerce_orders': EcommerceOrders,
  'ecommerce_order_products': EcommerceOrderProducts,
  'forms': Forms,
  'groups': Groups,
  'lists': Lists,
  'messages': Messages,
  'saved_responses': SavedResponses,
  'scores': Scores,
  'segments': Segments,
  'tags': Tags,
  'task_types': TaskTypes,
  'tasks': Tasks,
  'templates': Templates,
  'users': Users,
  'webhooks': Webhooks,
  'activities': Activities,
  'automation_blocks': AutomationBlocks,
  'bounce_logs': BounceLogs,
  'campaign_lists': CampaignLists,
  'campaign_messages': CampaignMessages,
  'configs': Configs,
  'contact_data': ContactData,
  'contact_emails': ContactEmails,
  'contact_lists': ContactLists,
  'contact_tags': ContactTags,
  'contact_conversions': ContactConversions,
  'conversions': Conversions,
  'conversion_triggers': ConversionTriggers,
  'deal_activities': DealActivities,
  'deal_group_users': DealGroupUsers,
  'ecommerce_order_activities': EcommerceOrderActivities,
  'email_activities': EmailActivities,
  'goals': Goals,
  'site_messages': SiteMessages,
  'sms': Sms
}

SUB_STREAMS = {
    'ecommerce_orders': 'ecommerce_order_products'
}

def flatten_streams():
    flat_streams = {}
    # Loop through all streams
    for stream in STREAMS.values():
      stream = stream()
      flat_streams[stream.stream_name] = {
            'key_properties': stream.key_properties,
            'replication_method': stream.replication_method,
            'replication_keys': stream.replication_keys
        }

    return flat_streams
