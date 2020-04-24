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


def process_json(filename, cli):
    with open(filename, "r") as f:
        contents = json.load(f)
    cli.add_row(contents)


def main():
    logging.basicConfig(level=logging.DEBUG, format=LOGGER.fmt, datefmt=LOGGER.datefmt)
    args = get_args()
    tree_walker = TreeWalker(args.input_dir, [], skip_webp=False, precompute_paths=True, ext="json")

    with DatabaseClient(max_n_accumulated_rows=8) as cli:
        for paths in tqdm(tree_walker.walk()):
            process_json(paths.input_file, cli)


if __name__ == '__main__':
    main()
