"""
Simple script for creating, dropping, and inserting into the SDO geometry metadata table.
Use the command line arguments --create, --drop, --insert, to create, drop, and insert into the table.
"""

import sys

from config import db_config
from src.db.DatabaseClient import DatabaseClient
from src.db.columns import COLUMNS, COL, to_string

METADATA_TABLE_NAME = "user_sdo_geom_metadata_values"
METADATA_COLUMNS = [
    COL(col_name="TABLE_NAME",  col_dtype="VARCHAR(32)",   get_value=None, not_null=False),
    COL(col_name="COLUMN_NAME", col_dtype="VARCHAR(32)",   get_value=None, not_null=False),
    COL(col_name="DIMINFO",     col_dtype="SDO_DIM_ARRAY", get_value=None, not_null=False),
    COL(col_name="SRID",        col_dtype="NUMBER",        get_value=None, not_null=False),
]


def drop():
    """
    Drop the metadata table
    """
    with DatabaseClient.connect() as conn:
        cursor = conn.cursor()
        drop_sql = f"DROP TABLE {METADATA_TABLE_NAME}"
        cursor.execute(drop_sql)
        conn.commit()
    print(f"Table successfully dropped with command\n{drop_sql}")


def create():
    create_table_sql = f"CREATE TABLE {METADATA_TABLE_NAME} ("
    for col in METADATA_COLUMNS:
        create_table_sql += to_string(col)
    create_table_sql = create_table_sql[:-1] + "\n)"

    with DatabaseClient.connect() as conn:
        cursor = conn.cursor()
        cursor.execute(create_table_sql)
        conn.commit()

    print(f"Table successfully created with command\n{create_table_sql}")


def insert():
    with DatabaseClient.connect() as conn:
        cursor = conn.cursor()

        columns = ", ".join([c.col_name for c in METADATA_COLUMNS])
        values = ", ".join([f":{c.col_name}" for c in METADATA_COLUMNS])
        insert_sql = f"INSERT INTO {METADATA_TABLE_NAME}({columns}) VALUES ({values})"

        diminfo = _create_diminfo(conn)
        rows = []
        for col in COLUMNS:
            if col.col_dtype == "SDO_GEOMETRY":
                row = {"TABLE_NAME": db_config.table_name, "COLUMN_NAME": col.col_name, "DIMINFO": diminfo, "SRID": 4326}
                rows.append(row)

        cursor.execute(insert_sql, rows[0])
        conn.commit()


def _create_dim_element(dim_element_type, dim_name, lb, ub, tolerance):
    obj = dim_element_type.newobject()
    obj.SDO_DIMNAME = dim_name
    obj.SDO_LB = lb
    obj.SDO_UB = ub
    obj.SDO_TOLERANCE = tolerance
    return obj


def _create_diminfo(conn):
    dim_element_type = conn.gettype("MDSYS.SDO_DIM_ELEMENT")
    elements = [
        _create_dim_element(dim_element_type, 'Longitude', -180, 180, 0.5),
        _create_dim_element(dim_element_type, 'Latitude', -90, 90, 0.5),
        _create_dim_element(dim_element_type, 'Height', -1000, 3000, 0.5)
    ]
    dim_array_type = conn.gettype("MDSYS.SDO_DIM_ARRAY")
    dim_array = dim_array_type.newobject()
    dim_array.extend(elements)
    return dim_array


if __name__ == '__main__':
    if "--drop" in sys.argv:
        drop()
    if "--create" in sys.argv:
        create()
    if "--insert" in sys.argv:
        insert()
