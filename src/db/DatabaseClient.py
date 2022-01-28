import os
import pickle
import cx_Oracle as cxo

import config
from config import db_config
from src.Logger import LOGGER
from src.db import geometry
from src.db.Table import Table

# Cache directory for the cached rows
DB_CACHE_DIR = os.path.join(config.CACHE_DIRECTORY, "db")
# Error code for the uniqueness constraint.
UNIQUENESS_ERROR_CODE = "ORA-00001"


class DatabaseError(BaseException):
    """ Generic exception for database errors. """
    pass


class DatabaseLimitExceeded(BaseException):
    """ Exception which indicates that a limit is exceeded in the DatabaseClient. """
    pass


class DatabaseClient:
    """
    Class used to handle database writes. Connection parameters are specified in `src.db.db_config`. This class can also
    be instantiated as a context manager.

    :param max_n_accumulated_rows: Maximum number of rows to accumulate before actually writing them to the remote
                                   database.
    :type max_n_accumulated_rows: int
    """
    _CONNECTION_PWD = config.decrypt_db_password(db_config.encrypted_password)

    def __init__(self, max_n_accumulated_rows=8, max_n_errors=1000, max_cache_size=1000, table_name=None,
                 enable_cache=True):
        self.max_n_accumulated_rows = max_n_accumulated_rows
        self.max_n_errors = max_n_errors
        self.max_cache_size = max_cache_size
        self.enable_cache = enable_cache
        self.accumulated_rows = []
        self.cached_rows = []
        self.total_inserted = self.total_updated = self.total_errors = 0
        self._ignore_error_check = False

        if table_name is None:
            table_name = db_config.table_name
        self.table = Table(table_name)

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
        connection = cxo.connect(db_config.user, DatabaseClient._CONNECTION_PWD, db_config.dsn, encoding="UTF-8",
                                 nencoding="UTF-8")
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

        if self.enable_cache:
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

            if self.enable_cache:
                # Delete the cached files
                while self.cached_rows:
                    cache_file = self.cached_rows.pop(0)
                    if os.path.exists(cache_file):
                        os.remove(cache_file)
                    else:
                        LOGGER.warning(__name__, f"Could not find cache file to remove: {cache_file}")

        except cxo.DatabaseError as err:
            raise DatabaseError(f"cx_Oracle.DatabaseError: {str(err)}")

    def insert_or_update_rows(self, rows):
        """
        Insert `rows` into the database.

        :param rows: List of rows to be inserted. These should be on the form returned by
        `src.db.DatabaseClient.create_row`
        :type rows: list of dict
        """
        self._check_total_errors()

        with self.connect() as connection:
            cursor = connection.cursor()
            # Insert rows
            insert_errors = self._insert_rows(cursor, rows)
            
            uniqueness_errors, other_errors = split_errors_on_code(insert_errors, UNIQUENESS_ERROR_CODE)

            if other_errors:
                other_error_rows = [rows[e.offset] for e in other_errors]
                self.handle_errors(other_errors, other_error_rows, action="inserting into")

            # Commit insertions
            connection.commit()

            # Handle insert errors caused by uniqueness constraint.
            if uniqueness_errors:
                # Attempt to update the rows which could not be inserted.
                uniqueness_error_rows = [rows[e.offset] for e in uniqueness_errors]
                update_errors = self._update_rows(cursor, uniqueness_error_rows)
                # Commit updates
                connection.commit()
                # Handle update errors
                if update_errors:
                    update_error_rows = [uniqueness_error_rows[e.offset] for e in update_errors]
                    self.handle_errors(update_errors, update_error_rows, action="updating")

    def handle_errors(self, errors, rows, action="writing to"):
        """
        Log errors caused when running `cursor.executemany`.

        :param errors: Errors from `cursor.getbatcherrors`
        :type errors: list
        :param rows: Rows which caused the errors
        :type rows: list of dict
        :param action: Optional database action for the error message.
        :type action: str
        """
        # Increment total error counter
        self.total_errors += len(errors)

        # Create an error message
        msg = f"Got {len(errors)} error(s) while {action} the database:\n"
        msg += "\n".join([err.message for err in errors])
        # Log the error
        LOGGER.error(__name__, msg, save=False, email=config.uncaught_exception_email or config.processing_error_email, email_mode="error")

    def _insert_rows(self, cursor, rows):
        LOGGER.info(__name__, f"Attempting to insert {len(rows)} row(s) into the database.")
        # Attempt to insert the rows into the database. When we have `batcherrors = True`, the rows which do not
        # violate the unique constraint will be inserted normally. The rows which do violate the constraint will
        # not be inserted.
        cursor.executemany(self.table.insert_sql, rows, batcherrors=True)
        # Get the indices of the rows where the insertion failed.
        errors = [e for e in cursor.getbatcherrors()]

        # Add number of inserted rows to total counter
        n_inserted = len(rows) - len(errors)
        self.total_inserted += n_inserted

        LOGGER.info(__name__, f"Successfully inserted {n_inserted} row(s) into the database.")
        return errors

    def _update_rows(self, cursor, rows):
        LOGGER.info(__name__, f"Attempting to update {len(rows)} row(s) in the database.")
        # Attempt to update the rows. When we have `batcherrors = True`, the valid rows will be updated normally.
        cursor.executemany(self.table.update_sql, rows, batcherrors=True)
        # Get the errors caused by the rows where the update failed.
        errors = [e for e in cursor.getbatcherrors()]

        # Add number of updated rows to total counter
        n_updated = len(rows) - len(errors)
        self.total_updated += n_updated

        LOGGER.info(__name__, f"Successfully updated {n_updated} row(s) in the database.")
        return errors

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

    def _check_total_errors(self):
        if self._ignore_error_check:
            return

        # Check total number of errors
        if self.total_errors > self.max_n_errors:
            raise DatabaseLimitExceeded(f"Limit for total number of errors exceeded in DatabaseClient "
                                        f"({self.total_errors} > {self.max_n_errors})")
        # Check cache size
        if len(self.cached_rows) > self.max_cache_size:
            raise DatabaseLimitExceeded(f"Limit for total number of cached rows exceeded in DatabaseClient "
                                        f"({len(self.cached_rows)} > {self.max_cache_size})")

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
        cli._ignore_error_check = True
        try:
            cli.insert_or_update_rows(rows)
        except Exception as err:
            raise DatabaseError(f"Got error '{err}' when inserting cached rows into the database.") from err

    # Remove the cache files
    for cache_file in files:
        os.remove(cache_file)


def split_errors_on_code(errors, code):
    """
    Split the list of database errors into two lists. The first list will contain errors with error code `code`.
    The other list will contain the other errors

    :param errors: Database errors
    :type errors: list
    :param code: Code to split on. E.g. "ORA-00001" for failed uniqueness constraint
    :type code: str
    :return: Two lists. The first list will contain errors with error code `code`. The other list will contain the
             other errors
    :rtype: tuple of list
    """
    errors_for_code = []
    other_errors = []
    for err in errors:
        if err.message.startswith(code):
            errors_for_code.append(err)
        else:
            other_errors.append(err)
    return errors_for_code, other_errors
