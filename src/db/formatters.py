import json
import iso8601

from src.db import db_config
from src.db.setup_table import COLUMNS
from src.Logger import LOGGER


def get_insert_sql():
    """
    Get the SQL expression used to insert a row into the database

    :return: `INSERT` SQL expression
    :rtype: string
    """
    col_names = ", ".join([c.col_name for c in COLUMNS])
    values = ", ".join([":" + c.col_name for c in COLUMNS])
    insert_sql = f"INSERT INTO {db_config.table_name}({col_names}) VALUES ({values})"
    return insert_sql


def _format_timestamp(ts):
    out = iso8601.parse_date(ts)
    return out


def _format_number(x):
    if x is None:
        return None
    x = float(x)
    return int(x) if x.is_integer() else x


def _format_clob(d):
    return json.dumps(d)


FORMAT_FUNCS = {
    "NUMBER": _format_number,
    "DATE": _format_timestamp,
    "CLOB": _format_clob,
}


def create_row(json_dict):
    """
    Create a database row from the given `json_dict`. See `src.db.setup_table` for the list of columns.

    :param json_dict: EXIF data
    :type json_dict: dict
    :return: Dict representing the database row.
    :rtype: dict
    """
    out = {}
    for col in COLUMNS:
        if col.json_key == "self":
            out[col.col_name] = _format_clob(json_dict)
            continue

        if col.json_key not in json_dict:
            # Key was not found in JSON dict
            LOGGER.warning(__name__, f"Key {col.json_key} was not found in the JSON-dict. "
                                     f"Stored value will be 'None'")
            value = None
        else:
            value = json_dict[col.json_key]
            if value is None:
                # Key was found but value was None
                LOGGER.info(__name__, f"Got None value in JSON-dict for key {col.json_key}")
            else:
                # Format the value
                format_func = FORMAT_FUNCS.get(col.col_dtype, lambda x: x)
                value = format_func(value)
        out[col.col_name] = value
    return out
