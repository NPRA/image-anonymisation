import os
import json
import pytest
import cx_Oracle as cxo
from collections import namedtuple
from uuid import uuid4

from src.db.columns import COLUMNS, to_string
from src.db.DatabaseClient import DatabaseClient


TEST_DB_USER = "system"
TEST_DB_PWD = "password"
TEST_DB_DSN = "localhost:1521/XE"
CFG = namedtuple("db_config", ["user", "pwd", "dsn", "schema", "table_name"])


@pytest.fixture
def config_and_connect():
    table_name = "test_" + str(uuid4()).replace("-", "_")
    cfg = CFG(user=TEST_DB_USER, pwd=TEST_DB_PWD, dsn=TEST_DB_DSN, schema=None, table_name=table_name)

    def connect(*_, **__):
        try:
            # Here we use the Connection class directly, to avoid a stack overflow if we mock `cxo.connect` later.
            return cxo.Connection(cfg.user, cfg.pwd, cfg.dsn, encoding="UTF-8", nencoding="UTF-8")
        except Exception as err:
            raise cxo.DatabaseError("Could not connect to the test database. Did you forget to start it?") from err

    with connect() as conn:
        # Create a temporary table
        create_table(table_name, conn)

    # Return the config and the connect function
    yield cfg, connect

    # Teardown
    with connect() as conn:
        # Drop temporary table
        drop_table(table_name, conn)


@pytest.fixture
def json_dicts():
    json_files_dir = r"tests\data\json_files"
    return load_json_files(json_files_dir)


def load_json_files(json_dir):
    json_dicts = []
    for filename in os.listdir(json_dir):
        if filename.endswith(".json"):
            with open(os.path.join(json_dir, filename), "r") as f:
                json_dicts.append(json.load(f))
    return json_dicts


def create_table(table_name, conn):
    create_table_sql = f"CREATE TABLE {table_name}("
    for col in COLUMNS:
        create_table_sql += to_string(col)
    create_table_sql = create_table_sql[:-1] + "\n)"

    conn.cursor().execute(create_table_sql)
    conn.commit()


def drop_table(table_name, conn):
    drop_table_sql = f"DROP TABLE {table_name}"
    conn.cursor().execute(drop_table_sql)
    conn.commit()


def check_row(row, expected_row):
    skip_dtypes = ["CLOB", "SDO_GEOMETRY", "DATE"]

    for i, col in enumerate(COLUMNS):
        if col.col_dtype not in skip_dtypes:
            value = row[i]
            expected_value = expected_row[col.col_name]
            assert value == expected_value, f"Value in database not equal to expected value. " \
                                            f"({value} != {expected_value})"


def check_results(conn, json_dicts, table_name):
    cursor = conn.cursor()
    cursor.execute(f"SELECT * FROM {table_name}")
    count = 0
    for row, expected_dict in zip(cursor, json_dicts):
        expected_row = DatabaseClient.create_row(expected_dict)
        check_row(row, expected_row)
        count += 1

    assert len(json_dicts) == count
