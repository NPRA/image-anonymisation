from collections import namedtuple

from src.db import formatters

# Prototype column
COL = namedtuple("column", ["col_name", "col_dtype", "get_value", "not_null"])

#: Name of the ID-column. This will also be the primary key in the database.
ID_COLUMN_NAME = "BildeID"

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
    COL(col_name=ID_COLUMN_NAME,       col_dtype="VARCHAR(255) PRIMARY KEY", get_value=formatters.BildeID,            not_null=False),
    COL(col_name="Tidspunkt",          col_dtype="DATE",                     get_value=formatters.Tidspunkt,          not_null=True),
    COL(col_name="Retning",            col_dtype="NUMBER",                   get_value=formatters.Retning,            not_null=True),
    COL(col_name="Posisjon",           col_dtype="SDO_GEOMETRY",             get_value=formatters.Posisjon,           not_null=True),
    COL(col_name="FylkeNummer",        col_dtype="NUMBER",                   get_value=formatters.FylkeNummer,        not_null=True),
    COL(col_name="Vegkategori",        col_dtype="VARCHAR(255)",             get_value=formatters.Vegkategori,        not_null=True),
    COL(col_name="Vegstatus",          col_dtype="VARCHAR(255)",             get_value=formatters.Vegstatus,          not_null=True),
    COL(col_name="Vegnummer",          col_dtype="NUMBER",                   get_value=formatters.Vegnummer,          not_null=True),
    COL(col_name="StrekningReferanse", col_dtype="VARCHAR(255)",             get_value=formatters.StrekningReferanse, not_null=True),
    COL(col_name="Meter",              col_dtype="NUMBER",                   get_value=formatters.Meter,              not_null=True),
    COL(col_name="Mappenavn",          col_dtype="VARCHAR(255)",             get_value=formatters.Mappenavn,          not_null=True),
    COL(col_name="Filnavn",            col_dtype="VARCHAR(255)",             get_value=formatters.Filnavn,            not_null=True),
    COL(col_name="JsonData",           col_dtype="CLOB",                     get_value=formatters.JsonData,           not_null=True),
    COL(col_name="ReflinkID",          col_dtype="NUMBER",                   get_value=formatters.ReflinkID,          not_null=False),
    COL(col_name="ReflinkPosisjon",    col_dtype="NUMBER",                   get_value=formatters.ReflinkPosisjon,    not_null=False),
    COL(col_name="DetekterteObjekter", col_dtype="CLOB",                     get_value=formatters.DetekterteObjekter, not_null=False),
    COL(col_name="Aar",                col_dtype="NUMBER",                   get_value=formatters.Aar,                not_null=True),
    COL(col_name="Feltkode",           col_dtype="VARCHAR(255)",             get_value=formatters.Feltkode,           not_null=True),
]


def to_string(col):
    col_str = "\n    {:20s} {:12}".format(col.col_name, col.col_dtype)
    if col.not_null:
        col_str += " {:8s}".format("NOT NULL")
    col_str += ","
    return col_str
