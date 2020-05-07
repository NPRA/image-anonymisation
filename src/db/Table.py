import config
from src.Logger import LOGGER
from src.db import formatters


class DatabaseTableError(Exception):
    pass


class Column:
    """
    Class representing a column in a table. The `Column.get_value` function is used to get the column value for a
    specific row from the given JSON dict.

    :param name: Name of the column
    :type name: str
    :param dtype: SQL datatype of the column
    :type dtype: str
    :param formatter: Name of a function in `src.db.formatters`. This function is assigned to `Column.get_value`, and
                      can be used to get the column value for a specific row from the given JSON dict. If `formatter` is
                      None, `Column.get_value` will be None.
    :type formatter: str | None
    :param extra: Optional extra information about the column, e.g. "NOT NULL" or "PRIMARY KEY".
    :type extra: str | None
    :param spatial_metadata: Metadata (dimensions, SRID) for the column. Only used when
                             `dtype == "SDO_GEOMETRY"`
    :type spatial_metadata: dict
    """
    def __init__(self, name, dtype, formatter, extra=None, spatial_metadata=None):
        self.name = name
        self.dtype = dtype
        self.extra = extra

        if formatter is not None:
            # Get the formatting function
            self.get_value = getattr(formatters, formatter)
        else:
            self.get_value = None

        if dtype == "SDO_GEOMETRY":
            # Check the `spatial_metadata` dict.
            if spatial_metadata is None:
                raise DatabaseTableError(f"Empty 'spatial_metadata' for column '{name}'")
            if "dimension" not in spatial_metadata:
                raise DatabaseTableError(f"Missing key 'dimension' in 'spatial_metadata' for column '{name}'")
            if "srid" not in spatial_metadata:
                raise DatabaseTableError(f"Missing key 'srid' in 'spatial_metadata' for column '{name}'")
            self.spatial_metadata = spatial_metadata

    def __str__(self):
        s = "{:20s} {:12}".format(self.name, self.dtype)
        if self.extra is not None:
            s += " {:12s}".format(self.extra)
        return s

    def __repr__(self):
        return self.__str__()


class Table:
    def __init__(self, name):
        """
        Class representing a database table The information (primary key column, and columns) about the table should be
        contained in a file named `<name>.yml` located in `config/db_tables`.

        :param name: Name of the table.
        :type name: str
        """
        table_dict = config.get_db_table_dict(name)
        self.name = name
        self.pk_column = table_dict["pk_column"]
        self.columns = [Column(**d) for d in table_dict["columns"]]
        self.insert_sql, self.update_sql = self.get_insert_and_update_sql()

    def get_insert_and_update_sql(self):
        """
        Get the SQL expression used to insert a row into the table

        :return: `INSERT` SQL expression
        :rtype: string
        """
        col_names = ", ".join([c.name for c in self.columns])
        values = ", ".join([":" + c.name for c in self.columns])
        insert_sql = f"INSERT INTO {self.name}({col_names}) VALUES ({values})"

        col_names_equals_values = ", ".join([f"{c.name} = :{c.name}" for c in self.columns])
        update_sql = f"UPDATE {self.name} " \
                     f"SET {col_names_equals_values} " \
                     f"WHERE {self.pk_column} = :{self.pk_column}"

        return insert_sql, update_sql

    def create_row(self, json_dict):
        """
        Create a database row from the given `json_dict`. See `src.db.setup_table` for the list of columns.

        :param json_dict: EXIF data
        :type json_dict: dict
        :return: Dict representing the database row.
        :rtype: dict
        """
        out = {}
        for col in self.columns:
            try:
                value = col.get_value(json_dict)
            except Exception as err:
                LOGGER.error(__name__, f"Got error '{type(err).__name__}: {err}' while getting value for database "
                                       f"column {col.name}. Value will be set to None")
                value = None
            out[col.name] = value
        return out
