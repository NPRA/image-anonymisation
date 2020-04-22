import os
import json
import pytest
import cx_Oracle as cxo
from collections import namedtuple
from uuid import uuid4

from src.db.columns import ID_COLUMN, COLUMNS, to_string


TEST_DB_USER = "system"
TEST_DB_PWD = "password"
TEST_DB_DSN = "localhost:1521/XE"
CFG = namedtuple("db_config", ["user", "pwd", "dsn", "schema", "table_name"])


def create_table(table_name, conn):
    create_table_sql = f"CREATE TABLE {table_name}("
    for col in [ID_COLUMN, *COLUMNS]:
        create_table_sql += to_string(col)
    create_table_sql = create_table_sql[:-1] + "\n)"

    conn.cursor().execute(create_table_sql)
    conn.commit()


def drop_table(table_name, conn):
    drop_table_sql = f"DROP TABLE {table_name}"
    conn.cursor().execute(drop_table_sql)
    conn.commit()


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
    dicts = []
    for filename in os.listdir(json_files_dir):
        if not filename.endswith(".json"):
            continue
        with open(os.path.join(json_files_dir, filename), "r") as f:
            dicts.append(json.load(f))

    return dicts

