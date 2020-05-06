"""
Simple script for creating, dropping, and inserting into the SDO geometry metadata table.
Use the command line arguments --create, --drop, --insert, to create, drop, and insert into the table.
"""
from config import db_config
from src.db.DatabaseClient import DatabaseClient
from src.db.Table import Column, Table

METADATA_TABLE_NAME = "MDSYS.USER_SDO_GEOM_METADATA"
METADATA_COLUMNS = [
    Column(name="TABLE_NAME",  dtype="VARCHAR(32)",   formatter=None, extra=None),
    Column(name="COLUMN_NAME", dtype="VARCHAR(32)",   formatter=None, extra=None),
    Column(name="DIMINFO",     dtype="SDO_DIM_ARRAY", formatter=None, extra=None),
    Column(name="SRID",        dtype="NUMBER",        formatter=None, extra=None),
]


def insert():
    table = Table(db_config.table_name)

    with DatabaseClient.connect() as conn:
        cursor = conn.cursor()

        columns = ", ".join([c.name for c in METADATA_COLUMNS])
        values = ", ".join([f":{c.name}" for c in METADATA_COLUMNS])
        insert_sql = f"INSERT INTO {METADATA_TABLE_NAME}({columns}) VALUES ({values})"

        diminfo = _create_diminfo(conn)
        rows = []
        for col in table.columns:
            if col.dtype == "SDO_GEOMETRY":
                row = {"TABLE_NAME": table.name, "COLUMN_NAME": col.name, "DIMINFO": diminfo, "SRID": 4326}
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
    insert()
