import re
import singer

LOGGER = singer.get_logger()


def fix_records(this_json):
    new_json = []
    for rec in this_json:
        if 'links' in rec:
            if isinstance(rec['links'], dict):
                rec.pop('links', None)
        for key, val in rec.items():
            if 'date' in key or 'stamp' in key or key in ('socialdata_lastcheck', 'deleted_at'):
                if val == '0000-00-00 00:00:00':
                    rec[key] = None

        new_json.append(rec)


SPLIT_RE = re.compile(r"([\-_]*(?<=[^0-9])(?=[A-Z])[^A-Z]*[\-_]*)")
def to_snake_case(input):
    return "_".join(s for s in SPLIT_RE.split(input) if s)

def transform_json(this_json, stream_name, data_key):
    if data_key in this_json:
        converted_json = to_snake_case(this_json[data_key])
    else:
        converted_json = to_snake_case(this_json)

    fix_records(converted_json)

    return converted_json
