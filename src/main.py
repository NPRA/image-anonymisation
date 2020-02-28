import os
import time
import logging
import argparse
from shutil import copy2
from datetime import datetime, timedelta

import config
from src import image_util
from src.TreeWalker import TreeWalker
from src.Masker import Masker
from src.Logger import LOGGER


def get_args():
    """ Get the command-line arguments. """
    parser = argparse.ArgumentParser(description='Image anonymisation')
    parser.add_argument("-i", "--input-folder", dest="input_folder", help="Base directory for input images.")
    parser.add_argument("-o", "--output-folder", dest="output_folder",
                        help="Base directory for masked (output) images and metadata files")
    parser.add_argument("-a", "--archive-folder", dest="archive_folder", default=None,
                        help="Base directory for archiving original images.")
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


def _copy_file(source_path, destination_path, filename, ext=None):
    if ext is not None:
        filename = os.path.splitext(filename)[0] + ext

    source_file = os.path.join(source_path, filename)
    destination_file = os.path.join(destination_path, filename)

    if os.path.exists(destination_file):
        LOGGER.warning(__name__, f"Archive file {destination_file} already exists. The existing file will be "
                                 f"overwritten.")

    copy2(source_file, destination_file)
    return source_file


def archive(input_path, mirror_paths, filename, archive_mask=False, archive_json=False, delete_input_img=False):
    """
    Copy the input image file (and possibly some output files) to the archive directory.

    :param input_path: Path to the directory containing the input image.
    :type input_path: str
    :param mirror_paths: List with at least two elements, containing the output path and the archive path.
    :type mirror_paths: list of str
    :param filename: Name of image-file
    :type filename: str
    :param archive_mask: Copy the mask file to the archive directory?
    :type archive_mask: bool
    :param archive_json: Copy the EXIF file to the archive directory?
    :type archive_json: bool
    :param delete_input_img: Delete the image from the input directory?
    :type delete_input_img: bool
    """
    input_jpg = _copy_file(input_path, mirror_paths[1], filename, ext=None)
    if archive_mask:
        _copy_file(mirror_paths[0], mirror_paths[1], filename, ext=".webp")
    if archive_json:
        _copy_file(mirror_paths[0], mirror_paths[1], filename, ext=".json")
    if delete_input_img:
        os.remove(input_jpg)


def main():
    """Run the masking."""
    start_datetime = datetime.now()
    # Configure logger
    logging.basicConfig(level=logging.INFO, format="(%(levelname)s): %(message)s")
    # Get arguments
    args = get_args()
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
    n_imgs = "?" if config.lazy_paths else tree_walker.n_valid_images
    n_masked = 0

    # Initialize the masker
    masker = Masker()
    # Mask images
    time_at_iter_start = time.time()
    for i, (input_path, mirror_paths, filename) in enumerate(tree_walker.walk()):
        output_path = mirror_paths[0]
        image_path = os.path.join(input_path, filename)
        LOGGER.set_state(input_path, output_path, filename)
        count_str = f"{i+1} of {n_imgs}"

        try:
            # Load image
            img, exif = image_util.load_image(image_path, read_exif=True)
            # Start masking
            start_time = time.time()
            mask_results = masker.mask(img)
            # Save results
            image_util.save_processed_img(img, mask_results, exif, input_path=input_path, output_path=output_path,
                                          filename=filename, draw_mask=config.draw_mask, local_json=config.local_json,
                                          remote_json=config.remote_json, local_mask=config.local_mask,
                                          remote_mask=config.remote_mask, mask_color=config.mask_color,
                                          blur=config.blur)
        # Catch any AssertionErrors encountered while processing the image.
        except AssertionError as err:
            LOGGER.error(__name__, f"Got error '{str(err)}' while processing image {count_str}. File: "
                                   f"{image_path}.", save=True)
            continue

        n_masked += 1
        time_delta = "{:.3f}".format(time.time() - start_time)
        if not config.lazy_paths:
            time_since_start = time.time() - time_at_iter_start
            est_time_remaining = (time_since_start / n_masked) * (n_imgs - n_masked)
            est_done = (datetime.now() + timedelta(seconds=est_time_remaining)).strftime("%Y-%m-%d, %H:%M:%S")
        else:
            est_done = "?"

        LOGGER.info(__name__, f"Masked image {count_str} in {time_delta} s. Estimated done: {est_done}. File: {image_path}.")

        # Archive
        if args.archive_folder is not None:
            os.makedirs(mirror_paths[1], exist_ok=True)
            archive(input_path, mirror_paths, filename, archive_json=config.archive_json,
                    archive_mask=config.archive_mask, delete_input_img=config.delete_input)

    # Summary
    LOGGER.info(__name__, "")
    LOGGER.info(__name__, f"Number of identified images: "
                          f"{tree_walker.n_valid_images + tree_walker.n_skipped_images}")
    LOGGER.info(__name__, f"Number of masked images: {n_masked}")
    LOGGER.info(__name__, f"Number of images skipped due to existing masks: {tree_walker.n_skipped_images}")
    LOGGER.info(__name__, f"Number of images skipped due to errors: {tree_walker.n_valid_images - n_masked}")
    LOGGER.info(__name__, f"Total time spent: {str(datetime.now() - start_datetime)}")


if __name__ == '__main__':
    main()
