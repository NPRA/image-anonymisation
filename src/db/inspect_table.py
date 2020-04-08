import json
import cx_Oracle as cxo
from pprint import pprint, pformat
from datetime import datetime

import config
from src.db.DatabaseClient import DatabaseClient
from src.db.setup_table import COLUMNS, TABLE_NAME


def output_type_handler(cursor, name, defaultType, size, precision, scale):
    if defaultType == cxo.CLOB:
        return cursor.var(cxo.LONG_STRING, arraysize=cursor.arraysize)


def lob_to_dict(lob):
    return json.loads(lob)


def datetime_to_str(dt):
    return datetime.strftime(dt, config.datetime_format)


def print_result(res, width=120):
    print(width * "-")
    print_dict = {}
    for col, elem in zip(COLUMNS, res):
        if col.col_dtype == "DATE":
            elem = datetime_to_str(elem)
        elif col.col_dtype == "CLOB":
            elem = lob_to_dict(elem)
        print_dict[col.col_name] = elem

    pprint(print_dict, width=width, depth=1)


if __name__ == '__main__':
    with DatabaseClient() as cli:
        with cli.connect() as connection:
            connection.outputtypehandler = output_type_handler
            cursor = connection.cursor()
            cursor.execute(f"SELECT * FROM {TABLE_NAME}")
            for res in cursor:
                print_result(res)
