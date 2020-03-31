import os
import sys
import time
import logging
import argparse
from datetime import datetime, timedelta
from socket import gethostname
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'
# os.environ['CUDA_VISIBLE_DEVICES'] = '-1'
import tensorflow as tf

import config
from src.io.TreeWalker import TreeWalker
from src.io.tf_dataset import get_tf_dataset
from src.Masker import Masker
from src.Logger import LOGGER, config_string, email_excepthook
from src.ImageProcessor import ImageProcessor

# Exceptions to catch when processing an image
PROCESSING_EXCEPTIONS = (
    tf.errors.InvalidArgumentError,
    tf.errors.UnknownError,
    tf.errors.NotFoundError,
)


def get_args():
    """ Get the command-line arguments. """
    parser = argparse.ArgumentParser(description='Image anonymisation')
    parser.add_argument("-i", "--input-folder", dest="input_folder", help="Base directory for input images.")
    parser.add_argument("-o", "--output-folder", dest="output_folder",
                        help="Base directory for masked (output) images and metadata files")
    parser.add_argument("-a", "--archive-folder", dest="archive_folder", default=None,
                        help="Optional base directory for archiving original images.")
    parser.add_argument("-l", "--log-folder", dest="log_folder", default=None,
                        help="Optional path to directory of log file. The log file will be named "
                             "<log\\folder>\\<hostname>.log")
    args = parser.parse_args()
    return args


def check_config(args):
    """ Check that the specified configuration variables are valid. """
    if config.archive_json and not config.remote_json:
        raise ValueError("Parameter 'archive_json' requires remote_json=True.")
    if config.archive_mask and not config.remote_mask:
        raise ValueError("Parameter 'archive_mask' requires remote_mask=True.")

    if config.delete_input:
        LOGGER.warning(__name__, "Parameter 'delete_input' is enabled. This will permanently delete the original"
                                 " image from the input directory!")
        assert args.archive_folder, "Argument 'delete_input' requires a valid archive directory to be specified."


def initialize():
    """
    Get command line arguments, and initialize the TreeWalker and Masker.

    :return: Command line arguments, an instance of `TreeWalker` initialized at the specified directories, and an
             instance of `Masker` ready for masking.
    :rtype: argparse.Namespace, TreeWalker, Masker
    """
    # Register a custom excepthook which sends an email on uncaught exceptions.
    sys.excepthook = email_excepthook

    # Configure logger
    logging.basicConfig(level=logging.INFO, format=LOGGER.fmt, datefmt=LOGGER.datefmt)
    # Get arguments
    args = get_args()

    # Set log file
    if args.log_folder is not None:
        os.makedirs(args.log_folder, exist_ok=True)
        log_file_name = config.log_file_name.format(datetime=datetime.now().strftime(config.datetime_format),
                                                    hostname=gethostname())
        log_file = os.path.join(args.log_folder, log_file_name)
        LOGGER.set_log_file(log_file)

    # Log the current config.
    LOGGER.info(__name__, "\n" + config_string())

    # Check that the config and command line arguments are valid
    check_config(args)

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
    else:
        base_archive_dir = None

    # Configure the logger
    LOGGER.base_input_dir = base_input_dir
    LOGGER.base_output_dir = base_output_dir

    # Initialize the walker
    tree_walker = TreeWalker(base_input_dir, mirror_dirs, skip_webp=(not config.force_remask),
                             precompute_paths=(not config.lazy_paths))
    # Initialize the masker
    masker = Masker()
    # Create the TensorFlow datatset
    dataset_iterator = iter(get_tf_dataset(tree_walker))
    # Initialize the ImageProcessor
    image_processor = ImageProcessor(masker=masker, max_num_async_workers=1, base_input_path=base_input_dir,
                                     base_output_path=base_output_dir, base_archive_path=base_archive_dir)
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


def log_summary(tree_walker, n_masked, start_datetime):
    """
    Log a summary of the masking process.

    :param tree_walker: `TreeWalker` instance used in masking.
    :type tree_walker: TreeWalker
    :param n_masked: Number of masked images
    :type n_masked: int
    :param start_datetime: Datetime object indicating when the program started.
    :type start_datetime: datetime.datetime
    """
    LOGGER.info(__name__, "Anonymisation finished.")
    LOGGER.info(__name__, f"Number of identified images: "
                          f"{tree_walker.n_valid_images + tree_walker.n_skipped_images}")
    LOGGER.info(__name__, f"Number of masked images: {n_masked}")
    LOGGER.info(__name__, f"Number of images skipped due to existing masks: {tree_walker.n_skipped_images}")
    LOGGER.info(__name__, f"Number of images skipped due to errors: {tree_walker.n_valid_images - n_masked}")
    LOGGER.info(__name__, f"Total time spent: {str(datetime.now() - start_datetime)}")


def main():
    """Run the masking."""
    # Initialize
    start_datetime = datetime.now()
    args, tree_walker, image_processor, dataset_iterator = initialize()
    n_imgs = "?" if config.lazy_paths else tree_walker.n_valid_images
    n_masked = 0

    # Mask images
    time_at_iter_start = time.time()
    for i, (input_path, mirror_paths, filename) in enumerate(tree_walker.walk()):
        count_str = f"{i+1} of {n_imgs}"

        output_path = mirror_paths[0]
        image_path = os.path.join(input_path, filename)
        LOGGER.set_state(input_path, output_path, filename)
        start_time = time.time()

        # Catch potential exceptions raised while processing the image
        try:
            # Get the image
            img = next(dataset_iterator)
            # Do the processing
            image_processor.process_image(img, input_path, mirror_paths, filename)
        except PROCESSING_EXCEPTIONS as err:
            LOGGER.set_state(input_path, output_path, filename)
            LOGGER.error(__name__, f"Got error:\n'{str(err)}'\nwhile processing image {count_str}. File: "
                                   f"{image_path}.", save=True)
            continue

        # Check if the image_processor encountered a worker error. If an error was encountered, we reset the flag,
        # and silently continue without logging the "Masked image x/y..." message.
        if image_processor.got_worker_error:
            image_processor.got_worker_error = False
        else:
            n_masked += 1
            time_delta = "{:.3f}".format(time.time() - start_time)
            est_done = get_estimated_done(time_at_iter_start, n_imgs, i+1)
            LOGGER.info(__name__, f"Masked image {count_str} in {time_delta} s. Estimated done: {est_done}. File: "
                                  f"{image_path}.")
    image_processor.close()

    # Summary
    log_summary(tree_walker, n_masked, start_datetime)


if __name__ == '__main__':
    main()
