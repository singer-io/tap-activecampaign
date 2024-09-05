import tap_tester.connections as connections
import tap_tester.runner as runner
import tap_tester.menagerie as menagerie
from base import ActiveCampaignTest


class ActiveCampaignPagination(ActiveCampaignTest):
    """
    Ensure tap can replicate multiple pages of data for streams that use pagination.
    """
    API_LIMIT = 100
    def name(self):
        return "activecampaign_pagination_test"

    def test_run(self):
        """
        • Verify that for each stream you can get multiple pages of data.  
        This requires we ensure more than 1 page of data exists at all times for any given stream.
        • Verify by pks that the data replicated matches the data we expect.
        """

        # Streams to verify all fields tests
        expected_streams = self.expected_check_streams()

        # We are not able to generate enough data to test pagination for below streams,
        # `brandings`, `configs`, `conversions`, `conversion_triggers`, `goals`, `contact_conversions`, `sms`, `user`.
        # The current plan allows only 25 users. So, skipped `user` stream. sms feature is not supported for the current plan.
        # So, removing it all from expected_streams set.
        # BUG TDL-26417: Skip 'bounce_logs'
        expected_streams = expected_streams - {'bounce_logs', 'contact_conversions', 'sms', 'users', 'brandings', 'configs', 'conversions', 'conversion_triggers', 'goals'}

        conn_id = connections.ensure_connection(self)

        found_catalogs = self.run_and_verify_check_mode(conn_id)

        # table and field selection
        test_catalogs_all_fields = [catalog for catalog in found_catalogs
                                    if catalog.get('tap_stream_id') in expected_streams]

        self.perform_and_verify_table_and_field_selection(
            conn_id, test_catalogs_all_fields)

        record_count_by_stream = self.run_and_verify_sync(conn_id)

        synced_records = runner.get_records_from_target_output()

        # Verify no unexpected streams were replicated
        synced_stream_names = set(synced_records.keys())
        self.assertSetEqual(expected_streams, synced_stream_names)

        for stream in expected_streams:
            with self.subTest(stream=stream):

                # expected values
                expected_primary_keys = self.expected_primary_keys()[stream]
         
                # verify that we can paginate with all fields selected
                record_count_sync = record_count_by_stream.get(stream, 0)
                self.assertGreater(record_count_sync, self.API_LIMIT,
                                    msg="The number of records is not over the stream max limit")

                primary_keys_list = [tuple([message.get('data').get(expected_pk) for expected_pk in expected_primary_keys])
                                        for message in synced_records.get(stream).get('messages')
                                        if message.get('action') == 'upsert']

                primary_keys_list_1 = primary_keys_list[:self.API_LIMIT]
                primary_keys_list_2 = primary_keys_list[self.API_LIMIT:2*self.API_LIMIT]

                primary_keys_page_1 = set(primary_keys_list_1)
                primary_keys_page_2 = set(primary_keys_list_2)

                # Verify by primary keys that data is unique for page
                self.assertTrue(
                    primary_keys_page_1.isdisjoint(primary_keys_page_2))
