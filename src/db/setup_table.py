import sys
import cx_Oracle as cxo
from collections import namedtuple

from src.db import db_config

COL = namedtuple("column", ["col_name", "col_dtype", "json_key"])
COLUMNS = [
    COL(col_name="bildeuuid",            col_dtype="VARCHAR2(255)", json_key="bildeuuid"),
    COL(col_name="anonymisert_bildefil", col_dtype="VARCHAR2(511)", json_key="anonymisert_bildefil"),
    COL(col_name="tid",                  col_dtype="DATE",          json_key="exif_tid"),
    COL(col_name="gpsposisjon",          col_dtype="VARCHAR2(255)", json_key="exif_gpsposisjon"),
    COL(col_name="reflinkid",            col_dtype="NUMBER",        json_key="exif_reflinkid"),
    COL(col_name="reflinkposisjon",      col_dtype="NUMBER",        json_key="exif_reflinkposisjon"),
    COL(col_name="detekterte_objekter",  col_dtype="CLOB",          json_key="detekterte_objekter"),
    COL(col_name="json_data",            col_dtype="CLOB",          json_key="self")
]


if __name__ == '__main__':
    cols = [f"{c.col_name} {c.col_dtype}" for c in COLUMNS]
    create_table_sql = f"CREATE TABLE {db_config.table_name}({', '.join(cols)})"

    with cxo.connect(db_config.user, db_config.pwd, db_config.dsn) as connection:
        if db_config.schema is not None:
            connection.current_schema = db_config.schema

        cursor = connection.cursor()

        if "--drop" in sys.argv:
            cursor.execute(f"DROP TABLE {db_config.table_name}")
            print(f"Deleted table {db_config.table_name}")

        cursor.execute(create_table_sql)

    print(f"Table {db_config.table_name} created successfully with command:\n{create_table_sql}")
