import os
import json
import argparse
from tqdm import tqdm

from src.db.DatabaseClient import DatabaseClient
from src.io.TreeWalker import TreeWalker


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
    args = get_args()
    tree_walker = TreeWalker(args.input_dir, [], skip_webp=False, precompute_paths=True, ext="json")
    cli = DatabaseClient(max_n_accumulated_rows=10)

    for input_path, _, filename in tqdm(tree_walker.walk()):
        filepath = os.path.join(input_path, filename)
        process_json(filepath, cli)

    cli.close()


if __name__ == '__main__':
    main()
