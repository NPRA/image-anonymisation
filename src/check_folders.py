import os
import logging
import argparse
from collections import namedtuple, OrderedDict

import config
from src.Logger import LOGGER, LOG_SEP
from src.io.TreeWalker import TreeWalker


def get_args():
    """ Get the command-line arguments. """
    parser = argparse.ArgumentParser(description='Output file checker.')
    parser.add_argument("-i", "--input-folder", dest="input_folder",
                        help="Base directory for input images.")
    parser.add_argument("-o", "--output-folder", dest="output_folder",
                        help="Base directory for masked (output) images and metadata files")
    parser.add_argument("-a", "--archive-folder", dest="archive_folder", default=None,
                        help="Optional base directory for archiving original images.")
    parser.add_argument("--ignore-config", dest="ignore_config", action="store_true",
                        help="Ignore the config variables and check for all possible files.")
    args = parser.parse_args()
    return args


def get_expected_files(args):
    ef = namedtuple("expected_file", ["name", "attr"])

    if args.ignore_config:
        expected_files = [
            ef(name="Output image", attr="output_file"),
            ef(name="Input json", attr="input_json"),
            ef(name="Output json", attr="output_json"),
            ef(name="Input mask", attr="input_webp"),
            ef(name="Output mask", attr="output_webp"),
            ef(name="Archive image", attr="archive_file"),
            ef(name="Archive json", attr="archive_json"),
            ef(name="Archive mask", attr="archive_webp")
        ]
    else:
        expected_files = [ef(name="Output image", attr="output_file")]

        if config.local_json:
            expected_files.append(ef(name="Input json", attr="input_json"))
        if config.remote_json:
            expected_files.append(ef(name="Output json", attr="output_json"))

        if config.local_mask:
            expected_files.append(ef(name="Input mask", attr="input_webp"))
        if config.remote_mask:
            expected_files.append(ef(name="Output mask", attr="output_webp"))

        if args.archive_folder is not None:
            expected_files.append(ef(name="Archive image", attr="archive_file"))
            if config.archive_json:
                expected_files.append(ef(name="Archive json", attr="archive_json"))
            if config.archive_mask:
                expected_files.append(ef(name="Archive mask", attr="archive_webp"))

    return expected_files


def initialize_tree_walker(args):
    # Get the absolute path of the directories
    base_input_dir = os.path.abspath(args.input_folder)
    base_output_dir = os.path.abspath(args.output_folder)
    mirror_dirs = [base_output_dir]

    if args.archive_folder is not None:
        mirror_dirs.append(os.path.abspath(args.archive_folder))

    # Initialize the walker
    tree_walker = TreeWalker(base_input_dir, mirror_dirs, skip_webp=False, precompute_paths=True)
    return tree_walker


def check_file(name, file_path):
    if file_path is None:
        status = "None"
    elif os.path.isfile(file_path):
        status = "OK"
    else:
        status = "Missing"
    msg = "{:15s}{:8s} ({})".format(name, status, file_path)
    print(msg)
    return status


def check_paths(expected_files, paths, cumulative_status):
    for ef in expected_files:
        file_path = getattr(paths, ef.attr)
        status = check_file(ef.name, file_path)
        cumulative_status[ef.name][status] += 1


def print_summary(status_values, cumulative_status):
    print(f"{LOG_SEP}\nSummary:")
    row = "{:15s}{:10s}{:10s}{:10s}"
    print(row.format("", *status_values))
    for name, d in cumulative_status.items():
        print(row.format(name, *[str(d[s]) for s in status_values]))

    print(LOG_SEP)


def main():
    # Configure logger
    logging.basicConfig(level=getattr(logging, config.log_level), format=LOGGER.fmt, datefmt=LOGGER.datefmt)

    args = get_args()
    tree_walker = initialize_tree_walker(args)
    expected_files = get_expected_files(args)

    status_values = ["OK", "Missing", "None"]
    cumulative_status = {ef.name: {s: 0 for s in status_values} for ef in expected_files}

    for i, paths in enumerate(tree_walker.walk()):
        print(f"{LOG_SEP}\nImage {i+1}/{tree_walker.n_valid_images}")
        check_paths(expected_files, paths, cumulative_status)

    print_summary(status_values, cumulative_status)


if __name__ == '__main__':
    main()
