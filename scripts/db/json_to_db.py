"""
Find all JSON-files in a directory tree, and insert their contents into the table specified in `src.db.db_config`.
"""
import os
import sys
import json
import logging
import argparse
from datetime import datetime
from socket import gethostname

import config
from src.db.DatabaseClient import DatabaseClient, DatabaseError
from src.io.TreeWalker import TreeWalker
from src.io.file_access_guard import wait_until_path_is_found
from src.Logger import LOGGER, LOG_SEP, logger_excepthook


PROCESSING_EXCEPTIONS = (
    OSError,
    SystemError,
    FileNotFoundError,
    KeyError,
    json.JSONDecodeError,
    DatabaseError
)


def get_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("-i", "--input-folder", dest="input_dir",
                        help="Base directory for finding .json files.")
    parser.add_argument("-t", "--table-name", dest="table_name", default=None,
                        help="Database table name.")
    parser.add_argument("-l", "--log-folder", dest="log_folder", default=None,
                        help="Optional path to directory of log file. The log file will be named "
                             "<log\\folder>\\<timestamp> <hostname>.log")
    parser.add_argument("-k", dest="config_file", default=None,
                        help=f"Path to custom configuration file. See the README for details. Default is "
                             f"{config.DEFAULT_CONFIG_FILE}")
    return parser.parse_args()


def set_excepthook(hooks):
    """
    Configure sys.excepthook to call all functions in `hooks` before calling the default excepthook.

    :param hooks: List of hooks. Each element must be a function with three arguments: Exception type, exception
                  instance, and traceback instance.
    :type hooks: list of function
    """
    def excepthook(etype, ex, tb):
        # Call hooks
        for hook in hooks:
            hook(etype, ex, tb)
        # Call the default excepthook.
        sys.__excepthook__(etype, ex, tb)
    # Register the custom hook
    sys.excepthook = excepthook


def initialize():
    logging.basicConfig(level=logging.DEBUG, format=LOGGER.fmt, datefmt=LOGGER.datefmt)
    set_excepthook([logger_excepthook])

    args = get_args()

    if args.log_folder is not None:
        os.makedirs(args.log_folder, exist_ok=True)
        log_file_name = config.log_file_name.format(datetime=datetime.now().strftime("%Y-%m-%d_%H%M%S"),
                                                    hostname=gethostname())
        log_file = os.path.join(args.log_folder, log_file_name)
        LOGGER.set_log_file(log_file)

    tree_walker = TreeWalker(args.input_dir, [], skip_webp=False, precompute_paths=True, ext="json")
    database_client = DatabaseClient(table_name=args.table_name,
                                     max_n_accumulated_rows=config.db_max_n_accumulated_rows,
                                     max_n_errors=config.db_max_n_errors,
                                     max_cache_size=config.db_max_cache_size,
                                     enable_cache=False)

    return tree_walker, database_client


def get_summary(tree_walker, database_client, start_datetime):
    """
    Log a summary of the masking process.

    :param tree_walker: `TreeWalker` instance used in masking.
    :type tree_walker: TreeWalker
    :param database_client:
    :type database_client:
    :param start_datetime: Datetime object indicating when the program started.
    :type start_datetime: datetime.datetime
    """

    lines = [
        "Script finished.",
        f"Files found: {tree_walker.n_valid_images}",
        f"Row(s) inserted into the database: {database_client.total_inserted}",
        f"Row(s) updated in the database: {database_client.total_updated}",
        f"Row(s) failed to insert/update in the database: {database_client.total_errors}",
        f"Total time spent: {str(datetime.now() - start_datetime)}"
    ]
    summary = "\n".join(lines)
    return summary


def load_json(paths):
    wait_until_path_is_found(paths.input_file)
    with open(paths.input_file, "r", encoding="utf-8") as f:
        json_dict = json.load(f)
    return json_dict


def main():
    tree_walker, database_client = initialize()
    start_datetime = datetime.now()

    for i, paths in enumerate(tree_walker.walk()):
        count_str = f"{i + 1} of {tree_walker.n_valid_images}"
        LOGGER.info(__name__, LOG_SEP)
        LOGGER.info(__name__, f"Iteration: {count_str}.")
        LOGGER.info(__name__, f"Processing file {paths.input_file}")

        try:
            json_dict = load_json(paths)
            database_client.add_row(json_dict)
        except PROCESSING_EXCEPTIONS as err:
            LOGGER.error(__name__, f"Got error '{type(err).__name__}: {str(err)}' when writing JSON to Database. "
                                   f"File: {paths.input_file}")

    LOGGER.info(__name__, LOG_SEP)
    LOGGER.info(__name__, "Writing remaining files to Database")
    database_client.close()

    summary_str = get_summary(tree_walker, database_client, start_datetime)
    LOGGER.info(__name__, LOG_SEP)
    LOGGER.info(__name__, summary_str)


if __name__ == '__main__':
    main()
