import yaml

from .config import *
from .constants import *


def get_db_table_dict(table_name):
    """
    Parse the yaml-file corresponding to the table named `table_name`, and return the contents as a dictionary.

    :param table_name:
    :type table_name:
    :return:
    :rtype:
    """
    table_file = os.path.join(PROJECT_ROOT, "config", "db_tables", f"{table_name}.yml")
    if not os.path.isfile(table_file):
        raise FileNotFoundError(f"Table config file '{table_file}' not found for table name '{table_name}'.")

    with open(table_file, "r") as f:
        table_dict = yaml.safe_load(f)

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
