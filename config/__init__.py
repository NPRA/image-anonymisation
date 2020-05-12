import os
import yaml
import argparse
from datetime import datetime


DEFAULT_CONFIG_FILE = os.path.join("config", "default_config.yml")


def _load_yml(file_path):
    """
    Load the contents of the YAML file `file_path`

    :param file_path: Path to YAML file
    :type file_path: str
    :return: YAML file contents
    :rtype: dict
    """
    try:
        with open(file_path, "r") as f:
            contents = yaml.safe_load(f)
    except Exception as err:
        raise RuntimeError(f"Error while loading YAML-file '{file_path}'") from err
    return contents


def _get_config_file():
    """
    Get the config file from the command line arguments

    :return: Path to configuration file
    :rtype: str
    """
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("-k", dest="config_file", default=DEFAULT_CONFIG_FILE)

    args, *_ = parser.parse_known_args()
    config_file = os.path.abspath(args.config_file)
    return config_file


def _load_from_config_file(config_file):
    default_config = _load_yml(DEFAULT_CONFIG_FILE)
    if config_file == DEFAULT_CONFIG_FILE:
        config_vars = default_config
    else:
        custom_config = _load_yml(config_file)
        config_vars = {}
        for key in default_config.keys():
            if key not in custom_config:
                raise RuntimeError(f"Configuration variable '{key}' not found in config file '{config_file}'")
            config_vars[key] = custom_config[key]

    globals().update(config_vars)


# Get the config file from the command line arguments
config_file = _get_config_file()
# Load the contents of the config file to the current namespace
_load_from_config_file(config_file)

# Version tag
config_last_edited = datetime.fromtimestamp(os.stat(config_file).st_mtime).strftime("%Y%m%d")
version = f"P{application_version}_K{config_last_edited}"

# Import constants
from .constants import *


def get_db_table_dict(table_name):
    """
    Parse the yaml-file corresponding to the table named `table_name`, and return the contents as a dictionary.

    :param table_name: Name of the table
    :type table_name: str
    :return: Contents of `<table_name>.yml`
    :rtype: dict
    """
    table_file = os.path.join(PROJECT_ROOT, "config", "db_tables", f"{table_name}.yml")
    table_dict = _load_yml(table_file)

    # Check that the dict is valid
    expected_elements = [
        # (key, expected value type)
        ("pk_column", str),
        ("columns", list)
    ]
    for key, expected_type in expected_elements:
        if key not in table_dict:
            raise KeyError(f"Key '{key}' not found in table config file '{table_file}' for table name '{table_name}'")

        elem = table_dict[key]
        if not isinstance(elem, expected_type):
            raise TypeError(f"Invalid type for key '{key}' ({type(elem).__name__} != {expected_type.__name__}) in table"
                            f" config file '{table_file}' for table name '{table_name}'")

    return table_dict
