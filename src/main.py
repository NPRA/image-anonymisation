import os
import time
import logging
import argparse
import multiprocessing
from datetime import datetime, timedelta
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'
import tensorflow as tf

import config
from src.io.exif_util import exif_from_file
from src.io.save import save_processed_img, archive
from src.io.TreeWalker import TreeWalker
from src.io.tf_dataset import get_tf_dataset
from src.Masker import Masker
from src.Logger import LOGGER

# Exceptions to catch when processing an image
PROCESSING_EXCEPTIONS = (
    AssertionError,
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
    parser.add_argument("-l", "--log-file", dest="log_file", default=None,
                        help="Optional path to log file.")
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
    # Configure logger
    logging.basicConfig(level=logging.INFO, format=LOGGER.fmt)
    # Get arguments
    args = get_args()
    # Set log file
    if args.log_file is not None:
        LOGGER.set_log_file(args.log_file)
    # Check that the config and command line arguments are valid
    check_config(args)

    # Get the absolute path of the directories
    base_input_dir = os.path.abspath(args.input_folder)
    base_output_dir = os.path.abspath(args.output_folder)
    mirror_dirs = [base_output_dir]

    # Configure the logger
    LOGGER.base_input_dir = base_input_dir
    LOGGER.base_output_dir = base_output_dir

    if args.archive_folder is not None:
        # Add the archive folder to the list of mirror directories.
        mirror_dirs.append(os.path.abspath(args.archive_folder))

    # Initialize the walker
    tree_walker = TreeWalker(base_input_dir, mirror_dirs, skip_webp=(not config.force_remask),
                             precompute_paths=(not config.lazy_paths))
    # Initialize the masker
    masker = Masker()
    # Create the TensorFlow datatset
    dataset = get_tf_dataset(tree_walker)
    return args, tree_walker, masker, dataset


def process_image(img, image_path, masker, pool, export_result, archive_result, input_path, mirror_paths, filename):
    """
    Complete procedure for processing a single image.

    :param img: Input image
    :type img: tf.python.framework.ops.EagerTensor
    :param image_path: Full path to the image. Must end with '.jpg'.
    :type image_path: str
    :param masker: Instance of `Masker` to use for computing masks.
    :type masker: Masker
    :param pool: Processing pool for asynchronous export of results.
    :type pool: multiprocessing.Pool
    :param export_result: Result of previous export call to `pool.apply_async`. This is used to ensure that the previous
                          export is complete before a new one is started.
    :type export_result: multiprocessing.ApplyResult
    :param archive_result: Result of previous archive call to `pool.apply_async`. This is used to ensure that the
                           previous archiving is complete before a new one is started.
    :type archive_result: multiprocessing.ApplyResult
    :param input_path: Full path to directory of input image
    :type input_path: str
    :param mirror_paths: List with at least one element, containing the output path and optionally, the archive path.
    :type mirror_paths: list of str
    :param filename: Name of image file
    :type filename: str

    :return: Result from the current call to `pool.apply_async`
    :rtype: multiprocessing.ApplyResult
    """
    # Load image
    exif = exif_from_file(image_path)
    # Start masking
    mask_results = masker.mask(img, mask_dilation_pixels=config.mask_dilation_pixels)

    # Convert to numpy array for exporting
    img = img.numpy()
    # Make sure that the previous export is done before starting a new one.
    if export_result is not None:
        assert export_result.get() == 0
    # Save results
    export_result = pool.apply_async(
        save_processed_img,
        args=(img, mask_results, exif),
        kwds=dict(
            input_path=input_path, output_path=mirror_paths[0],
            filename=filename, draw_mask=config.draw_mask, local_json=config.local_json,
            remote_json=config.remote_json, local_mask=config.local_mask,
            remote_mask=config.remote_mask, mask_color=config.mask_color,
            blur=config.blur, gray_blur=config.gray_blur, normalized_gray_blur=config.normalized_gray_blur,
        )
    )

    if len(mirror_paths) > 1:
        # Do async. archiving
        os.makedirs(mirror_paths[1], exist_ok=True)
        if archive_result is not None:
            assert archive_result.get() == 0
        archive_result = pool.apply_async(
            archive,
            args=(input_path, mirror_paths, filename),
            kwds=dict(archive_json=config.archive_json, archive_mask=config.archive_mask,
                      delete_input_img=config.delete_input, assert_output_mask=True)
        )
    return export_result, archive_result


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
    est_done = (datetime.now() + timedelta(seconds=est_time_remaining)).strftime("%Y-%m-%d, %H:%M:%S")
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
    LOGGER.info(__name__, "")
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
    args, tree_walker, masker, dataset = initialize()
    n_imgs = "?" if config.lazy_paths else tree_walker.n_valid_images
    n_masked = 0

    # multiprocessing.Pool for asynchronous result export
    pool = multiprocessing.Pool(processes=1)
    export_result = archive_result = None

    dataset_iterator = iter(dataset)

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
            export_result, archive_result = process_image(img=img, image_path=image_path, masker=masker, pool=pool,
                                                          export_result=export_result, archive_result=archive_result,
                                                          input_path=input_path, mirror_paths=mirror_paths,
                                                          filename=filename)
        except PROCESSING_EXCEPTIONS as err:
            LOGGER.error(__name__, f"Got error '{str(err)}' while processing image {count_str}. File: "
                                   f"{image_path}.", save=True)
            continue

        n_masked += 1
        time_delta = "{:.3f}".format(time.time() - start_time)
        est_done = get_estimated_done(time_at_iter_start, n_imgs, n_masked)
        LOGGER.info(__name__, f"Masked image {count_str} in {time_delta} s. Estimated done: {est_done}. File: "
                              f"{image_path}.")

    # Summary
    log_summary(tree_walker, n_masked, start_datetime)
    # Close the processing pool
    pool.close()


if __name__ == '__main__':
    main()
