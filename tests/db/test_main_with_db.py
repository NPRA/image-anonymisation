import os
import time
import pytest
from unittest import mock
from func_timeout import func_timeout, FunctionTimedOut

from tests.db.conftest import check_results, load_json_files
from tests.test_main import run_main, check_files


@pytest.mark.db
@pytest.mark.parametrize("enable_exports,enable_async", [
    (True, True),
    (True, False),
    (False, True),
    (False, False)
])
def test_main_with_db(get_tmp_data_dir, get_config, get_args, config_and_connect, enable_exports, enable_async):
    """
    End-to-end test for the `src.main.main` function. This test also checks that database writes work as expected, by
    enabling database writing in the config, and then checking that the entries written to the test database correspond
    to the exported  JSON files.

    :param get_args: Fixture-function which gets the command line arguments
    :type get_args: function
    :param get_config: Fixture-function which gets the config
    :type get_config: function
    :param get_tmp_data_dir: Fixture-function which sets up a temporary data directory
    :type get_tmp_data_dir: function
    :param enable_exports: Enable saving of extra output files (mask, json, and archive)
    :type enable_exports: bool
    :param enable_async: Enable asynchronous processing
    :type enable_async: bool
    """
    # Setup a temporary directory
    tmp_dir = get_tmp_data_dir(subdirs=["real"])

    # Booleans for archiving and output file saving.
    archive = enable_exports
    # We set `local_json = True` so we have somewhere to get the JSON files
    config_params = dict(local_json=True, remote_json=enable_exports, local_mask=enable_exports,
                         remote_mask=enable_exports, enable_async=enable_async, write_exif_to_db=True,
                         db_max_n_accumulated_rows=2)

    # Set the archive folder
    if archive:
        archive_folder = os.path.join(tmp_dir, "arch")
    else:
        archive_folder = None

    # Get the command line arguments
    args = get_args(input_folder=os.path.join(tmp_dir, "real"), output_folder=os.path.join(tmp_dir, "out"),
                    archive_folder=archive_folder, clear_cache=False)
    # Get the config
    cfg = get_config(CACHE_DIRECTORY=os.path.join(tmp_dir, "_cache"), **config_params)

    # Get the database config and connect function
    db_config, db_connect = config_and_connect
    # Run main
    run_main_with_db(cfg, args, db_connect, db_config)

    # Wait for the asynchronous export to complete
    time.sleep(5)
    # Check that all files were created/not created as expected
    check_files(tmp_dir, cfg, args)

    # Load the JSON files so we can check the entries in the database
    json_dicts = load_json_files(args.output_folder)
    # Check that the rows in the database match the json files
    with db_connect() as conn:
        check_results(conn, json_dicts, db_config.table_name)


@pytest.mark.db
@pytest.mark.parametrize("timeout", [20, 22.5, 25])
def test_main_with_db_and_interrupt(get_tmp_data_dir, get_args, get_config, config_and_connect, timeout):
    """
    Check that the main function is capable of recovering from "random" interruptions. This test uses the `func_timeout`
    module to simulate an interrupt, calls main again, and checks that the produced output is as expected. This test
    also checks that the entries written to the database are as expected.


    :param get_args: Fixture-function which gets the command line arguments
    :type get_args: function
    :param get_config: Fixture-function which gets the config
    :type get_config: function
    :param get_tmp_data_dir: Fixture-function which sets up a temporary data directory
    :type get_tmp_data_dir: function
    :param timeout: Number of seconds to wait before interrupting the first call to `src.main.main`.
    :type timeout: int | float
    """
    tmp_dir = get_tmp_data_dir(subdirs=["real"])

    # Get the command line arguments
    args = get_args(input_folder=os.path.join(tmp_dir, "real"), output_folder=os.path.join(tmp_dir, "out"),
                    archive_folder=os.path.join(tmp_dir, "arch"), clear_cache=True)
    # Get the config
    cfg = get_config(CACHE_DIRECTORY=os.path.join(tmp_dir, "_cache"), local_json=True, remote_json=True,
                     local_mask=True, remote_mask=True, enable_async=True, write_exif_to_db=True,
                     db_max_n_accumulated_rows=16)

    # Get the database config and connection function
    db_config, db_connect = config_and_connect

    # Start main, and abort it after `timeout` seconds.
    try:
        func_timeout(timeout, run_main_with_db, args=[cfg, args, db_connect, db_config])
    except FunctionTimedOut as err:
        print(err)

    # We expect an assertion error to be raised, since main was aborted.
    with pytest.raises(AssertionError):
        check_files(tmp_dir, cfg, args)

    # Run main again. This time, let it finish
    run_main_with_db(cfg, args, db_connect, db_config)

    # Check that the expected files were written.
    check_files(tmp_dir, cfg, args)

    # Load the JSON files so we can check the entries in the database
    json_dicts = load_json_files(args.output_folder)
    # Check that the rows in the database match the json files
    with db_connect() as conn:
        check_results(conn, json_dicts, db_config.table_name)


def run_main_with_db(cfg, args, db_connect, db_config):
    with mock.patch("src.db.DatabaseClient.cxo.connect", new=db_connect):
        with mock.patch("src.db.DatabaseClient.db_config.table_name", new=db_config.table_name):
            run_main(cfg, args)