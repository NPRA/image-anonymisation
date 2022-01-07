import os
import sys
import time
import logging
import argparse
from datetime import datetime, timedelta
from socket import gethostname
import numpy as np

os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'
# os.environ['CUDA_VISIBLE_DEVICES'] = '-1'
import tensorflow as tf

import config
from src.io.TreeWalker import TreeWalker
from src.io.tf_dataset import get_tf_dataset
from src.io.file_checker import clear_cache
from src.Masker import Masker
from src.Logger import LOGGER, LOG_SEP, config_string, logger_excepthook
from src.ImageProcessor import ImageProcessor

# Exceptions to catch when processing an image
PROCESSING_EXCEPTIONS = (
    SystemError,
    tf.errors.InvalidArgumentError,
    tf.errors.UnknownError,
    tf.errors.NotFoundError,
)

if config.write_exif_to_db:
    from src.db.DatabaseClient import DatabaseError

    PROCESSING_EXCEPTIONS = (DatabaseError, *PROCESSING_EXCEPTIONS)


def get_args():
    """ Get the command-line arguments. """
    parser = argparse.ArgumentParser(description='Image anonymisation')
    parser.add_argument("-i", "--input-folder", dest="input_folder",
                        help="Base directory for input images.")
    parser.add_argument("-o", "--output-folder", dest="output_folder",
                        help="Base directory for masked (output) images and metadata files")
    parser.add_argument("-a", "--archive-folder", dest="archive_folder", default=None,
                        help="Optional base directory for archiving original images.")
    parser.add_argument("-l", "--log-folder", dest="log_folder", default=None,
                        help="Optional path to directory of log file. The log file will be named "
                             "<log\\folder>\\<timestamp> <hostname>.log")
    parser.add_argument("--skip-clear-cache", dest="clear_cache", action="store_false",
                        help="Disables the clearing of cahce files at startup.")
    parser.add_argument("-k", dest="config_file", default=None,
                        help=f"Path to custom configuration file. See the README for details. Default is "
                             f"{config.DEFAULT_CONFIG_FILE}")
    parser.add_argument("-p", "--preview_only", dest="preview_only", action="store_true",
                        help="Only create preview images of the input images. "
                             "The masking process will not be applied. Default: False")
    args = parser.parse_args()
    return args


def check_config(args):
    """ Check that the specified configuration variables are valid. """
    if config.archive_json and not config.remote_json:
        raise ValueError("Parameter 'archive_json' requires remote_json=True.")
    if (config.remote_preview or config.local_preview) and not config.preview_dim:
        raise ValueError("Parameter 'remote_preview' and 'local_preview' requires 'preview_dim'")
    if config.archive_preview and not config.remote_preview:
        raise ValueError("Parameter 'archive_preview' requires remote_preview=True.")

    # if config.archive_mask and not config.remote_mask:
    # raise ValueError("Parameter 'archive_mask' requires remote_mask=True.")

    if config.delete_input:
        LOGGER.warning(__name__, "Parameter 'delete_input' is enabled. This will permanently delete the original"
                                 " image from the input directory!")
        assert args.archive_folder, "Argument 'delete_input' requires a valid archive directory to be specified."

    if config.uncaught_exception_email or config.processing_error_email or config.finished_email:
        # Try to import the email_sender module, which checks if the `email_config.py` file is present.
        # Otherwise this will raise an exception prompting the user to create the file.
        import src.email_sender

    valid_log_levels = ["DEBUG", "INFO", "WARNING", "ERROR"]
    assert config.log_level in valid_log_levels, f"config.log_level must be one of {valid_log_levels}"


def set_excepthook(hooks):
    """
    Configure sys.excepthook to call all functions in `hooks` before calling the default excepthook.

    :param hooks: List of hooks. Each element must be a function with three arguments: Exception type, exception
                  instance, and traceback instance.
    :type hooks: list of function
    """

    def excepthook(etype, ex, tb):
        # Call hooks
        for hook in hooks:
            hook(etype, ex, tb)
        # Call the default excepthook.
        sys.__excepthook__(etype, ex, tb)

    # Register the custom hook
    sys.excepthook = excepthook


def initialize():
    """
    Get command line arguments, and initialize the TreeWalker and Masker.

    :return: Command line arguments, an instance of `TreeWalker` initialized at the specified directories, and an
             instance of `Masker` ready for masking.
    :rtype: argparse.Namespace, TreeWalker, Masker
    """
    # Register the logging excepthook
    except_hooks = [logger_excepthook]

    if config.uncaught_exception_email:
        # Register a custom excepthook which sends an email on uncaught exceptions.
        from src.email_sender import email_excepthook
        except_hooks.append(email_excepthook)

    # Set the exception hook(s)
    set_excepthook(except_hooks)

    # Get arguments
    args = get_args()
    # Check that the config and command line arguments are valid
    check_config(args)

    # Configure logger
    logging.basicConfig(level=getattr(logging, config.log_level), format=LOGGER.fmt, datefmt=LOGGER.datefmt)

    # Set log file
    if args.log_folder is not None:
        os.makedirs(args.log_folder, exist_ok=True)
        log_file_name = config.log_file_name.format(datetime=datetime.now().strftime("%Y-%m-%d_%H%M%S"),
                                                    hostname=gethostname())
        log_file = os.path.join(args.log_folder, log_file_name)
        LOGGER.set_log_file(log_file)

    # Log the call
    LOGGER.info(__name__, f"Call: {' '.join(sys.argv)}")
    # Log the current config.
    LOGGER.info(__name__, "\n" + config_string())

    if args.clear_cache:
        # Clear any cached files
        clear_cache()
        # Clear the database cache if database writing is enabled
        if config.write_exif_to_db:
            from src.db.DatabaseClient import clear_db_cache
            clear_db_cache()

    # Get the absolute path of the directories
    base_input_dir = os.path.abspath(args.input_folder)
    base_output_dir = os.path.abspath(args.output_folder)
    mirror_dirs = [base_output_dir]
    # Make the output directory
    os.makedirs(base_output_dir, exist_ok=True)

    if args.archive_folder is not None:
        base_archive_dir = os.path.abspath(args.archive_folder)
        mirror_dirs.append(base_archive_dir)
        # Make the archive directory
        os.makedirs(base_archive_dir, exist_ok=True)
    if config.separate_preview_directory:
        # Make the preview directory
        os.makedirs(config.separate_preview_directory, exist_ok=True)
    # Make the cache directory
    os.makedirs(config.CACHE_DIRECTORY, exist_ok=True)

    # Configure the logger
    LOGGER.base_input_dir = base_input_dir
    LOGGER.base_output_dir = base_output_dir

    # Initialize the walker
    tree_walker = TreeWalker(base_input_dir, mirror_dirs, skip_webp=(not config.force_remask),
                             precompute_paths=(not config.lazy_paths))
    # Initialize the masker
    masker = Masker(mask_dilation_pixels=config.mask_dilation_pixels, max_num_pixels=config.max_num_pixels)
    # Create the TensorFlow datatset
    dataset_iterator = iter(get_tf_dataset(tree_walker))
    # Initialize the ImageProcessor
    image_processor = ImageProcessor(masker=masker, max_num_async_workers=config.max_num_async_workers, old_exif_version=True)
    return args, tree_walker, image_processor, dataset_iterator


def get_estimated_done(time_at_iter_start, n_imgs, n_masked):
    """
    Get the estimated completion time for the program.

    :param time_at_iter_start: Time of iteration start
    :type time_at_iter_start: float
    :param n_imgs: Number of total images to process. If this is not an int or a float, a "?" will be returned.
    :type n_imgs: int | float | str
    :param n_masked: Number of completed images
    :type n_masked: int

    :return: String-formatted estimated time of completion
    :rtype: str
    """
    if not isinstance(n_imgs, (int, float)):
        return "?"
    time_since_start = time.time() - time_at_iter_start
    est_time_remaining = (time_since_start / n_masked) * (n_imgs - n_masked)
    est_done = (datetime.now() + timedelta(seconds=est_time_remaining)).strftime(config.datetime_format)
    return est_done


def get_summary(tree_walker, image_processor, start_datetime):
    """
    Log a summary of the masking process.

    :param tree_walker: `TreeWalker` instance used in masking.
    :type tree_walker: TreeWalker
    :param image_processor: `src.ImageProcessor.ImageProcessor` instance used when processing the images.
    :type image_processor: src.ImageProcessor.ImageProcessor
    :param start_datetime: Datetime object indicating when the program started.
    :type start_datetime: datetime.datetime
    """

    lines = [
        "Anonymisation finished.",
        f"Input folder: {tree_walker.input_folder}",
        f"Identified images: {tree_walker.n_valid_images + tree_walker.n_skipped_images}",
        f"Images skipped due to existing masks: {tree_walker.n_skipped_images}",
        f"Images skipped due to processing errors: {tree_walker.n_valid_images - image_processor.n_completed}",
        f"Masked images: {image_processor.n_completed}",
    ]
    if len(tree_walker.mirror_folders) > 1:
        lines.insert(2, f"Archive folder: {tree_walker.mirror_folders[1]}")
    if len(tree_walker.mirror_folders) > 0:
        lines.insert(2, f"Output folder: {tree_walker.mirror_folders[0]}")

    if image_processor.database_client is not None:
        cli = image_processor.database_client
        lines += [
            f"Row(s) inserted into the database: {cli.total_inserted}",
            f"Row(s) updated in the database: {cli.total_updated}",
            f"Row(s) failed to insert/update in the database: {cli.total_errors}",
        ]

    lines.append(f"Total time spent: {str(datetime.now() - start_datetime)}")
    summary = "\n".join(lines)
    return summary


def main():
    """Run the masking."""
    # Initialize
    start_datetime = datetime.now()
    args, tree_walker, image_processor, dataset_iterator = initialize()
    n_imgs = "?" if config.lazy_paths else (tree_walker.n_valid_images + tree_walker.n_skipped_images)

    # Mask images
    time_at_iter_start = time.time()
    for i, paths in enumerate(tree_walker.walk()):
        count_str = f"{tree_walker.n_skipped_images + i + 1} of {n_imgs}"
        start_time = time.time()
        LOGGER.set_state(paths)
        LOGGER.info(__name__, LOG_SEP)
        LOGGER.info(__name__, f"Iteration: {count_str}.")

        # Catch potential exceptions raised while processing the image
        try:
            # Get the image
            img = next(dataset_iterator)
            # Do preprocessing for cutouts
            if config.use_cutouts:
                LOGGER.debug(__name__, f"Using cutout-method")
                # Process image with cutout method
                image_processor.process_image_with_cutouts(img, paths)
            else:
                # Process image without the cutout method
                image_processor.process_image_without_cutouts(img, paths)
        except PROCESSING_EXCEPTIONS as err:
            error_msg = f"'{str(err)}'. File: {paths.input_file}"
            LOGGER.error(__name__, error_msg, save=True, email=True, email_mode="error")
            continue

        est_done = get_estimated_done(time_at_iter_start, n_imgs, i + 1)
        iter_time_delta = "{:.3f}".format(time.time() - start_time)
        LOGGER.info(__name__, f"Iteration finished in {iter_time_delta} s.")
        LOGGER.info(__name__, f"Estimated completion: {est_done}")

    # Close the image_processor. This will make sure that all exports are finished before we continue.
    LOGGER.info(__name__, LOG_SEP)
    LOGGER.info(__name__, f"Writing output files for the remaining images.")
    image_processor.close()

    # Summary
    summary_str = get_summary(tree_walker, image_processor, start_datetime)
    LOGGER.info(__name__, LOG_SEP)
    LOGGER.info(__name__, summary_str, email=True, email_mode="finished")


if __name__ == '__main__':
    main()
