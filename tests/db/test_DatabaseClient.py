import pytest
from unittest import mock

from src.db.DatabaseClient import DatabaseClient

from tests.db.conftest import check_results


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
