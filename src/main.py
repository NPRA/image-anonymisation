import os
import time
import logging
import argparse
from shutil import copy2

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


def check_config():
    """ Check that the specified configuration variables are valid. """
    if config.archive_json and not config.remote_json:
        raise ValueError("Argument '--archive-json' requires --remote-json.")
    if config.archive_mask and not config.remote_mask:
        raise ValueError("Argument '--archive-mask' requires --remote-mask.")

    if config.delete_input:
        LOGGER.warning(__name__, "Argument '--delete-input-image' is enabled. This will permanently delete the original"
                                 " image from the input directory!")
        assert config.archive_folder, "Argument '--delete-input-image' requires a valid archive directory to be " \
                                      "specified"


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
    input_jpg = _copy_file(input_path, mirror_paths[1], filename, ext=None)
    if archive_mask:
        _copy_file(mirror_paths[0], mirror_paths[1], filename, ext=".webp")
    if archive_json:
        _copy_file(mirror_paths[0], mirror_paths[1], filename, ext=".json")
    if delete_input_img:
        os.remove(input_jpg)


def main():
    """Run the masking."""
    logging.basicConfig(level=logging.INFO)
    check_config()
    args = get_args()

    base_input_dir = os.path.abspath(args.input_folder)
    base_output_dir = os.path.abspath(args.output_folder)
    LOGGER.base_input_dir = base_input_dir
    LOGGER.base_output_dir = base_output_dir

    mirror_dirs = [base_output_dir]
    if args.archive_folder is not None:
        mirror_dirs.append(os.path.abspath(args.archive_folder))

    tree_walker = TreeWalker(base_input_dir, mirror_dirs, skip_webp=(not config.force_remask),
                             precompute_paths=(not config.lazy_paths))
    masker = Masker()

    for input_path, mirror_paths, filename in tree_walker.walk():
        output_path = mirror_paths[0]
        image_path = os.path.join(input_path, filename)
        LOGGER.set_state(input_path, output_path, filename)

        # Load image
        try:
            img, exif = image_util.load_image(image_path, read_exif=True)
        except AssertionError as err:
            LOGGER.error(__name__, f"Got error '{str(err)}' while loading image {image_path}.", save=True)
            continue

        # Mask image
        try:
            start_time = time.time()
            mask_results = masker.mask(img)
        except AssertionError as err:
            LOGGER.error(__name__, f"Got error '{str(err)}' while masking image {image_path}.", save=True)
            continue

        # Save results
        try:
            image_util.save_processed_img(img, mask_results, exif, input_path=input_path, output_path=output_path,
                                          filename=filename, draw_mask=config.draw_mask, local_json=config.local_json,
                                          remote_json=config.remote_json, local_mask=config.local_mask,
                                          remote_mask=config.remote_mask, mask_color=config.mask_color,
                                          blur=config.blur)
        except AssertionError as err:
            LOGGER.error(__name__, f"Got error '{str(err)}' while exporting masked image {image_path}.", save=True)
            continue

        time_delta = round(time.time() - start_time, 3)
        LOGGER.info(__name__, f"Masked image {image_path} in {time_delta} s.")

        # Archive
        if args.archive_folder is not None:
            os.makedirs(mirror_paths[1], exist_ok=True)
            archive(input_path, mirror_paths, filename, archive_json=config.archive_json,
                    archive_mask=config.archive_mask, delete_input_img=config.delete_input)
            # LOGGER.info(__name__, f"Archived image {image_path}")


if __name__ == '__main__':
    main()
