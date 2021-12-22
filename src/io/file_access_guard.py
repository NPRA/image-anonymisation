import time
import os
import numpy as np
import config
from src.Logger import LOGGER


class PathNotReachableError(Exception):
    """Error raised when one or more paths cannot be reached"""
    pass


def all_exists(paths, exists_func=os.path.exists):
    """
    Returns true if all elements of `paths` is a valid path.

    :param paths: Iterable where each element is a string of paths. The elements can also be `bytes`.
    :type paths: list of str | tuple of str | np.ndarray
    :param exists_func: Function which checks if the path exists. Default is `os.path.exists`.
    :type exists_func: function
    :return: True if all paths exists, False otherwise
    :rtype: bool
    """
    exists = True
    for path in paths:
        if isinstance(path, bytes):
            path = path.decode("utf-8")
        exists = (exists and exists_func(path))
    return exists


def wait_until_path_is_found(paths, retry_interval=config.file_access_retry_seconds,
                             timeout=config.file_access_timeout_seconds):
    """
    Blocks execution until all elements of `paths` are valid paths, for `timeout` seconds. If the timeout is reached,
    and one or more paths still do not exist, a `PathNotReachableError` will be raised.

    :param paths: Iterable where each element is a string of paths. The elements can also be `bytes`.
    :type paths: list of str | tuple of str | np.ndarray
    :param retry_interval: Number of seconds to wait between each retry.
    :type retry_interval: int
    :param timeout: Total number of seconds to wait.
    :type timeout: int
    :return: 0, if the existence of all paths is confirmed before the timeout is reached.
    :rtype: int
    """
    total_wait_time = 0

    if not isinstance(paths, (list, tuple, np.ndarray)):
        paths = [paths]

    while not all_exists(paths):
        time.sleep(retry_interval)
        total_wait_time += retry_interval
        if total_wait_time > timeout:
            raise PathNotReachableError(f"At least one of the paths in {paths} could not be reached in {timeout}s. "
                                        f"Aborting.")
        else:
            LOGGER.warning(__name__, f"At least one of the paths in {paths} could not be reached. Retrying.")
    return 0
