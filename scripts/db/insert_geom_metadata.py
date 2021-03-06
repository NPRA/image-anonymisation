"""
Simple script for creating, dropping, and inserting into the SDO geometry metadata table.
Use the command line arguments --create, --drop, --insert, to create, drop, and insert into the table.
"""
import argparse

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
    parser = argparse.ArgumentParser(description="Simple script for inserting metadata into the SDO geometry metadata table.")
    parser.add_argument("-t", "--table-name", dest="table_name", default=db_config.table_name,
                        help="Database table name.")
    args = parser.parse_args()
    table = Table(args.table_name)

    with DatabaseClient.connect() as conn:
        cursor = conn.cursor()

        columns = ", ".join([c.name for c in METADATA_COLUMNS])
        values = ", ".join([f":{c.name}" for c in METADATA_COLUMNS])
        insert_sql = f"INSERT INTO {METADATA_TABLE_NAME}({columns}) VALUES ({values})"

        rows = []
        for col in table.columns:
            if col.dtype == "SDO_GEOMETRY":
                diminfo = _create_diminfo(conn, col.spatial_metadata)
                row = {"TABLE_NAME": table.name, "COLUMN_NAME": col.name, "DIMINFO": diminfo,
                       "SRID": col.spatial_metadata["srid"]}
                rows.append(row)

        cursor.executemany(insert_sql, rows)
        conn.commit()


def _create_dim_element(dim_element_type, dim_name, lb, ub, tolerance):
    obj = dim_element_type.newobject()
    obj.SDO_DIMNAME = dim_name
    obj.SDO_LB = lb
    obj.SDO_UB = ub
    obj.SDO_TOLERANCE = tolerance
    return obj


def _create_diminfo(conn, spatial_metadata):
    dim_element_type = conn.gettype("MDSYS.SDO_DIM_ELEMENT")

    dim_elements = []
    for dim_element_data in spatial_metadata["dim_elements"]:
        dim_element = _create_dim_element(dim_element_type, dim_name=dim_element_data["name"],
                                          lb=dim_element_data["min"], ub=dim_element_data["max"],
                                          tolerance=dim_element_data["tol"])
        dim_elements.append(dim_element)

    dim_array_type = conn.gettype("MDSYS.SDO_DIM_ARRAY")
    dim_array = dim_array_type.newobject()
    dim_array.extend(dim_elements)
    return dim_array


if __name__ == '__main__':
    insert()
