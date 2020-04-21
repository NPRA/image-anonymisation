import sys
import cx_Oracle as cxo
from collections import namedtuple

from src.db import db_config, formatters

#: Prototype column
COL = namedtuple("column", ["col_name", "col_dtype", "get_value", "not_null"])
#: The `COLUMNS` list specifies the columns in the table. Each column is represented as a namedtuple with four elements:
#:
#: * `col_name`: The name of the column
#: * `col_dtype`: The SQL datatype of the column
#: * `get_value`: A function that returns the value of the column for a given dictionary. The dictionary is assumed
#:   to contain the same key-value-pairs as the JSON-file written by the anonymisation application.
#:   The return type of the function must be compatible with `col_dtype`. For instance, if
#:   `col_dtype="VARCHAR(...)"`, then `get_value` should return a string. Note that if
#:   `col_dtype="SDO_GEOMETRY"`, then `get_value` should return a `src.db.geometry.SDOGeometry` object.
#: * `not_null`: True if the value cannot be null. False otherwise
COLUMNS = [
    COL(col_name="Tidspunkt",          col_dtype="DATE",         get_value=formatters.Tidspunkt,          not_null=True),
    COL(col_name="Retning",            col_dtype="NUMBER",       get_value=formatters.Retning,            not_null=True),
    COL(col_name="Posisjon",           col_dtype="SDO_GEOMETRY", get_value=formatters.Posisjon,           not_null=True),
    COL(col_name="FylkeNummer",        col_dtype="VARCHAR(255)", get_value=formatters.FylkeNummer,        not_null=True),
    COL(col_name="Vegkategori",        col_dtype="VARCHAR(255)", get_value=formatters.Vegkategori,        not_null=True),
    COL(col_name="Vegstatus",          col_dtype="VARCHAR(255)", get_value=formatters.Vegstatus,          not_null=True),
    COL(col_name="Vegnummer",          col_dtype="VARCHAR(255)", get_value=formatters.Vegnummer,          not_null=True),
    COL(col_name="StrekningReferanse", col_dtype="VARCHAR(255)", get_value=formatters.StrekningReferanse, not_null=True),
    COL(col_name="Meter",              col_dtype="NUMBER",       get_value=formatters.Meter,              not_null=True),
    COL(col_name="Mappenavn",          col_dtype="VARCHAR(255)", get_value=formatters.Mappenavn,          not_null=True),
    COL(col_name="Filnavn",            col_dtype="VARCHAR(255)", get_value=formatters.Filnavn,            not_null=True),
    COL(col_name="JsonData",           col_dtype="CLOB",         get_value=formatters.JsonData,           not_null=True),
    COL(col_name="ReflinkID",          col_dtype="NUMBER",       get_value=formatters.ReflinkID,          not_null=False),
    COL(col_name="ReflinkPosisjon",    col_dtype="NUMBER",       get_value=formatters.ReflinkPosisjon,    not_null=False),
    COL(col_name="DetekterteObjekter", col_dtype="CLOB",         get_value=formatters.DetekterteObjekter, not_null=False),
    COL(col_name="Aar",                col_dtype="NUMBER",       get_value=formatters.Aar,                not_null=True),
    COL(col_name="Feltkode",           col_dtype="VARCHAR(255)", get_value=formatters.Feltkode,           not_null=True),
]


if __name__ == '__main__':
    create_table_sql = f"CREATE TABLE {db_config.table_name}("
    for col in COLUMNS:
        create_table_sql += "\n    {:20s} {:12}".format(col.col_name, col.col_dtype)
        if col.not_null:
            create_table_sql += " {:8s}".format("NOT NULL")
        create_table_sql += ","

    create_table_sql = create_table_sql[:-1] + "\n)"

    with cxo.connect(db_config.user, db_config.pwd, db_config.dsn) as connection:
        if db_config.schema is not None:
            connection.current_schema = db_config.schema

        cursor = connection.cursor()

        if "--drop" in sys.argv:
            cursor.execute(f"DROP TABLE {db_config.table_name}")
            print(f"Deleted table {db_config.table_name}")

        cursor.execute(create_table_sql)

    print(f"Table {db_config.table_name} created successfully with command:\n{create_table_sql}")
