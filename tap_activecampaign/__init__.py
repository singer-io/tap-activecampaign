import sys
import json
import argparse
import singer
from singer import metadata, utils
from tap_activecampaign.client import ActiveCampaignClient
from tap_activecampaign.discover import discover
from tap_activecampaign.sync import sync

LOGGER = singer.get_logger()

REQUIRED_CONFIG_KEYS = [
    'api_url',
    'api_token',
    'start_date',
    'user_agent'
]

def do_discover():

    LOGGER.info('Starting discover')
    catalog = discover()
    json.dump(catalog.to_dict(), sys.stdout, indent=2)
    LOGGER.info('Finished discover')


@singer.utils.handle_top_exception(LOGGER)
def main():

    parsed_args = singer.utils.parse_args(REQUIRED_CONFIG_KEYS)

    with ActiveCampaignClient(parsed_args.config['api_url'],
                              parsed_args.config['api_token'],
                              parsed_args.config['user_agent'],
                              parsed_args.config.get('request_timeout')) as client:

        state = {}
        if parsed_args.state:
            state = parsed_args.state

        if parsed_args.discover:
            do_discover()
        elif parsed_args.catalog:
            sync(client=client,
                 config=parsed_args.config,
                 catalog=parsed_args.catalog,
                 state=state)

if __name__ == '__main__':
    main()
