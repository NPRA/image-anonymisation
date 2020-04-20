import os
import time
import atexit
import pytest
from shutil import rmtree
from unittest import mock
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'
import tensorflow as tf

from src.main import main
from tests.helpers import check_file_exists


# List of files expected to be processed when `src.main.main` finishes
EXPECTED_PROCESSED_FILES = [
    ("", "Fy50_Rv003_hp01_f1_m01237.jpg"),
    ("", "Fy50_Rv003_hp01_f1_m01247.jpg"),
    ("", "Fy50_Rv003_hp01_f1_m01267.jpg"),
    ("", "Fy50_Rv003_hp01_f1_m01277.jpg"),
    ("bar", "Fy50_Rv003_hp01_f1_m00114.jpg"),
    ("bar", "Fy50_Rv003_hp01_f1_m00124.jpg"),
    ("bar", "Fy50_Rv003_hp01_f1_m00134.jpg"),
    ("bar", "Fy50_Rv003_hp01_f1_m01176.jpg"),
    ("bar", "Fy50_Rv003_hp01_f1_m01186.jpg"),
    ("bar", "Fy50_Rv003_hp01_f1_m01197.jpg"),
    ("bar", "Fy50_Rv003_hp01_f1_m01206.jpg"),
    ("bar", "Fy50_Rv003_hp01_f1_m01227.jpg"),
    ("foo", "Fy08_Fv034_hp01_f1_m00028.jpg"),
    ("foo", "Fy08_Fv034_hp01_f1_m00048.jpg"),
    ("foo", "Fy08_Fv034_hp01_f1_m00088.jpg"),
    ("foo", "Fy08_Fv034_hp01_f1_m00108.jpg"),
    ("foo", "Fy08_Fv034_hp01_f1_m00128.jpg"),
    ("foo", "Fy08_Fv034_hp01_f1_m00148.jpg"),
    ("foo", "Fy08_Fv034_hp01_f1_m00168.jpg"),
    ("foo", "Fy08_Fv034_hp01_f1_m00188.jpg"),
]
# List of files expected to raise errors during processing
EXPECTED_ERROR_FILES = [
    ("", "corrupted.jpg"),
    ("foo", "corrupted.jpg"),
]


@pytest.mark.parametrize("enable_exports,enable_async", [
    (True, True),
    (True, False),
    (False, True),
    (False, False)
])
def test_main(get_args, get_config, get_tmp_data_dir, enable_exports, enable_async):
    """
    End-to-end test for the `src.main.main` function.

    :param get_args: Fixture-function which gets the command line arguments
    :type get_args: function
    :param get_config: Fixture-function which gets the config
    :type get_config: function
    :param get_tmp_data_dir: Fixture-function which sets up a temporary data directory
    :type get_tmp_data_dir: function
    :param enable_exports: Enable saving of extra output files (mask, json, and archive)
    :type enable_exports: bool
    :param enable_async: Enable asynchronous processing
    :type enable_async: bool
    """
    # Setup a temporary directory
    tmp_dir = get_tmp_data_dir(subdirs=["real"])
    # Register an exit handler which removes the temporary directory
    atexit.register(rmtree, tmp_dir)

    # Booleans for archiving and output file saving.
    archive = enable_exports
    config_params = dict(local_json=enable_exports, remote_json=enable_exports, local_mask=enable_exports,
                         remote_mask=enable_exports)

    # Set the archive folder
    if archive:
        archive_folder = os.path.join(tmp_dir, "arch")
    else:
        archive_folder = None

    # Get the command line arguments
    args = get_args(input_folder=os.path.join(tmp_dir, "real"), output_folder=os.path.join(tmp_dir, "out"),
                    archive_folder=archive_folder, clear_cache=True)
    # Get the config
    cfg = get_config(CACHE_DIRECTORY=os.path.join(tmp_dir, "_cache"), **config_params)
    # Run main
    run_main(cfg, args)
    # Wait for the asynchronous export to complete
    time.sleep(3)
    # Check that all files were created/not created as expected
    check_files(tmp_dir, cfg, args)


def run_main(new_config, new_args):
    """
    Run `src.main.main` while mocking the command line arguments and the config.

    :param new_config: Configuration object
    :type new_config: FakeConfig
    :param new_args: Command line arguments
    :type new_args: FakeArgs
    """
    tf.keras.backend.clear_session()
    mockers = [
        mock.patch("src.main.config", new=new_config),
        mock.patch("src.ImageProcessor.config", new=new_config),
        mock.patch("src.Masker.config", new=new_config),
        mock.patch("src.main.get_args", new=new_args),
        mock.patch("src.Workers.config", new=new_config)
    ]
    for m in mockers: m.start()
    main()
    for m in mockers: m.stop()


def check_files(tmp_dir, cfg, args):
    """
    Check that we find/don't find all expected files.

    :param tmp_dir: Base temporary directory
    :type tmp_dir: str
    :param cfg: Config object
    :type cfg: FakeConfig
    :param args: Command line arguments object
    :type args: FakeArgs
    """
    no_archive = args.archive_folder is None

    for rel_path, filename in EXPECTED_PROCESSED_FILES:
        input_path = os.path.join(tmp_dir, "real", rel_path)
        output_path = os.path.join(tmp_dir, "out", rel_path)
        archive_path = os.path.join(tmp_dir, "arch", rel_path)

        assert os.path.isdir(output_path)
        check_file_exists(output_path, filename)
        check_file_exists(input_path, filename, invert=cfg.delete_input)
        check_file_exists(archive_path, filename, invert=no_archive)
        check_file_exists(input_path, filename, ext=".json", invert=not cfg.local_json)
        check_file_exists(output_path, filename, ext=".json", invert=not cfg.remote_json)
        check_file_exists(input_path, filename, ext=".webp", invert=not cfg.local_mask)
        check_file_exists(output_path, filename, ext=".webp", invert=not cfg.remote_mask)

    for rel_path, filename in EXPECTED_ERROR_FILES:
        error_path = os.path.join(tmp_dir, "out_error", rel_path)
        check_file_exists(error_path, filename)
