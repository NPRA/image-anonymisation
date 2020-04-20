import os


def check_file_exists(path, filename=None, ext=None, invert=False):
    """
    Assert that the given file exists.

    :param path: Path to directory containing the file.
    :type path: str
    :param filename: Name of file (with extension)
    :type filename: str
    :param ext: Optional extension to use instead of the extension in `filename`
    :type ext: str
    :param invert: Invert the assertion? (Default = False).
    :type invert: bool
    """
    if filename is not None:
        file_path = os.path.join(path, filename)
    else:
        file_path = path

    if ext is not None:
        file_path = os.path.splitext(file_path)[0] + ext

    is_file = os.path.isfile(file_path)
    if not invert:
        assert is_file, f"Expected to find file '{file_path}'"
    else:
        assert not is_file, f"Expected to NOT find file '{file_path}'"