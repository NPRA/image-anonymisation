import os
import json

import config
from src.Logger import LOGGER
from src.io.file_access_guard import wait_until_path_is_found
from src.io.TreeWalker import Paths


def check_all_files_written(paths):
    missing_files = find_missing_files(paths)
    if missing_files:
        _handle_missing_files(paths, missing_files)
    else:
        if config.delete_input:
            wait_until_path_is_found(paths.input_file)
            os.remove(paths.input_file)
            LOGGER.debug(__name__, f"Input file removed: {paths.input_file}")

        paths.remove_cache_file()
        LOGGER.info(__name__, f"All output files written for image: {paths.input_file}")


def find_missing_files(paths):
    expected_files = get_expected_files(paths)

    wait_until_path_is_found([paths.base_input_dir, *paths.base_mirror_dirs])
    missing_files = []
    for file_path in expected_files:
        if not _file_is_ok(file_path):
            missing_files.append(file_path)

    return missing_files


def get_expected_files(paths):
    expected_files = [paths.output_file]

    if config.local_json:
        expected_files.append(paths.input_json)
    if config.remote_json:
        expected_files.append(paths.output_json)

    if config.local_mask:
        expected_files.append(paths.input_webp)
    if config.remote_mask:
        expected_files.append(paths.output_webp)

    if paths.archive_dir is not None:
        expected_files.append(paths.archive_file)
        if config.archive_json:
            expected_files.append(paths.archive_json)
        if config.archive_mask:
            expected_files.append(paths.archive_webp)

    return expected_files


def _file_is_ok(file_path, invert=False):
    file_exists = os.path.isfile(file_path)
    if invert:
        return not file_exists
    return file_exists


def _handle_missing_files(paths, missing_files):
    current_logger_state = LOGGER.get_state()
    LOGGER.set_state(paths)
    LOGGER.error(__name__, f"Missing output files {missing_files} for image: {paths.input_file}", save=True,
                 email=True, email_mode="error")
    LOGGER.set_state(current_logger_state)


def clear_cache():
    LOGGER.info(__name__, "Clearing cache files")
    count = 0
    for filename in os.listdir(config.CACHE_DIRECTORY):
        if filename.endswith(".json"):
            clear_cache_file(os.path.join(config.CACHE_DIRECTORY, filename))
            count += 1
    LOGGER.info(__name__, f"Found and cleared {count} cache file(s)")


def clear_cache_file(file_path):
    with open(file_path, "r") as f:
        cache_info = json.load(f)

    paths = Paths(base_input_dir=cache_info["base_input_dir"], base_mirror_dirs=cache_info["base_mirror_dirs"],
                  input_dir=cache_info["input_dir"], mirror_dirs=cache_info["mirror_dirs"],
                  filename=cache_info["filename"])

    wait_until_path_is_found([paths.base_input_dir, *paths.base_mirror_dirs])

    for expected_file in get_expected_files(paths):
        if os.path.isfile(expected_file):
            os.remove(expected_file)
            LOGGER.info(__name__, f"Removed file '{expected_file}' for unfinished image '{paths.input_file}'")
        else:
            LOGGER.debug(__name__, f"Could not find file '{expected_file}' for unfinished image '{paths.input_file}'")

    # Remove the cache file
    os.remove(file_path)
