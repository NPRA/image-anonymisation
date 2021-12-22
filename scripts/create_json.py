"""
Find all JSON-files in a directory tree, and insert their contents into the table specified in `src.db.db_config`.
"""
import os
import sys
import logging
import argparse
from datetime import datetime
from socket import gethostname
import config
from src.io.TreeWalker import TreeWalker
from src.Logger import LOGGER, LOG_SEP, logger_excepthook
from src.Workers import EXIFWorker


PROCESSING_EXCEPTIONS = (
    OSError,
    SystemError,
    FileNotFoundError,
    KeyError,
)


def get_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("-i", "--input-folder", dest="input_folder",
                        help="Base directory for input images.")
    parser.add_argument("-o", "--output-folder", dest="output_folder",
                        help="Base output directory JSON files")
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
        log_dir = os.path.abspath(args.log_folder)
        os.makedirs(args.log_folder, exist_ok=True)
        log_file_name = config.log_file_name.format(datetime=datetime.now().strftime("%Y-%m-%d_%H%M%S"),
                                                    hostname=gethostname())
        log_file = os.path.join(log_dir, log_file_name)
        LOGGER.set_log_file(log_file)
    
    input_dir = os.path.abspath(args.input_folder)
    output_dir = os.path.abspath(args.output_folder)

    os.makedirs(args.output_folder, exist_ok=True)
    tree_walker = TreeWalker(input_dir, [output_dir], skip_webp=False, precompute_paths=True)
    return tree_walker


def main():
    tree_walker = initialize()

    for i, paths in enumerate(tree_walker.walk()):
        count_str = f"{i + 1} of {tree_walker.n_valid_images}"
        LOGGER.info(__name__, LOG_SEP)
        LOGGER.info(__name__, f"Iteration: {count_str}.")
        LOGGER.info(__name__, f"Processing file {paths.input_file}")

        try:
            worker = EXIFWorker(None, paths, None)
            worker.get()
        except PROCESSING_EXCEPTIONS as err:
            LOGGER.error(f"Got error '{type(err).__name__}: {str(err)}' when creating JSON from image. "
                         f"File: {paths.input_file}")


if __name__ == '__main__':
    main()
