import os
import pickle
import cx_Oracle as cxo

import config
from config import db_config
from src.Logger import LOGGER
from src.db import geometry
from src.db.Table import Table

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
        self.table = Table(db_config.table_name)

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
        row = self.table.create_row(json_dict)
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
            self.insert_or_update_rows(self.accumulated_rows)
            # Clear the list of accumulated rows
            self.accumulated_rows = []

            # Delete the cached files
            while self.cached_rows:
                cache_file = self.cached_rows.pop(0) 
                if os.path.exists(cache_file):
                    os.remove(cache_file)
                else:
                    LOGGER.warning(__name__, f"Could not find cache file to remove: {cache_file}")

        except cxo.DatabaseError as err:
            raise AssertionError(f"cx_Oracle.DatabaseError: {str(err)}")

    def insert_or_update_rows(self, rows):
        """
        Insert `rows` into the database.

        :param rows: List of rows to be inserted. These should be on the form returned by
        `src.db.DatabaseClient.create_row`
        :type rows: list of dict
        """
        with self.connect() as connection:
            cursor = connection.cursor()

            n_inserted, insert_errors = self._insert_rows(cursor, rows)

            if insert_errors:
                LOGGER.warning(__name__, f"INSERT failed for {len(insert_errors)} row(s)")
                # Filter out the rows which caused errors
                insert_error_rows = [rows[e.offset] for e in insert_errors]
                # Call an update on these rows
                n_updated, update_errors = self._update_rows(cursor, insert_error_rows)

                if update_errors:
                    update_error_rows =



            # Counts
            n_updated = len(error_indices)
            n_inserted = len(rows) - n_updated
            # Commit the changes
            connection.commit()

        LOGGER.info(__name__, f"Successfully inserted {n_inserted} rows into the database.")
        if n_updated > 0:
            LOGGER.info(__name__, f"Successfully updated {n_updated} rows in the database.")

    def _insert_rows(self, cursor, rows):
        LOGGER.info(__name__, f"Attempting to insert {len(rows)} row(s) into the database.")
        # Attempt to insert the rows into the database. When we have `batcherrors = True`, the rows which do not
        # violate the unique constraint will be inserted normally. The rows which do violate the constraint will
        # not be inserted.
        cursor.executemany(self.table.insert_sql, rows, batcherrors=True)
        # Get the indices of the rows where the insertion failed.
        errors = [e for e in cursor.getbatcherrors()]
        n_inserted = len(rows) - len(errors)
        return n_inserted, errors

    def _update_rows(self, cursor, rows):
        LOGGER.info(__name__, f"Attempting to update {len(rows)} row(s) in the database.")
        cursor.executemany(self.table.update_sql, rows, batcherrors=True)
        # Get the indices of the rows where the insertion failed.
        errors = [e for e in cursor.getbatcherrors()]
        n_updated = len(rows) - len(errors)
        return n_updated, errors

    def _cache_row(self, row):
        """
        Write the cache file for the given row. The file's path will be appended to `self.cached_rows`.

        :param row: Row to cache
        :type row: dict
        """
        os.makedirs(DB_CACHE_DIR, exist_ok=True)
        cache_filename = os.path.join(DB_CACHE_DIR, row[self.table.pk_column] + ".pkl")
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
