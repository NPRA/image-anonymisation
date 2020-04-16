import os
import time
import atexit
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


def run_test(get_args, get_config, get_tmp_data_dir, archive, config_params):
    """
    Actually run the test.

    :param get_args: Fixture-function which gets the command line arguments
    :type get_args: function
    :param get_config: Fixture-function which gets the config
    :type get_config: function
    :param get_tmp_data_dir: Fixture-function which sets up a temporary data directory
    :type get_tmp_data_dir: function
    :param config_params: Dictionary containing config parameters. These will override the defaults in
                        `tests.conftest.Config` and `config`.
    :type config_params: dict
    """
    # Setup a temporary directory
    tmp_dir = get_tmp_data_dir(subdirs=["real"])
    # Register an exit handler which removes the temporary directory
    atexit.register(rmtree, tmp_dir)

    # Is archiving enabled?
    if archive:
        archive_folder = os.path.join(tmp_dir, "arch")
    else:
        archive_folder = None

    # Get the command line arguments
    args = get_args(input_folder=os.path.join(tmp_dir, "real"), output_folder=os.path.join(tmp_dir, "out"),
                    archive_folder=archive_folder)
    # Get the configs
    cfg = get_config(**config_params)
    # Run main
    run_main(cfg, args)
    # Wait for the asynchronous export to complete
    time.sleep(3)
    # Check that all files were created/not created as expected
    check_files(tmp_dir, cfg, args)


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


def test_main(get_args, get_config, get_tmp_data_dir):
    """
    Run `src.main.main` without any additional file exports, and without asynchronous processing enabled. Check that
    files are created/not created as expected.
    """
    run_test(get_args, get_config, get_tmp_data_dir, archive=False, config_params=dict(
        enable_async=False, local_json=False, remote_json=False, local_mask=False, remote_mask=False
    ))


def test_main_async(get_args, get_config, get_tmp_data_dir):
    """
    Run `src.main.main` without any additional file exports, and with asynchronous processing enabled. Check that
    files are created/not created as expected.
    """
    run_test(get_args, get_config, get_tmp_data_dir, archive=False, config_params=dict(
        enable_async=True, local_json=False, remote_json=False, local_mask=False, remote_mask=False
    ))


def test_main_exports(get_args, get_config, get_tmp_data_dir):
    """
    Run `src.main.main` with all additional file exports, but without asynchronous processing enabled. Check that
    files are created/not created as expected.
    """
    run_test(get_args, get_config, get_tmp_data_dir, archive=True, config_params=dict(
        enable_async=False, local_json=True, remote_json=True, local_mask=True, remote_mask=True
    ))


def test_main_async_exports(get_args, get_config, get_tmp_data_dir):
    """
    Run `src.main.main` with all additional file exports, and with asynchronous processing enabled. Check that
    files are created/not created as expected.
    """
    run_test(get_args, get_config, get_tmp_data_dir, archive=True, config_params=dict(
        enable_async=True, local_json=True, remote_json=True, local_mask=True, remote_mask=True
    ))


