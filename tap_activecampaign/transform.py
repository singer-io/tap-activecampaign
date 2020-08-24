import singer
import humps

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

    return new_json


def transform_json(this_json, data_key):
    if data_key in this_json:
        converted_json = humps.decamelize(this_json[data_key])
    else:
        converted_json = humps.decamelize(this_json)

    fixed_records = fix_records(converted_json)

    return fixed_records
