import cx_Oracle as cxo

from src.Logger import LOGGER
from src.db import db_config, geometry
from src.db.columns import COLUMNS


class DatabaseClient:
    """
    Class used to handle database writes. Connection parameters are specified in `src.db.db_config`. This class can also
    be instantiated as a context manager.

    :param max_n_accumulated_rows: Maximum number of rows to accumulate before actually writing them to the remote
                                   database.
    :type max_n_accumulated_rows: int
    """
    def __init__(self, max_n_accumulated_rows=8):
        self.max_n_accumulated_rows = max_n_accumulated_rows
        self.accumulated_rows = []
        self.insert_sql = self.get_insert_sql()

    @staticmethod
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

    @staticmethod
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
            try:
                value = col.get_value(json_dict)
            except Exception as err:
                LOGGER.error(__name__, f"Got error '{err}' while getting value for database column {col.col_name}. "
                                       f"Value will be set to None")
                value = None
            out[col.col_name] = value
        return out

    @staticmethod
    def input_type_handler(cursor, value, num_elements):
        if isinstance(value, geometry.SDOGeometry):
            in_converter, obj_type = geometry.get_geometry_converter(cursor.connection)
            var = cursor.var(cxo.OBJECT, arraysize=num_elements, inconverter=in_converter, typename=obj_type.name)
            return var

    @staticmethod
    def connect():
        """
        Connect to the database, and set the schema if it is specified. An appropriate input type handler will also
        be set for the connection, in order to make it compatible with spatial objects.

        :return: Database connection object
        :rtype: cxo.Connection
        """
        connection = cxo.connect(db_config.user, db_config.pwd, db_config.dsn, encoding="UTF-8", nencoding="UTF-8")
        connection.inputtypehandler = DatabaseClient.input_type_handler
        if db_config.schema is not None:
            connection.current_schema = db_config.schema
        return connection

    def add_row(self, json_dict):
        """
        Add the contents of `json_dict` to the buffer, which will eventually be written to the remote database. When the
        buffer size (number of accumulated rows) exceeds `self.max_n_accumulated_rows`, all the accumulated rows will be
        written to the database. The buffer will then be cleared.

        :param json_dict: EXIF data
        :type json_dict: dict
        """
        row = self.create_row(json_dict)
        self.accumulated_rows.append(row)

        if len(self.accumulated_rows) >= self.max_n_accumulated_rows:
            self.insert_accumulated_rows()
            self.accumulated_rows = []

    def insert_accumulated_rows(self):
        """
        Insert all accumulated rows into the database
        """
        try:
            with self.connect() as connection:
                cursor = connection.cursor()
                cursor.executemany(self.insert_sql, self.accumulated_rows)
                connection.commit()
            LOGGER.info(__name__, f"Successfully inserted {len(self.accumulated_rows)} rows into the database.")
        except cxo.DatabaseError as err:
            raise AssertionError(f"cx_Oracle.DatabaseError: {str(err)}")

    def close(self):
        """
        Insert the remaining accumulated rows into the database
        """
        if self.accumulated_rows:
            self.insert_accumulated_rows()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
