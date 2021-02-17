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

STREAMS = {

  #Reference: https://developers.activecampaign.com/reference#list-all-accounts
    'accounts': {
      'path': 'accounts',
      'data_key': 'accounts',
      'key_properties': ['id'],
      'replication_method': 'INCREMENTAL',
      'replication_keys': ['updated_timestamp'],
      'created_timestamp': 'created_timestamp',
      'links': []
    },

  #Reference: https://developers.activecampaign.com/reference#list-all-associations-1
    'account_contacts': {
      'path': 'accountContacts',
      'data_key': 'accountContacts',
      'key_properties': ['id'],
      'replication_method': 'INCREMENTAL',
      'replication_keys': ['updated_timestamp'],
      'created_timestamp': 'created_timestamp',
      'links': []
    },

  #Reference: https://developers.activecampaign.com/reference#list-all-custom-fields
    'account_custom_fields': {
      'path': 'accountCustomFieldMeta',
      'data_key': 'accountCustomFieldMeta',
      'key_properties': ['id'],
      'replication_method': 'INCREMENTAL',
      'replication_keys': ['updated_timestamp'],
      'created_timestamp': 'created_timestamp',
      'links': []
    },

  #Reference: https://developers.activecampaign.com/reference#list-all-custom-field-values-2
    'account_custom_field_values': {
      'path': 'accountCustomFieldData',
      'data_key': 'accountCustomFieldData',
      'key_properties': ['id'],
      'replication_method': 'INCREMENTAL',
      'replication_keys': ['updated_timestamp'],
      'created_timestamp': 'created_timestamp',
      'links': []
    },

  #Reference: https://developers.activecampaign.com/reference#list-all-addresses
    'addresses': {
      'path': 'addresses',
      'data_key': 'addresses',
      'key_properties': ['id'],
      'replication_method': 'FULL_TABLE',
      'links': ['addressGroup', 'addressList']
    },

  #Reference: https://developers.activecampaign.com/reference#list-all-automations
    'automations': {
      'path': 'automations',
      'data_key': 'automations',
      'key_properties': ['id'],
      'replication_method': 'INCREMENTAL',
      'replication_keys': ['mdate'],
      'created_timestamp': 'cdate',
      'links': ['contactGoals', 'blocks']
    },

  #Reference: https://developers.activecampaign.com/reference#brandings
    'brandings': {
      'path': 'brandings',
      'data_key': 'brandings',
      'key_properties': ['id'],
      'replication_method': 'FULL_TABLE',
      'links': []
    },

  #Reference: https://developers.activecampaign.com/reference#list-all-calendar-feeds
    'calendars': {
      'path': 'calendars',
      'data_key': 'calendars',
      'key_properties': ['id'],
      'replication_method': 'INCREMENTAL',
      'replication_keys': ['mdate'],
      'created_timestamp': 'cdate',
      'links': ['calendarRels', 'calendarUsers']
    },

  #Reference: https://developers.activecampaign.com/reference#list-all-campaigns
    'campaigns': {
      'path': 'campaigns',
      'data_key': 'campaigns',
      'key_properties': ['id'],
      'replication_method': 'INCREMENTAL',
      'replication_keys': ['updated_timestamp'],
      'created_timestamp': 'created_timestamp',
      'links': []
    },

  #Reference: https://developers.activecampaign.com/reference#retrieve-links-associated-campaign
    'campaign_links': {
      'path': 'links',
      'data_key': 'links',
      'key_properties': ['id'],
      'replication_method': 'INCREMENTAL',
      'replication_keys': ['updated_timestamp'],
      'created_timestamp': 'created_timestamp',
      'links': []
    },

  #Reference: https://developers.activecampaign.com/reference#list-all-contacts
    'contacts': {
      'path': 'contacts',
      'data_key': 'contacts',
      'key_properties': ['id'],
      'replication_method': 'INCREMENTAL',
      'replication_keys': ['updated_timestamp'],
      'created_timestamp': 'created_timestamp',
      'bookmark_query_field': 'filters[updated_after]',
      'links': [
        'contactGoals', 'contactLogs', 'geoIps', 'trackingLogs'
      ]
    },

  #Reference: https://developers.activecampaign.com/reference#list-all-contact-automations
    'contact_automations': {
      'path': 'contactAutomations',
      'data_key': 'contactAutomations',
      'key_properties': ['id'],
      'replication_method': 'INCREMENTAL',
      'replication_keys': ['lastdate'],
      'created_timestamp': 'adddate',
      'links': []
    },

  #Reference: https://developers.activecampaign.com/reference#retrieve-fields-1
    'contact_custom_fields': {
      'path': 'fields',
      'data_key': 'fields',
      'key_properties': ['id'],
      'replication_method': 'FULL_TABLE',
      'links': []
    },

  #Reference: https://developers.activecampaign.com/reference#retrieve-fields-1
    'contact_custom_field_options': {
      'path': 'fields',
      'data_key': 'fieldOptions',
      'key_properties': ['id'],
      'replication_method': 'FULL_TABLE',
      'links': []
    },

  #Reference: https://developers.activecampaign.com/reference#retrieve-fields-1
    'contact_custom_field_rels': {
      'path': 'fields',
      'data_key': 'fieldRels',
      'key_properties': ['id'],
      'replication_method': 'FULL_TABLE',
      'links': []
    },

  #Reference: https://developers.activecampaign.com/reference#list-all-custom-field-values-1
    'contact_custom_field_values': {
      'path': 'fieldValues',
      'data_key': 'fieldValues',
      'key_properties': ['id'],
      'replication_method': 'INCREMENTAL',
      'replication_keys': ['udate'],
      'created_timestamp': 'cdate',
      'links': []
    },

  #Reference: https://developers.activecampaign.com/reference#list-all-secondary-contacts
    'contact_deals': {
      'path': 'contactDeals',
      'data_key': 'contactDeals',
      'key_properties': ['id'],
      'replication_method': 'INCREMENTAL',
      'replication_keys': ['updated_timestamp'],
      'created_timestamp': 'created_timestamp',
      'links': []
    },

  #Reference: https://developers.activecampaign.com/reference#list-all-deal-stages
    'deal_stages': {
      'path': 'dealStages',
      'data_key': 'dealStages',
      'key_properties': ['id'],
      'replication_method': 'INCREMENTAL',
      'replication_keys': ['udate'],
      'created_timestamp': 'cdate',
      'links': []
    },

  #Reference: https://developers.activecampaign.com/reference#list-all-pipelines
    #Also known as: pipelines
    'deal_groups': {
      'path': 'dealGroups',
      'data_key': 'dealGroups',
      'key_properties': ['id'],
      'replication_method': 'INCREMENTAL',
      'replication_keys': ['udate'],
      'created_timestamp': 'cdate',
      'links': ['dealGroupGroups']
    },

  #Reference: https://developers.activecampaign.com/reference#retrieve-all-dealcustomfielddata-resources
    'deal_custom_fields': {
      'path': 'dealCustomFieldMeta',
      'data_key': 'dealCustomFieldMeta',
      'key_properties': ['id'],
      'replication_method': 'INCREMENTAL',
      'replication_keys': ['updated_timestamp'],
      'created_timestamp': 'created_timestamp',
      'links': []
    },

  #Reference: https://developers.activecampaign.com/reference#list-all-custom-field-values
    'deal_custom_field_values': {
      'path': 'dealCustomFieldData',
      'data_key': 'dealCustomFieldData',
      'key_properties': ['id'],
      'replication_method': 'INCREMENTAL',
      'replication_keys': ['updated_timestamp'],
      'created_timestamp': 'created_timestamp',
      'links': []
    },

  #Reference: https://developers.activecampaign.com/reference#list-all-deals
    'deals': {
      'path': 'deals',
      'data_key': 'deals',
      'key_properties': ['id'],
      'replication_method': 'INCREMENTAL',
      'replication_keys': ['mdate'],
      'created_timestamp': 'cdate',
      'links': []
    },

  #Reference: https://developers.activecampaign.com/reference#list-all-connections
    'ecommerce_connections': {
      'path': 'connections',
      'data_key': 'connections',
      'key_properties': ['id'],
      'replication_method': 'INCREMENTAL',
      'replication_keys': ['udate'],
      'created_timestamp': 'cdate',
      'links': []
    },

  #Reference: https://developers.activecampaign.com/reference#list-all-customers
    'ecommerce_customers': {
      'path': 'ecomCustomers',
      'data_key': 'ecomCustomers',
      'key_properties': ['id'],
      'replication_method': 'INCREMENTAL',
      'replication_keys': ['tstamp'],
      'links': []
    },

  #Reference: https://developers.activecampaign.com/reference#list-all-customers
    'ecommerce_orders': {
      'path': 'ecomOrders',
      'data_key': 'ecomOrders',
      'key_properties': ['id'],
      'replication_method': 'INCREMENTAL',
      'replication_keys': ['updated_date'],
      'created_timestamp': 'created_date',
      'params': {},
      'links': ['orderDiscounts'],
      'children': {
        #Reference: https://developers.activecampaign.com/reference#list-products-for-order
          'ecommerce_order_products': {
            'path': 'ecomOrders/{}/orderProducts',
            'data_key': 'ecomOrderProducts',
            'key_properties': ['id'],
            'replication_method': 'FULL_TABLE',
            'links': []
          }
      }
    },

  #Reference: https://developers.activecampaign.com/reference#forms-1
    'forms': {
      'path': 'forms',
      'data_key': 'forms',
      'key_properties': ['id'],
      'replication_method': 'INCREMENTAL',
      'replication_keys': ['udate'],
      'created_timestamp': 'cdate',
      'links': []
    },

  #Reference: https://developers.activecampaign.com/reference#list-all-groups
    'groups': {
      'path': 'groups',
      'data_key': 'groups',
      'key_properties': ['id'],
      'replication_method': 'FULL_TABLE',
      'links': []
    },

  #Reference: https://developers.activecampaign.com/reference#retrieve-all-lists
    'lists': {
      'path': 'lists',
      'data_key': 'lists',
      'key_properties': ['id'],
      'replication_method': 'INCREMENTAL',
      'replication_keys': ['updated_timestamp'],
      'created_timestamp': 'created_timestamp',
      'links': ['addressLists', 'contactGoalLists']
    },

  #Reference: https://developers.activecampaign.com/reference#list-all-messages
    'messages': {
      'path': 'messages',
      'data_key': 'messages',
      'key_properties': ['id'],
      'replication_method': 'INCREMENTAL',
      'replication_keys': ['mdate'],
      'created_timestamp': 'cdate',
      'links': []
    },

  #Reference: https://developers.activecampaign.com/reference#list-all-saved-responses
    'saved_responses': {
      'path': 'savedResponses',
      'data_key': 'savedResponses',
      'key_properties': ['id'],
      'replication_method': 'INCREMENTAL',
      'replication_keys': ['mdate'],
      'created_timestamp': 'cdate',
      'links': []
    },

  #Reference: https://developers.activecampaign.com/reference#retrieve-a-score
    'scores': {
      'path': 'scores',
      'data_key': 'scores',
      'key_properties': ['id'],
      'replication_method': 'INCREMENTAL',
      'replication_keys': ['mdate'],
      'created_timestamp': 'cdate',
      'links': []
    },

  #Reference: https://developers.activecampaign.com/reference#list-all-segments
    'segments': {
      'path': 'segments',
      'data_key': 'segments',
      'key_properties': ['id'],
      'replication_method': 'FULL_TABLE',
      'links': []
    },

  #Reference: https://developers.activecampaign.com/reference#retrieve-all-tags
    'tags': {
      'path': 'tags',
      'data_key': 'tags',
      'key_properties': ['id'],
      'replication_method': 'FULL_TABLE',
      'links': ['contactGoalTags']
    },

  #Reference: https://developers.activecampaign.com/reference#list-all-deal-task-types
    'task_types': {
      'path': 'dealTasktypes',
      'data_key': 'dealTasktypes',
      'key_properties': ['id'],
      'replication_method': 'FULL_TABLE',
      'links': []
    },

  #Reference: https://developers.activecampaign.com/reference#list-all-tasks
    'tasks': {
      'path': 'dealTasks',
      'data_key': 'dealTasks',
      'key_properties': ['id'],
      'replication_method': 'INCREMENTAL',
      'replication_keys': ['udate'],
      'created_timestamp': 'cdate',
      'links': ['activities', 'taskNotifications']
    },

  #Reference: https://developers.activecampaign.com/reference#templates
    'templates': {
      'path': 'templates',
      'data_key': 'templates',
      'key_properties': ['id'],
      'replication_method': 'INCREMENTAL',
      'replication_keys': ['mdate'],
      'created_timestamp': None,
      'links': []
    },

  #Reference: https://developers.activecampaign.com/reference#list-all-users
    'users': {
      'path': 'users',
      'data_key': 'users',
      'key_properties': ['id'],
      'replication_method': 'FULL_TABLE',
      'links': []
    },

  #Reference: https://developers.activecampaign.com/reference#get-a-list-of-webhooks
    'webhooks': {
      'path': 'webhooks',
      'data_key': 'webhooks',
      'key_properties': ['id'],
      'replication_method': 'FULL_TABLE',
      'links': []
    },

  #Undocumented Endpoints
    'activities': {
      'path': 'activities',
      'data_key': 'activities',
      'key_properties': ['id'],
      'replication_method': 'INCREMENTAL',
      'replication_keys': ['tstamp'],
      'created_timestamp': None,
      'links': []
    },

    'automation_blocks': {
      'path': 'automationBlocks',
      'data_key': 'automationBlocks',
      'key_properties': ['id'],
      'replication_method': 'INCREMENTAL',
      'replication_keys': ['mdate'],
      'created_timestamp': 'cdate',
      'links': []
    },

    'bounce_logs': {
      'path': 'bounceLogs',
      'data_key': 'bounceLogs',
      'key_properties': ['id'],
      'replication_method': 'INCREMENTAL',
      'replication_keys': ['updated_timestamp'],
      'created_timestamp': 'created_timestamp',
      'links': []
    },

    'campaign_lists': {
      'path': 'campaignLists',
      'data_key': 'campaignLists',
      'key_properties': ['id'],
      'replication_method': 'FULL_TABLE',
      'links': []
    },

    'campaign_messages': {
      'path': 'campaignMessages',
      'data_key': 'campaignMessages',
      'key_properties': ['id'],
      'replication_method': 'FULL_TABLE',
      'links': []
    },

    'configs': {
      'path': 'configs',
      'data_key': 'configs',
      'key_properties': ['id'],
      'replication_method': 'INCREMENTAL',
      'replication_keys': ['updated_timestamp'],
      'created_timestamp': 'created_timestamp',
      'links': []
    },

    'contact_data': {
      'path': 'contactData',
      'data_key': 'contactData',
      'key_properties': ['id'],
      'replication_method': 'INCREMENTAL',
      'replication_keys': ['tstamp'],
      'created_timestamp': None,
      'links': []
    },

    'contact_emails': {
      'path': 'contactEmails',
      'data_key': 'contactEmails',
      'key_properties': ['id'],
      'replication_method': 'INCREMENTAL',
      'replication_keys': ['sdate'],
      'created_timestamp': None,
      'links': []
    },

    'contact_lists': {
      'path': 'contactLists',
      'data_key': 'contactLists',
      'key_properties': ['id'],
      'replication_method': 'INCREMENTAL',
      'replication_keys': ['updated_timestamp'],
      'created_timestamp': 'created_timestamp',
      'links': []
    },

    'contact_tags': {
      'path': 'contactTags',
      'data_key': 'contactTags',
      'key_properties': ['id'],
      'replication_method': 'INCREMENTAL',
      'replication_keys': ['updated_timestamp'],
      'created_timestamp': 'created_timestamp',
      'links': []
    },

    'contact_conversions': {
      'path': 'contactConversions',
      'data_key': 'contactConversions',
      'key_properties': ['id'],
      'replication_method': 'INCREMENTAL',
      'replication_keys': ['cdate'],
      'created_timestamp': None,
      'links': []
    },

    'conversions': {
      'path': 'conversions',
      'data_key': 'conversions',
      'key_properties': ['id'],
      'replication_method': 'INCREMENTAL',
      'replication_keys': ['udate'],
      'created_timestamp': 'cdate',
      'links': []
    },

    'conversions': {
      'path': 'conversions',
      'data_key': 'conversions',
      'key_properties': ['id'],
      'replication_method': 'INCREMENTAL',
      'replication_keys': ['udate'],
      'created_timestamp': 'cdate',
      'links': ['contactConversions']
    },

    'conversion_triggers': {
      'path': 'conversionTriggers',
      'data_key': 'conversionTriggers',
      'key_properties': ['id'],
      'replication_method': 'INCREMENTAL',
      'replication_keys': ['udate'],
      'created_timestamp': 'cdate',
      'links': []
    },

    'deal_activities': {
      'path': 'dealActivities',
      'data_key': 'dealActivities',
      'key_properties': ['id'],
      'replication_method': 'INCREMENTAL',
      'replication_keys': ['cdate'],
      'created_timestamp': None,
      'links': []
    },

    'deal_group_users': {
      'path': 'dealGroupUsers',
      'data_key': 'dealGroupUsers',
      'key_properties': ['id'],
      'replication_method': 'FULL_TABLE',
      'links': []
    },

    'ecommerce_order_activities': {
      'path': 'ecomOrderActivities',
      'data_key': 'ecomOrderActivities',
      'key_properties': ['id'],
      'replication_method': 'INCREMENTAL',
      'replication_keys': ['updated_date'],
      'created_timestamp': 'created_date',
      'links': []
    },

    'email_activities': {
      'path': 'emailActivities',
      'data_key': 'emailActivities',
      'key_properties': ['id'],
      'replication_method': 'INCREMENTAL',
      'replication_keys': ['tstamp'],
      'created_timestamp': None,
      'links': []
    },

    'goals': {
      'path': 'goals',
      'data_key': 'goals',
      'key_properties': ['id'],
      'replication_method': 'FULL_TABLE',
      'links': ['contactGoals']
    },

    'site_messages': {
      'path': 'siteMessages',
      'data_key': 'siteMessages',
      'key_properties': ['id'],
      'replication_method': 'INCREMENTAL',
      'replication_keys': ['ldate'],
      'created_timestamp': None,
      'links': []
    },

    'sms': {
      'path': 'sms',
      'data_key': 'sms',
      'key_properties': ['id'],
      'replication_method': 'INCREMENTAL',
      'replication_keys': ['tstamp'],
      'created_timestamp': None,
      'links': []
    },

}


def flatten_streams():
    flat_streams = {}
    # Loop through parents
    for stream_name, endpoint_config in STREAMS.items():
        flat_streams[stream_name] = {
            'key_properties': endpoint_config.get('key_properties'),
            'replication_method': endpoint_config.get('replication_method'),
            'replication_keys': endpoint_config.get('replication_keys')
        }
        # Loop through children
        children = endpoint_config.get('children')
        if children:
            for child_stream_name, child_enpoint_config in children.items():
                flat_streams[child_stream_name] = {
                    'key_properties': child_enpoint_config.get('key_properties'),
                    'replication_method': child_enpoint_config.get('replication_method'),
                    'replication_keys': child_enpoint_config.get('replication_keys')
                }
    return flat_streams
