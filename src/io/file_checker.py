import os

import config
from src.Logger import LOGGER
from src.io.file_access_guard import wait_until_path_is_found


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

    wait_paths = [paths.base_input_dir, paths.base_output_dir]
    if paths.base_archive_dir:
        wait_paths.append(paths.base_archive_dir)
    wait_until_path_is_found(wait_paths)

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