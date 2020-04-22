import os
import pytest
import atexit
from shutil import copytree, rmtree
from uuid import uuid4

import config as original_config


MARKERS = ["slow", "db"]


def pytest_addoption(parser):
    for marker in MARKERS:
        parser.addoption(f"--run-{marker}", action="store_true", default=False, help=f"Run {marker} tests")


def pytest_configure(config):
    for marker in MARKERS:
        config.addinivalue_line("markers", f"{marker}: mark test as type {marker}")


def pytest_collection_modifyitems(config, items):
    for marker in MARKERS:
        if config.getoption(f"--run-{marker}"):
            return
        skip = pytest.mark.skip(reason=f"need --run-{marker} option to run")
        for item in items:
            if marker in item.keywords:
                item.add_marker(skip)


class Config:
    EXCLUDED_NAMES = ["os"]
    DEFAULTS = {
        "draw_mask": True,
        "remote_json": False,
        "local_json": False,
        "remote_mask": False,
        "local_mask": False,
        "archive_json": False,
        "archive_mask": False,
        "delete_input": False,
        "force_remask": False,
        "lazy_paths": False,
        "file_access_retry_seconds": 2,
        "file_access_timeout_seconds": 6,
        "uncaught_exception_email": False,
        "processing_error_email": False,
        "finished_email": False,
        "write_exif_to_db": False,
        "db_max_n_accumulated_rows": 1,
        "max_num_async_workers": 1,
    }

    def __init__(self, **kwargs):
        config_keys = [key for key in original_config.__dict__.keys()
                       if (not key.startswith("_")) and (key not in Config.EXCLUDED_NAMES)]

        for key in config_keys:
            value = kwargs.get(key, Config.DEFAULTS.get(key, original_config.__dict__.get(key)))
            setattr(self, key, value)


@pytest.fixture
def get_config():
    return Config


class Args:
    KEYS = ["input_folder", "output_folder", "archive_folder", "log_folder", "clear_cache"]
    
    def __init__(self, **kwargs):
        for key in Args.KEYS:
            setattr(self, key, kwargs.get(key, None))

    def __call__(self):
        return self


@pytest.fixture
def get_args():
    return Args


@pytest.fixture
def get_tmp_data_dir():
    def _get_tmp_data_dir(subdirs=tuple(), remove_on_exit=True):
        tests_root = os.path.dirname(os.path.realpath(__file__))
        tmp_dir_name = f"tmp_{uuid4()}"
        tmp_dir = os.path.join(tests_root, tmp_dir_name)
        os.makedirs(tmp_dir)

        for subdir_name in subdirs:
            src_dir = os.path.join(tests_root, "data", subdir_name)
            dest_dir = os.path.join(tmp_dir, subdir_name)
            copytree(src_dir, dest_dir)

        if remove_on_exit:
            atexit.register(rmtree, tmp_dir)

        return tmp_dir
    return _get_tmp_data_dir
