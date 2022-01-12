import tap_tester.connections as connections
import tap_tester.runner as runner
import tap_tester.menagerie as menagerie
from base import ActiveCampaignTest

class ActiveCampaignAllFields(ActiveCampaignTest):
    """Ensure running the tap with all streams and fields selected results in the replication of all fields."""
     
    def name(self):
        return "activecampaign_all_fields"

    def test_run(self):
        """
        • Verify no unexpected streams were replicated
        • Verify that more than just the automatic fields are replicated for each stream. 
        • verify all fields for each stream are replicated
        """
        
        
        # Streams to verify all fields tests
        expected_streams = self.expected_check_streams()

        # We are not able to generate data for `contact_conversions` stream. 
        # For `sms` stream it requires Enterprise plan of account. So, removing it from expected_streams set.
        expected_streams = expected_streams - {'contact_conversions', 'sms'}
        
        expected_automatic_fields = self.expected_automatic_fields()
        conn_id = connections.ensure_connection(self)

        found_catalogs = self.run_and_verify_check_mode(conn_id)

        # table and field selection
        test_catalogs_all_fields = [catalog for catalog in found_catalogs
                                    if catalog.get('tap_stream_id') in expected_streams]

        self.perform_and_verify_table_and_field_selection(
            conn_id, test_catalogs_all_fields)

        # grab metadata after performing table-and-field selection to set expectations
        # used for asserting all fields are replicated
        stream_to_all_catalog_fields = dict()
        for catalog in test_catalogs_all_fields:
            stream_id, stream_name = catalog['stream_id'], catalog['stream_name']
            catalog_entry = menagerie.get_annotated_schema(conn_id, stream_id)
            fields_from_field_level_md = [md_entry['breadcrumb'][1]
                                          for md_entry in catalog_entry['metadata']
                                          if md_entry['breadcrumb'] != []]
            stream_to_all_catalog_fields[stream_name] = set(
                fields_from_field_level_md)

        self.run_and_verify_sync(conn_id)

        synced_records = runner.get_records_from_target_output()

        # Verify no unexpected streams were replicated
        synced_stream_names = set(synced_records.keys())
        self.assertSetEqual(expected_streams, synced_stream_names)
        
        
        for stream in expected_streams:
            with self.subTest(stream=stream):

                # expected values
                expected_all_keys = stream_to_all_catalog_fields[stream]
                expected_automatic_keys = expected_automatic_fields.get(
                    stream, set())

                # Verify that more than just the automatic fields are replicated for each stream.
                self.assertTrue(expected_automatic_keys.issubset(
                    expected_all_keys), msg='{} is not in "expected_all_keys"'.format(expected_automatic_keys-expected_all_keys))

                messages = synced_records.get(stream)
                # collect actual values
                actual_all_keys = set()
                for message in messages['messages']:
                    if message['action'] == 'upsert':
                        actual_all_keys.update(message['data'].keys())

                # As we can't generate following field by activecampaign APIs and UI, so removed it form expectation list.
                if stream == "ecommerce_orders":
                    expected_all_keys = expected_all_keys - {'order_products'}

                #  BUG | below keys are not synced due to typo mismatch  https://jira.talendforge.org/browse/TDL-16481
                # Fixed this bug in PR#10(https://github.com/singer-io/tap-activecampaign/pull/10). In that PR all fields
                # are replicated in the target which we verified by the all_fields test case without skipping the below fields.
                # Reference : https://github.com/singer-io/tap-activecampaign/blob/TDL-16481-update-schema/tests/test_all_fields.py#L84
                if stream == "brandings":
                    expected_all_keys = expected_all_keys - {'group_id', 'admin_template_httm', 'public_template_httm'}
                elif stream == "campaign_links":
                    expected_all_keys = expected_all_keys - {'uniqueclicks'}
                elif stream == "contact_custom_fields":
                    expected_all_keys = expected_all_keys - {'defvalue'}
                elif stream == "contact_lists":
                    expected_all_keys = expected_all_keys - {'ip4_sub', 'ip4_unsub'}
                elif stream == "contacts":
                    expected_all_keys = expected_all_keys - {'org_id'}
                elif stream == "conversions":
                    expected_all_keys = expected_all_keys - {'enforce_limit'}
                elif stream == "deal_activities":
                    expected_all_keys = expected_all_keys - {'d_stage_id', 'data_old_val'}
                elif stream == "deal_stages":
                    expected_all_keys = expected_all_keys - {'card_region_1', 'card_region_2', 'card_region_3', 'card_region_4', 'card_region_5'}
                elif stream == "forms":
                    expected_all_keys = expected_all_keys - {'recents'}
                elif stream == "tasks":
                    expected_all_keys = expected_all_keys - {'deal_task_type'}   
                elif stream == "templates":
                    expected_all_keys = expected_all_keys - {'contant'}
                elif stream == "users":
                    expected_all_keys = expected_all_keys - {'local_zone_id'}                    

                # verify all fields for each stream are replicated
                self.assertSetEqual(expected_all_keys, actual_all_keys)