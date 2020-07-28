# tap-activecampaign

This is a [Singer](https://singer.io) tap that produces JSON-formatted data
following the [Singer
spec](https://github.com/singer-io/getting-started/blob/master/SPEC.md).

This tap:

- Pulls raw data from the [ActiveCampaign v3 API](https://developers.activecampaign.com/reference#overview)
- Extracts the following resources:
  - [accounts](https: //developers.activecampaign.com/reference#list-all-accounts)
  - [account_contacts](https://developers.activecampaign.com/reference#list-all-associations-1)
  - [account_custom_fields](https://developers.activecampaign.com/reference#list-all-custom-fields)
  - [account_custom_field_values](https://developers.activecampaign.com/reference#list-all-custom-field-values-2)
  - [addresses](https://developers.activecampaign.com/reference#list-all-addresses)
  - [automations](https://developers.activecampaign.com/reference#list-all-automations)
  - [brandings](https://developers.activecampaign.com/reference#brandings)
  - [calendars](https://developers.activecampaign.com/reference#list-all-calendar-feeds)
  - [campaigns](https://developers.activecampaign.com/reference#list-all-campaigns)
  - [campaign_links](https://developers.activecampaign.com/reference#retrieve-links-associated-campaign)
  - [contacts](https://developers.activecampaign.com/reference#list-all-contacts)
  - [contact_automations](https://developers.activecampaign.com/reference#list-all-contact-automations)
  - [contact_custom_fields](hhttps://developers.activecampaign.com/reference#retrieve-fields-1)
  - [contact_custom_field_options](https://developers.activecampaign.com/reference#retrieve-fields-1)
  - [contact_custom_field_rels](https://developers.activecampaign.com/reference#retrieve-fields-1)
  - [contact_custom_field_values](https://developers.activecampaign.com/reference#list-all-custom-field-values-1)
  - [contact_deals](ttps://developers.activecampaign.com/reference#list-all-secondary-contacts)
  - [deals](https://developers.activecampaign.com/reference#list-all-deals)
  - [deal_stages](https://developers.activecampaign.com/reference#list-all-deal-stages)
  - [deal_groups](https://developers.activecampaign.com/reference#list-all-pipelines)
  - [deal_custom_fields](https://developers.activecampaign.com/reference#retrieve-all-dealcustomfielddata-resources)
  - [deal_custom_field_values](https://developers.activecampaign.com/reference#list-all-custom-field-values)




- Outputs the schema for each resource
- Incrementally pulls data based on the input state

## Streams
[accounts](https: //developers.activecampaign.com/reference#list-all-accounts)
- Endpoint: https://{subdomain}.api-us1.com/accounts
- Data key: accounts
- Primary keys: id
- Replication strategy: Incremental (query all, filter results)
  - Bookmark: updated_timestamp
- Transformations: camelCase to snake_case, remove links node

[account_contacts](https://developers.activecampaign.com/reference#list-all-associations-1)
- Endpoint: https://{subdomain}.api-us1.com/accountContacts
- Data key: accountContacts
- Primary keys: id
- Replication strategy: Incremental (query all, filter results)
  - Bookmark: updated_timestamp
- Transformations: camelCase to snake_case, remove links node

[account_custom_fields](https://developers.activecampaign.com/reference#list-all-custom-fields)
- Endpoint: https://{subdomain}.api-us1.com/accountCustomFieldMeta
- Data key: accountCustomFieldMeta
- Primary keys: id
- Replication strategy: Incremental (query all, filter results)
  - Bookmark: updated_timestamp
- Transformations: camelCase to snake_case, remove links node

[account_custom_field_values](https://developers.activecampaign.com/reference#list-all-custom-field-values-2)
- Endpoint: https://{subdomain}.api-us1.com/accountCustomFieldData
- Data key: accountCustomFieldData
- Primary keys: id
- Replication strategy: Incremental (query all, filter results)
  - Bookmark: updated_timestamp
- Transformations: camelCase to snake_case, remove links node

[addresses](https://developers.activecampaign.com/reference#list-all-addresses)
- Endpoint: https://{subdomain}.api-us1.com/addresses
- Data key: addresses
- Primary keys: id
- Replication strategy: Full Table
- Transformations: camelCase to snake_case, remove links node

[automations](https://developers.activecampaign.com/reference#list-all-automations)
- Endpoint: https://{subdomain}.api-us1.com/automations
- Primary keys: id
- Replication strategy: Incremental (query all, filter results)
  - Bookmark: mdate
- Transformations: camelCase to snake_case, remove links node

[brandings](https://developers.activecampaign.com/reference#brandings)
- Endpoint: https://{subdomain}.api-us1.com/brandings
- Data key: brandings
- Primary keys: id
- Replication strategy: Full Table
- Transformations: camelCase to snake_case, remove links node

[calendars](https://developers.activecampaign.com/reference#list-all-calendar-feeds)
- Endpoint: https://{subdomain}.api-us1.com/calendars
- Data key: calendars
- Primary keys: id
- Replication strategy: Incremental (query all, filter results)
  - Bookmark: mdate
- Transformations: camelCase to snake_case, remove links node

[campaigns](https://developers.activecampaign.com/reference#list-all-campaigns)
- Endpoint: https://{subdomain}.api-us1.com/campaigns
- Data key: campaigns
- Primary keys: id
- Replication strategy: Incremental (query all, filter results)
  - Bookmark: updated_timestamp
- Transformations: camelCase to snake_case, remove links node

[campaign_links](https://developers.activecampaign.com/reference#retrieve-links-associated-campaign)
- Endpoint: https://{subdomain}.api-us1.com/links
- Data key: links
- Primary keys: id
- Replication strategy: Incremental (query all, filter results)
  - Bookmark: updated_timestamp
- Transformations: camelCase to snake_case, remove links node

[contacts](https://developers.activecampaign.com/reference#list-all-contacts)
- Endpoint: https://{subdomain}.api-us1.com/contacts
- Data key: contacts
- Primary keys: id
- Replication strategy: Incremental (query all, filter results)
  - Bookmark: updated_timestamp
  - Bookmark query fields: updated_after
- Transformations: camelCase to snake_case, remove links node

[contact_automations](https://developers.activecampaign.com/reference#list-all-contact-automations)
- Endpoint: https://{subdomain}.api-us1.com/contactAutomations
- Data key: contactAutomations
- Primary keys: id
- Replication strategy: Incremental (query all, filter results)
  - Bookmark: lastdate
- Transformations: camelCase to snake_case, remove links node

[contact_custom_fields](hhttps://developers.activecampaign.com/reference#retrieve-fields-1)
- Endpoint: https://{subdomain}.api-us1.com/fields
- Data key: fields
- Primary keys: id
- Replication strategy: Full Table
- Transformations: camelCase to snake_case, remove links node

[contact_custom_field_options](https://developers.activecampaign.com/reference#retrieve-fields-1)
- Endpoint: https://{subdomain}.api-us1.com/fields
- Data key: fieldOptions
- Primary keys: id
- Replication strategy: Full Table
- Transformations: camelCase to snake_case, remove links node

[contact_custom_field_rels](https://developers.activecampaign.com/reference#retrieve-fields-1)
- Endpoint: https://{subdomain}.api-us1.com/fields
- Data key: fieldRels
- Primary keys: id
- Replication strategy: Full Table
- Transformations: camelCase to snake_case, remove links node

[contact_custom_field_values](https://developers.activecampaign.com/reference#list-all-custom-field-values-1)
- Endpoint: https://{subdomain}.api-us1.com/fieldValues
- Data key: fieldValues
- Primary keys: id
- Replication strategy: Incremental (query all, filter results)
  - Bookmark: udate
- Transformations: camelCase to snake_case, remove links node

[contact_deals](ttps://developers.activecampaign.com/reference#list-all-secondary-contacts)
- Endpoint: https://{subdomain}.api-us1.com/contactDeals
- Data key: contactDeals
- Primary keys: id
- Replication strategy: Incremental (query all, filter results)
  - Bookmark: updated_timestamp
- Transformations: camelCase to snake_case, remove links node

[deal_stages](https://developers.activecampaign.com/reference#list-all-deal-stages)
- Endpoint: https://{subdomain}.api-us1.com/dealStages
- Data key: dealStages
- Primary keys: id
- Replication strategy: Incremental (query all, filter results)
  - Bookmark: udate
- Transformations: camelCase to snake_case, remove links node


[deal_groups](https://developers.activecampaign.com/reference#list-all-pipelines)
- Endpoint: https://{subdomain}.api-us1.com/dealGroups
- Data key: dealGroups
- Primary keys: id
- Replication strategy: Incremental (query all, filter results)
  - Bookmark: udate
- Transformations: camelCase to snake_case, remove links node

[deal_custom_fields](https://developers.activecampaign.com/reference#retrieve-all-dealcustomfielddata-resources)
- Endpoint: https://{subdomain}.api-us1.com/dealCustomFieldMeta
- Data key: dealCustomFieldMeta
- Primary keys: id
- Replication strategy: Incremental (query all, filter results)
  - Bookmark: updated_timestamp
- Transformations: camelCase to snake_case, remove links node

[deal_custom_field_values](https://developers.activecampaign.com/reference#list-all-custom-field-values)
- Endpoint: https://{subdomain}.api-us1.com/dealCustomFieldData
- Data key: dealCustomFieldData
- Primary keys: id
- Replication strategy: Incremental (query all, filter results)
  - Bookmark: updated_timestamp
- Transformations: camelCase to snake_case, remove links node

[deals](https://developers.activecampaign.com/reference#list-all-deals)
- Endpoint: https://{subdomain}.api-us1.com/deals
- Data key: deals
- Primary keys: id
- Replication strategy: Incremental (query all, filter results)
  - Bookmark: mdate
- Transformations: camelCase to snake_case, remove links node



## Authentication


## Quick Start

1. Install

    Clone this repository, and then install using setup.py. We recommend using a virtualenv:

    ```bash
    > virtualenv -p python3 venv
    > source venv/bin/activate
    > python setup.py install
    OR
    > cd .../tap-activecampaign
    > pip install .
    ```
2. Dependent libraries
    The following dependent libraries were installed.
    ```bash
    > pip install singer-python
    > pip install singer-tools
    > pip install target-stitch
    > pip install target-json
    
    ```
    - [singer-tools](https://github.com/singer-io/singer-tools)
    - [target-stitch](https://github.com/singer-io/target-stitch)
3. Create your tap's `config.json` file which should look like the following:

    ```json
      {
        "api_url": "YOUR_API_URL",
        "api_token": "YOUR_API_TOKEN",
        "start_date": "2019-01-01T00:00:00Z",
        "user_agent": "tap-activecampaign <api_user_email@your_company.com>"
      }
    ```
    
    Optionally, also create a `state.json` file. `currently_syncing` is an optional attribute used for identifying the last object to be synced in case the job is interrupted mid-stream. The next run would begin where the last job left off.

    ```json
      {
        "currently_syncing": "tasks",
        "bookmarks": {
          "tasks": "2020-07-21T21:30:59.000000Z",
          "contact_conversions": "2020-07-22T19:49:14.000000Z",
          "deal_activities": "2020-07-22T19:49:22.000000Z",
          "contacts": "2020-07-22T17:22:04.000000Z",
          "contact_lists": "2020-07-21T16:30:50.000000Z",
          "deal_custom_field_values": "2020-06-09T00:57:32.000000Z",
          "templates": "2020-06-09T11:56:58.000000Z",
          "conversions": "2020-07-22T19:47:41.000000Z",
          "ecommerce_order_activities": "2019-01-01T00:00:00Z",
          "contact_data": "2020-07-22T19:49:11.000000Z",
          "contact_deals": "2020-07-21T15:13:46.000000Z",
          "calendars": "2020-06-08T17:30:48.000000Z",
          "forms": "2020-06-25T14:25:36.000000Z",
          "contact_automations": "2020-07-22T22:20:45.000000Z",
          "saved_responses": "2020-06-09T15:49:45.000000Z",
          "site_messages": "2020-07-22T19:49:11.000000Z",
          "ecommerce_orders": "2020-06-09T00:18:37.000000Z",
          "messages": "2020-07-22T19:12:02.000000Z",
          "contact_custom_field_values": "2020-06-08T18:42:51.000000Z",
          "account_contacts": "2020-07-22T19:16:06.000000Z",
          "email_activities": "2020-07-22T19:17:54.000000Z",
          "automations": "2020-07-22T19:17:23.000000Z",
          "campaign_links": "2020-07-22T14:12:24.000000Z",
          "automation_blocks": "2020-07-22T19:48:41.000000Z",
          "account_custom_fields": "2020-06-08T18:12:27.000000Z",
          "bounce_logs": "2020-07-22T17:22:05.000000Z",
          "account_custom_field_values": "2020-07-21T21:39:08.000000Z",
          "sms": "2020-07-22T19:39:46.000000Z",
          "activities": "2020-07-22T19:49:14.000000Z",
          "conversion_triggers": "2020-07-22T19:47:54.000000Z",
          "lists": "2020-06-09T10:58:19.000000Z",
          "scores": "2020-07-21T20:51:20.000000Z",
          "deal_custom_fields": "2020-06-09T01:01:52.000000Z",
          "ecommerce_connections": "2020-06-09T00:12:54.000000Z",
          "configs": "2020-07-21T16:36:36.000000Z",
          "contact_emails": "2020-07-21T21:31:10.000000Z",
          "ecommerce_customers": "2020-06-09T00:18:12.000000Z",
          "contact_tags": "2020-07-21T16:31:42.000000Z",
          "accounts": "2020-07-22T19:16:06.000000Z",
          "deals": "2020-07-22T19:49:22.000000Z",
          "deal_groups": "2020-06-09T00:52:40.000000Z",
          "deal_stages": "2020-06-08T22:53:48.000000Z",
          "campaigns": "2020-07-22T17:22:05.000000Z"
        }
      }  
    ```

4. Run the Tap in Discovery Mode
    This creates a catalog.json for selecting objects/fields to integrate:
    ```bash
    tap-activecampaign --config config.json --discover > catalog.json
    ```
   See the Singer docs on discovery mode
   [here](https://github.com/singer-io/getting-started/blob/master/docs/DISCOVERY_MODE.md#discovery-mode).

5. Run the Tap in Sync Mode (with catalog) and [write out to state file](https://github.com/singer-io/getting-started/blob/master/docs/RUNNING_AND_DEVELOPING.md#running-a-singer-tap-with-a-singer-target)

    For Sync mode:
    ```bash
    > tap-activecampaign --config tap_config.json --catalog catalog.json > state.json
    > tail -1 state.json > state.json.tmp && mv state.json.tmp state.json
    ```
    To load to json files to verify outputs:
    ```bash
    > tap-activecampaign --config tap_config.json --catalog catalog.json | target-json > state.json
    > tail -1 state.json > state.json.tmp && mv state.json.tmp state.json
    ```
    To pseudo-load to [Stitch Import API](https://github.com/singer-io/target-stitch) with dry run:
    ```bash
    > tap-activecampaign --config tap_config.json --catalog catalog.json | target-stitch --config target_config.json --dry-run > state.json
    > tail -1 state.json > state.json.tmp && mv state.json.tmp state.json
    ```

6. Test the Tap
    
    While developing the activecampaign tap, the following utilities were run in accordance with Singer.io best practices:
    Pylint to improve [code quality](https://github.com/singer-io/getting-started/blob/master/docs/BEST_PRACTICES.md#code-quality):
    ```bash
    > pylint tap_activecampaign -d missing-docstring -d logging-format-interpolation -d too-many-locals -d too-many-arguments
    ```
    Pylint test resulted in the following score:
    ```bash
    Your code has been rated at 9.78/10
    ```

    To [check the tap](https://github.com/singer-io/singer-tools#singer-check-tap) and verify working:
    ```bash
    > tap-activecampaign --config tap_config.json --catalog catalog.json | singer-check-tap > state.json
    > tail -1 state.json > state.json.tmp && mv state.json.tmp state.json
    ```
    Check tap resulted in the following:
    ```bash
      The output is valid.
      It contained 720 messages for 59 streams.

          59 schema messages
          502 record messages
          159 state messages

      Details by stream:
      +------------------------------+---------+---------+
      | stream                       | records | schemas |
      +------------------------------+---------+---------+
      | ecommerce_order_activities   | 1       | 1       |
      | contact_emails               | 1       | 1       |
      | task_types                   | 6       | 1       |
      | email_activities             | 4       | 1       |
      | bounce_logs                  | 7       | 1       |
      | ecommerce_orders             | 1       | 1       |
      | contact_lists                | 9       | 1       |
      | contact_deals                | 2       | 1       |
      | ecommerce_customers          | 2       | 1       |
      | forms                        | 3       | 1       |
      | deal_custom_fields           | 5       | 1       |
      | deals                        | 16      | 1       |
      | contact_custom_field_options | 6       | 1       |
      | sms                          | 1       | 1       |
      | accounts                     | 9       | 1       |
      | contact_custom_field_rels    | 1       | 1       |
      | activities                   | 25      | 1       |
      | lists                        | 6       | 1       |
      | addresses                    | 3       | 1       |
      | saved_responses              | 3       | 1       |
      | messages                     | 26      | 1       |
      | conversions                  | 3       | 1       |
      | contact_data                 | 5       | 1       |
      | goals                        | 3       | 1       |
      | tags                         | 7       | 1       |
      | deal_activities              | 44      | 1       |
      | account_contacts             | 9       | 1       |
      | users                        | 2       | 1       |
      | segments                     | 16      | 1       |
      | contact_conversions          | 2       | 1       |
      | groups                       | 2       | 1       |
      | brandings                    | 1       | 1       |
      | ecommerce_order_products     | 2       | 1       |
      | calendars                    | 3       | 1       |
      | contact_custom_fields        | 2       | 1       |
      | automation_blocks            | 66      | 1       |
      | campaign_lists               | 18      | 1       |
      | scores                       | 2       | 1       |
      | deal_stages                  | 1       | 1       |
      | deal_group_users             | 1       | 1       |
      | webhooks                     | 2       | 1       |
      | campaign_links               | 21      | 1       |
      | contacts                     | 14      | 1       |
      | configs                      | 21      | 1       |
      | ecommerce_connections        | 2       | 1       |
      | conversion_triggers          | 7       | 1       |
      | campaigns                    | 12      | 1       |
      | account_custom_fields        | 13      | 1       |
      | deal_custom_field_values     | 9       | 1       |
      | tasks                        | 4       | 1       |
      | site_messages                | 2       | 1       |
      | campaign_messages            | 13      | 1       |
      | deal_groups                  | 3       | 1       |
      | templates                    | 1       | 1       |
      | contact_automations          | 19      | 1       |
      | contact_tags                 | 8       | 1       |
      | automations                  | 9       | 1       |
      | contact_custom_field_values  | 1       | 1       |
      | account_custom_field_values  | 15      | 1       |
      +------------------------------+---------+---------+

    ```
---

Copyright &copy; 2020 Stitch
