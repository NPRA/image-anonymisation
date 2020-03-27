import os
import time
from shutil import rmtree, copytree
from socket import gethostname
from unittest import mock
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'
import tensorflow as tf

from src.main import main
import config

# Path to the testing data
DATA_DIR = os.path.join(config.PROJECT_ROOT, "tests", "data")
RAW_INPUT_DIR = os.path.join(DATA_DIR, "real")
# Temporary paths to use in testing
TMP_DIR = os.path.join(DATA_DIR, "tmp")
INPUT_DIR = os.path.join(TMP_DIR, "in")
OUTPUT_DIR = os.path.join(TMP_DIR, "out")
ARCHIVE_DIR = os.path.join(TMP_DIR, "arch")
# Logging is disabled since it causes a PermissionError in cleanup
LOG_DIR = None

# Configuration variables and default values
CONFIG_VARS = {
    "draw_mask": True,
    "remote_json": True,
    "local_json": False,
    "remote_mask": True,
    "local_mask": False,
    "archive_json": False,
    "archive_mask": False,
    "delete_input": False,
    "force_remask": False,
    "lazy_paths": False,
    "mask_color": None,
    "mask_dilation_pixels": 0,
    "blur": None,
    "gray_blur": True,
    "normalized_gray_blur": True,
    "TF_DATASET_NUM_PARALLEL_CALLS": 1,
    "MODEL_NAME": config.MODEL_NAME,
    "PROJECT_ROOT": config.PROJECT_ROOT,
    "GRAPH_DIRECTORY": config.GRAPH_DIRECTORY,
    "MODEL_PATH": config.MODEL_PATH,
    "DOWNLOAD_BASE": config.DOWNLOAD_BASE,
}
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


class FakeArgs:
    """
    Class used to mock the command line arguments

    :param input_folder: Path to base input folder
    :type input_folder: str
    :param output_folder: Path to base output folder
    :type output_folder: str
    :param archive_folder: Path to base archive folder. None disables archiving
    :type archive_folder: str | None
    :param log_folder: Path to base log folder. None disables file-logging
    :type log_folder: str | None
    """
    def __init__(self, input_folder=INPUT_DIR, output_folder=OUTPUT_DIR, archive_folder=ARCHIVE_DIR,
                 log_folder=LOG_DIR):
        self.input_folder = input_folder
        self.output_folder = output_folder
        self.archive_folder = archive_folder
        self.log_folder = log_folder

    def __call__(self):
        return self


class FakeConfig:
    """
    Class used to mock the configuration variables in `config`. Only variables present in `CONFIG_VARS` are supported.
    Deafult values will be retrieved from `CONFIG_VARS`.

    :param **kwargs: Configuration variables. Overrides the defaults set in `CONFIG_VARS`.
    :type kwargs:
    """
    def __init__(self, **kwargs):
        for key in CONFIG_VARS.keys():
            setattr(self, key, kwargs.get(key, CONFIG_VARS[key]))


# The multiprocessing.Pool.apply_async call has to be mocked, since mocking does not work "inside" the call to
# pool.apply_async. The config module is therefore not correctly mocked for asynchronously applied functions.
def fake_apply_async(pool, func, args, kwds={}):
    result = func(*args, **kwds)
    return FakeAsyncResults(result)


class FakeAsyncResults:
    def __init__(self, result):
        self.result = result

    def get(self):
        return self.result


def _run_main(new_config, new_args):
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
        mock.patch("src.ImageProcessor.multiprocessing.pool.Pool.apply_async", new=fake_apply_async),
        mock.patch("src.Masker.config", new=new_config),
        mock.patch("src.main.get_args", new=new_args),
    ]
    for m in mockers:
        m.start()
    main()
    for m in mockers:
        m.stop()


def _check_file_exists(path, filename, ext=None, invert=False):
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
    if ext is not None:
        filename = os.path.splitext(filename)[0] + ext

    file_path = os.path.join(path, filename)
    is_file = os.path.isfile(file_path)
    if not invert:
        assert is_file, f"Expected to find file '{file_path}'"
    else:
        assert not is_file, f"Expected to NOT find file '{file_path}'"


def _check_files(cfg, args):
    """
    Check that we find/don't find all expected files.

    :param cfg: Config object
    :type cfg: FakeConfig
    :param args: Command line arguments object
    :type args: FakeArgs
    """
    no_archive = args.archive_folder is None

    if args.log_folder is not None:
        assert os.listdir(LOG_DIR), f"LOG_DIR ({LOG_DIR}) is empty."

    for rel_path, filename in EXPECTED_PROCESSED_FILES:
        input_path = os.path.join(INPUT_DIR, rel_path)
        output_path = os.path.join(OUTPUT_DIR, rel_path)
        archive_path = os.path.join(ARCHIVE_DIR, rel_path)

        assert os.path.isdir(output_path)
        _check_file_exists(output_path, filename)
        _check_file_exists(input_path, filename, invert=cfg.delete_input)
        _check_file_exists(archive_path, filename, invert=no_archive)
        _check_file_exists(input_path, filename, ext=".json", invert=not cfg.local_json)
        _check_file_exists(output_path, filename, ext=".json", invert=not cfg.remote_json)
        _check_file_exists(input_path, filename, ext=".webp", invert=not cfg.local_mask)
        _check_file_exists(output_path, filename, ext=".webp", invert=not cfg.remote_mask)

    for rel_path, filename in EXPECTED_ERROR_FILES:
        if rel_path:
            error_path = os.path.join(OUTPUT_DIR + "_error", rel_path + "_error")
        else:
            error_path = OUTPUT_DIR + "_error"
        _check_file_exists(error_path, filename)


def _setup_directories():
    if os.path.isdir(TMP_DIR):
        rmtree(TMP_DIR)
    os.makedirs(TMP_DIR)
    copytree(RAW_INPUT_DIR, INPUT_DIR)


def _clean_directories():
    rmtree(TMP_DIR)


def test_main_all_exports_enabled():
    """
    Run `src.main.main` with all file-exports enabled, and check that files are created as expected.
    """
    _setup_directories()
    args = FakeArgs()
    cfg = FakeConfig(delete_input=False, local_json=True, remote_json=True, local_mask=True, remote_mask=True)
    _run_main(cfg, args)
    # Wait for the asynchronous export to complete
    time.sleep(3)
    _check_files(cfg, args)
    _clean_directories()


def test_main_all_exports_disabled():
    """
    Run `src.main.main` with all file-exports disabled, and check that files are created/not created as expected.
    """
    _setup_directories()
    args = FakeArgs(archive_folder=None, log_folder=None)
    cfg = FakeConfig(delete_input=False, local_json=False, remote_json=False, local_mask=False, remote_mask=False)
    _run_main(cfg, args)
    # Wait for the asynchronous export to complete
    time.sleep(3)
    _check_files(cfg, args)
    _clean_directories()