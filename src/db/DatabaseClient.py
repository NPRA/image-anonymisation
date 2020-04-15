import cx_Oracle as cxo

from src.Logger import LOGGER
from src.db import db_config
from src.db.formatters import create_row, get_insert_sql

INSERT_SQL = get_insert_sql()


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

    @staticmethod
    def connect():
        """
        Connect to the database, and set the schema if it is specified.

        :return: Database connection object
        :rtype: cxo.Connection
        """
        connection = cxo.connect(db_config.user, db_config.pwd, db_config.dsn)
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
        row = create_row(json_dict)
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
                cursor.executemany(INSERT_SQL, self.accumulated_rows)
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
