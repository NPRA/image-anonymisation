import json
import iso8601
import cx_Oracle as cxo

from src.db import db_config
from src.db.formatters import create_row, get_insert_sql

INSERT_SQL = get_insert_sql()


class DatabaseClient:
    def __init__(self, max_n_accumulated_rows=8):
        self.max_n_accumulated_rows = max_n_accumulated_rows
        self.accumulated_rows = []

    @staticmethod
    def connect():
        connection = cxo.connect(db_config.user, db_config.pwd, db_config.dsn)
        if db_config.schema is not None:
            connection.current_schema = db_config.schema
        return connection

    def add_row(self, json_dict):
        row = create_row(json_dict)
        self.accumulated_rows.append(row)

        if len(self.accumulated_rows) >= self.max_n_accumulated_rows:
            self.insert_accumulated_rows()
            self.accumulated_rows = []

    def insert_accumulated_rows(self):
        try:
            with self.connect() as connection:
                cursor = connection.cursor()
                cursor.executemany(INSERT_SQL, self.accumulated_rows)
                connection.commit()
        except cxo.DatabaseError as err:
            raise AssertionError(f"cx_Oracle.DatabaseError: {str(err)}")

    def close(self):
        if self.accumulated_rows:
            self.insert_accumulated_rows()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
