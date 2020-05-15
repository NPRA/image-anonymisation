"""
Find all JSON-files in a directory tree, and insert their contents into the table specified in `src.db.db_config`.
"""
import json
import logging
import argparse
from tqdm import tqdm

from src.db.DatabaseClient import DatabaseClient
from src.io.TreeWalker import TreeWalker
from src.Logger import LOGGER


def get_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("-i", "--input-folder", dest="input_dir",
                        help="Base directory for finding .json files.")
    return parser.parse_args()


def process_json(paths, cli):
    with open(paths.input_file, "r") as f:
        contents = json.load(f)
    if "relative_input_dir" not in contents:
        contents["relative_input_dir"] = paths.relative_input_dir
    import numpy as np
    if np.random.random() > 1:
        contents["exif_fylke"] = None
    cli.add_row(contents)


def main():
    logging.basicConfig(level=logging.DEBUG, format=LOGGER.fmt, datefmt=LOGGER.datefmt)
    args = get_args()
    tree_walker = TreeWalker(args.input_dir, [], skip_webp=False, precompute_paths=True, ext="json")

    cli = DatabaseClient(max_n_accumulated_rows=2, max_cache_size=5, max_n_errors=1000)
    for paths in tqdm(tree_walker.walk()):
        try:
            process_json(paths, cli)
        except AssertionError as err:
            print(err)

    cli.close()


if __name__ == '__main__':
    main()
