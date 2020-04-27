import os
import pickle
import cx_Oracle as cxo

import config
from src.Logger import LOGGER
from src.db import db_config, geometry
from src.db.columns import COLUMNS, ID_COLUMN_NAME

DB_CACHE_DIR = os.path.join(config.CACHE_DIRECTORY, "db")


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
        self.cached_rows = []
        self.insert_sql, self.update_sql = self.get_insert_and_update_sql()

    @staticmethod
    def get_insert_and_update_sql():
        """
        Get the SQL expression used to insert a row into the database

        :return: `INSERT` SQL expression
        :rtype: string
        """
        col_names = ", ".join([c.col_name for c in COLUMNS])
        values = ", ".join([":" + c.col_name for c in COLUMNS])
        insert_sql = f"INSERT INTO {db_config.table_name}({col_names}) VALUES ({values})"

        col_names_equals_values = ", ".join([f"{c.col_name} = :{c.col_name}" for c in COLUMNS])
        update_sql = f"UPDATE {db_config.table_name} " \
                     f"SET {col_names_equals_values} " \
                     f"WHERE {ID_COLUMN_NAME} = :{ID_COLUMN_NAME}"

        return insert_sql, update_sql

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
                LOGGER.error(__name__, f"Got error '{type(err).__name__}: {err}' while getting value for database "
                                       f"column {col.col_name}. Value will be set to None")
                value = None
            out[col.col_name] = value
        return out

    @staticmethod
    def input_type_handler(cursor, value, num_elements):
        """Input type handler which converts `src.db.geometry.SDOGeometry` objects to oracle SDO_GEOMETRY objects."""
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
        self._cache_row(row)

        if len(self.accumulated_rows) >= self.max_n_accumulated_rows:
            self.insert_accumulated_rows()

    def insert_accumulated_rows(self):
        """
        Insert all accumulated rows into the database
        """
        try:
            # Insert the rows
            self.insert_rows(self.accumulated_rows)
            # Clear the list of accumulated rows
            self.accumulated_rows = []

            # Delete the cached files
            while self.cached_rows:
                os.remove(self.cached_rows.pop(0))

        except cxo.DatabaseError as err:
            raise AssertionError(f"cx_Oracle.DatabaseError: {str(err)}")

    def insert_rows(self, rows):
        """
        Insert `rows` into the database.

        :param rows: List of rows to be inserted. These should be on the form returned by
        `src.db.DatabaseClient.create_row`
        :type rows: list of dict
        """
        with self.connect() as connection:
            cursor = connection.cursor()
            # Attempt to insert the rows into the database. When we have `batcherrors = True`, the rows which do not
            # violate the unique constraint will be inserted normally. The rows which do violate the constraint will
            # not be inserted.
            cursor.executemany(self.insert_sql, rows, batcherrors=True)

            # Get the indices of the rows where the insertion failed.
            error_indices = [e.offset for e in cursor.getbatcherrors()]

            # If we have any rows which caused an error.
            if error_indices:
                LOGGER.warning(__name__, f"Found {len(error_indices)} rows where the {ID_COLUMN_NAME} already "
                                         f"existed in the database. These will be updated.")
                # Filter out the rows which caused errors
                error_rows = [rows[i] for i in error_indices]
                # Call an update on these rows
                cursor.executemany(self.update_sql, error_rows)

            # Counts
            n_updated = len(error_indices)
            n_inserted = len(rows) - n_updated
            # Commit the changes
            connection.commit()

        LOGGER.info(__name__, f"Successfully inserted {n_inserted} rows into the database.")
        if n_updated > 0:
            LOGGER.info(__name__, f"Successfully updated {n_updated} rows in the database.")

    def _cache_row(self, row):
        """
        Write the cache file for the given row. The file's path will be appended to `self.cached_rows`.

        :param row: Row to cache
        :type row: dict
        """
        os.makedirs(DB_CACHE_DIR, exist_ok=True)
        cache_filename = os.path.join(DB_CACHE_DIR, row[ID_COLUMN_NAME] + ".pkl")
        self.cached_rows.append(cache_filename)
        with open(cache_filename, "wb") as f:
            pickle.dump(row, f)

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


def clear_db_cache():
    """
    Traverse the database cache directory and insert all cached rows into the database. If insertion was successful, the
    cache files will be deleted.
    """
    if not os.path.isdir(DB_CACHE_DIR):
        return

    rows = []
    files = []
    for filename in os.listdir(DB_CACHE_DIR):
        if not filename.endswith(".pkl"):
            continue

        cache_file = os.path.join(DB_CACHE_DIR, filename)
        LOGGER.debug(__name__, f"Found database cache file: {cache_file}")
        # Load the cached row and append it to `rows`
        with open(cache_file, "rb") as f:
            rows.append(pickle.load(f))
        # Store the path to the cached row
        files.append(cache_file)

    # Return if we didn't find any valid rows.
    if not rows:
        return

    # Attempt to insert the rows into the database
    with DatabaseClient() as cli:
        try:
            cli.insert_rows(rows)
        except Exception as err:
            raise RuntimeError(f"Got error '{err}' when inserting cached rows into the database.") from err

    # Remove the cache files
    for cache_file in files:
        os.remove(cache_file)
