import pytest
from unittest import mock

from src.db.columns import COLUMNS
from src.db.DatabaseClient import DatabaseClient


def check_row(row, expected_row):
    skip_dtypes = ["CLOB", "SDO_GEOMETRY", "DATE"]

    for i, col in enumerate(COLUMNS):
        if col.col_dtype not in skip_dtypes:
            # Add 1 to skip the ID column
            value = row[i+1]
            expected_value = expected_row[col.col_name]
            assert value == expected_value, f"Value in database not equal to expected value. ({value} != {expected_value})"


def check_results(conn, json_dicts, table_name):
    cursor = conn.cursor()
    cursor.execute(f"SELECT * FROM {table_name}")
    count = 0
    for row, expected_dict in zip(cursor, json_dicts):
        expected_row = DatabaseClient.create_row(expected_dict)
        check_row(row, expected_row)
        count += 1

    assert len(json_dicts) == count


@pytest.mark.db
def test_DatabaseClient_insert_accumulated_rows(config_and_connect, json_dicts):
    cfg, connect = config_and_connect
    
    with mock.patch("src.db.DatabaseClient.cxo.connect", new=connect):
        with mock.patch("src.db.DatabaseClient.db_config.table_name", new=cfg.table_name):
            cli = DatabaseClient(max_n_accumulated_rows=1)
            for jd in json_dicts:
                cli.add_row(jd)

    with connect() as conn:
        check_results(conn, json_dicts, cfg.table_name)
