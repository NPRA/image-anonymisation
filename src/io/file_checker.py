import os
import json

import config
from src.Logger import LOGGER
from src.io.file_access_guard import wait_until_path_is_found
from src.io.TreeWalker import Paths


def check_all_files_written(paths):
    """
    Check that all files for a given image have been saved correctly. The list of checked files is determined by the
    File I/O parameters in `config`. If all expected output files exist, the cache file will be deleted. If all expected
    output files exist, AND `config.delete_input` is True, the input image will be deleted as well.

    :param paths: Paths object representing the input image
    :type paths: src.io.TreeWalker.Paths
    :return: True if all expected files were found. False otherwise
    :rtype: bool
    """
    missing_files = find_missing_files(paths)
    if missing_files:
        _handle_missing_files(paths, missing_files)
        return False
    else:
        if config.delete_input:
            wait_until_path_is_found(paths.input_file)
            os.remove(paths.input_file)
            LOGGER.debug(__name__, f"Input file removed: {paths.input_file}")

        paths.remove_cache_file()
        LOGGER.info(__name__, f"All output files written for image: {paths.input_file}")
        return True


def find_missing_files(paths):
    """
    Find any missing files among the expected output files for the given image.

    :param paths: Paths object representing the input image
    :type paths: src.io.TreeWalker.Paths
    :return: List of missing output files
    :rtype: list of str
    """
    expected_files = get_expected_files(paths)

    wait_until_path_is_found([paths.base_input_dir, *paths.base_mirror_dirs])
    missing_files = []
    for file_path in expected_files:
        if not _file_is_ok(file_path):
            missing_files.append(file_path)

    return missing_files


def get_expected_files(paths):
    """
    Get a list of the output files we expect to find for the given image.

    :param paths: Paths object representing the input image
    :type paths: src.io.TreeWalker.Paths
    :return: List of expected input files
    :rtype: list of str
    """
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
    """
    Check that the given file is "OK". I.e. it exists.

    :param file_path: Full path to file
    :type file_path: str
    :param invert: Invert the check? (Check if the file does not exist instead)
    :type invert: bool
    :return: True if the file is ok, False otherwise
    :rtype: bool
    """
    file_exists = os.path.isfile(file_path)
    if invert:
        return not file_exists
    return file_exists


def _handle_missing_files(paths, missing_files):
    """
    Handle any missing files identified for a given image. This will log an error, which saves the error image, and
    sends an error-email, if email sending is enabled.

    :param paths: Paths object representing the input image
    :type paths: src.io.TreeWalker.Paths
    :param missing_files: List of missing files
    :type missing_files: list of str
    """
    current_logger_state = LOGGER.get_state()
    LOGGER.set_state(paths)
    LOGGER.error(__name__, f"Missing output files {missing_files} for image: {paths.input_file}", save=True,
                 email=True, email_mode="error")
    LOGGER.set_state(current_logger_state)


def clear_cache():
    """
    Clear the cache directory. Each JSON file in the cache directory is expected to represent an image for which the
    export process was aborted due to a critical error. This function will clear the output files written for the
    unfinished image, and then delete the cache file.
    """
    # Return if we couldn't find a cache directory. This probably means that this is the first time the application is
    # ran on this machine, so the cache directory has not been created yet
    if not os.path.exists(config.CACHE_DIRECTORY):
        return

    LOGGER.info(__name__, "Clearing cache files")
    count = 0
    for filename in os.listdir(config.CACHE_DIRECTORY):
        if filename.endswith(".json"):
            clear_cache_file(os.path.join(config.CACHE_DIRECTORY, filename))
            count += 1
    LOGGER.info(__name__, f"Found and cleared {count} cache file(s)")


def clear_cache_file(file_path):
    """
    Clear the output files for the unfinished image whose cahce file is located at `file_path`

    :param file_path: Path to cache file for unfinished image
    :type file_path: str
    """
    # Read the JSON file
    with open(file_path, "r") as f:
        cache_info = json.load(f)
    # Create a `src.io.TreeWalker.Paths` object representing the image
    paths = Paths(base_input_dir=cache_info["base_input_dir"], base_mirror_dirs=cache_info["base_mirror_dirs"],
                  input_dir=cache_info["input_dir"], mirror_dirs=cache_info["mirror_dirs"],
                  filename=cache_info["filename"])
    # Wait for the directories if they cannot be reached
    wait_until_path_is_found([paths.base_input_dir, *paths.base_mirror_dirs])
    # Remove any expected output files if they are present
    for expected_file in get_expected_files(paths):
        if os.path.isfile(expected_file):
            os.remove(expected_file)
            LOGGER.info(__name__, f"Removed file '{expected_file}' for unfinished image '{paths.input_file}'")
        else:
            LOGGER.debug(__name__, f"Could not find file '{expected_file}' for unfinished image '{paths.input_file}'")
    # Remove the cache file
    os.remove(file_path)