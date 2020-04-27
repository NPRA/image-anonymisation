"""
Print all rows of the table specified in `src.db.db_config`. Should only be used for debugging purposes.
"""
import json
import cx_Oracle as cxo
from pprint import pprint
from datetime import datetime

import config
from config import db_config
from src.db import geometry
from src.db.DatabaseClient import DatabaseClient
from src.db.columns import COLUMNS


WIDTH = 150
SEP = WIDTH * "-"


def output_type_handler(cursor, name, defaultType, size, precision, scale):
    if defaultType == cxo.CLOB:
        return cursor.var(cxo.LONG_STRING, arraysize=cursor.arraysize)


def lob_to_dict(lob):
    if lob is None:
        return {}
    return json.loads(lob)


def datetime_to_str(dt):
    return datetime.strftime(dt, config.datetime_format)


def sdo_geometry_to_str(sdo):
    gtype = sdo.SDO_GTYPE
    srid = sdo.SDO_SRID
    elem_info = sdo.SDO_ELEM_INFO.aslist()
    ordinates = sdo.SDO_ORDINATES.aslist()
    return str(geometry.SDOGeometry(gtype, srid, elem_info, ordinates))


def print_result(res):
    print(SEP)
    print_dict = {}
    for col, elem in zip(COLUMNS, res):
        if col.col_dtype == "DATE":
            elem = datetime_to_str(elem)
        elif col.col_dtype == "CLOB":
            elem = lob_to_dict(elem)
        elif col.col_dtype == "SDO_GEOMETRY":
            elem = sdo_geometry_to_str(elem)
        print_dict[col.col_name] = elem

    pprint(print_dict, width=WIDTH, depth=None)


if __name__ == '__main__':
    with DatabaseClient.connect() as connection:
        connection.outputtypehandler = output_type_handler
        cursor = connection.cursor()
        cursor.execute(f"SELECT * FROM {db_config.table_name}")
        count = 0
        for res in cursor:
            print_result(res)
            count += 1
        print(SEP)
        print(f"Found {count} records in table.")
