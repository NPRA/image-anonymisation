import pytest
from unittest import mock

from src.db.DatabaseClient import DatabaseClient

from tests.db.conftest import check_results


def insert_json_dicts_and_check_rows(cfg, connect, json_dicts):
    with mock.patch("src.db.DatabaseClient.cxo.connect", new=connect):
        with mock.patch("src.db.DatabaseClient.db_config.table_name", new=cfg.table_name):
            # Add the rows to the database
            with DatabaseClient() as cli:
                for jd in json_dicts:
                    cli.add_row(jd)

    # Check that the inserted rows correspond with the json dicts.
    with connect() as conn:
        check_results(conn, json_dicts, cfg.table_name)


@pytest.mark.db
def test_DatabaseClient_insert_accumulated_rows(config_and_connect, json_dicts):
    cfg, connect = config_and_connect
    # Insert the contents of the json dicts into the database, and check that they were inserted correctly
    insert_json_dicts_and_check_rows(cfg, connect, json_dicts)


@pytest.mark.db
def test_DatabaseClient_insert_if_exists_else_update(config_and_connect, json_dicts):
    cfg, connect = config_and_connect

    # Insert the contents of the json dicts into the database, and check that they were inserted correctly
    insert_json_dicts_and_check_rows(cfg, connect, json_dicts)

    # Edit the json dicts
    for i, jd in enumerate(json_dicts):
        jd["exif_mappenavn"] = str(i)

    # "Insert" the new rows and check them. We expect the existing rows to be updated and no new ones to be created.
    insert_json_dicts_and_check_rows(cfg, connect, json_dicts)
