import os
import time
import logging
import argparse
from shutil import copy2

from src import image_util
from src.TreeWalker_v2 import TreeWalker
from src.Masker import Masker
from src.Logger import LOGGER


def get_args():
    """
    Parse command line arguments.

    :return: Parsed arguments
    :rtype: argparse.ArgumentParser
    """
    parser = argparse.ArgumentParser(description='Image anonymisation')

    parser.add_argument("-i", "--input-folder", dest="input_folder", help="Base directory for input images.")

    parser.add_argument("-o", "--output-folder", dest="output_folder",
                        help="Base directory for masked (output) images and metadata files")

    parser.add_argument("-a", "--archive-folder", dest="archive_folder", default=None,
                        help="Base directory for archiving original images.")

    parser.add_argument("-m", "--draw-mask", action="store_true", dest="draw_mask",
                        help="Apply the mask to the image file?")

    parser.add_argument("-rj", "--remote-json", action="store_true", dest="remote_json",
                        help="Write the EXIF .json file to the output (remote) directory?")

    parser.add_argument("-lj", "--local-json", action="store_true", dest="local_json",
                        help="Write the EXIF .json file to the input (local) directory?")

    parser.add_argument("-rm", "--remote-mask", action="store_true", dest="remote_mask",
                        help="Write mask file to the output (remote) directory?")

    parser.add_argument("-lm", "--local-mask", action="store_true", dest="local_mask",
                        help="Write the mask file to the input (local) directory?")

    parser.add_argument("-aj", "--archive-json", action="store_true", dest="archive_json",
                        help="Write the EXIF .json file to the archive directory?")

    parser.add_argument("-am", "--archive-mask", action="store_true", dest="archive_mask",
                        help="Write mask file to the archive directory?")

    parser.add_argument("--delete-input-image", action="store_true", dest="delete_input",
                        help="Delete the original image from the input directory when the masking is completed?")

    parser.add_argument("--force-remasking", action="store_true", dest="force_remask",
                        help="When this flag is set, the masks will be recomputed even though the .webp file exists.")

    parser.add_argument("--lazy-paths", action="store_true", dest="lazy_paths",
                        help="When this flag is set, the file tree will be traversed during the masking process. "
                             "Otherwise, all paths will be identified and stored before the masking starts")

    parser.add_argument("--mask-color", dest="mask_color", default=None, nargs=3, type=int,
                        help="RGB tuple [0-255] indicating the masking color. Setting this option will override the "
                             "colors in config.py.")

    parser.add_argument("--blur", dest="blur", default=None, type=int,
                        help="Blurring coefficient [1-100] which specifies the degree of blurring to apply within the "
                             "mask. When this parameter is specified, the image will be blurred, and not masked with a "
                             "specific color.")

    args = parser.parse_args()

    if args.archive_json and not args.remote_json:
        raise ValueError("Argument '--archive-json' requires --remote-json.")
    if args.archive_mask and not args.remote_mask:
        raise ValueError("Argument '--archive-mask' requires --remote-mask.")

    if args.delete_input:
        LOGGER.warning(__name__, "Argument '--delete-input-image' is enabled. This will permanently delete the original"
                                 " image from the input directory!")
        assert args.archive_folder, "Argument '--delete-input-image' requires a valid archive directory to be specified"
    return args


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
    args = get_args()

    base_input_dir = os.path.abspath(args.input_folder)
    base_output_dir = os.path.abspath(args.output_folder)
    LOGGER.base_input_dir = base_input_dir
    LOGGER.base_output_dir = base_output_dir

    mirror_dirs = [base_output_dir]
    if args.archive_folder is not None:
        mirror_dirs.append(os.path.abspath(args.archive_folder))

    tree_walker = TreeWalker(base_input_dir, mirror_dirs, skip_webp=(not args.force_remask),
                             precompute_paths=(not args.lazy_paths))
    masker = Masker()

    for input_path, mirror_paths, filename in tree_walker.walk():
        output_path = mirror_paths[0]
        LOGGER.set_state(input_path, output_path, filename)

        image_path = os.path.join(input_path, filename)
        img = image_util.load_image(image_path, read_exif=True)
        if img is None:
            continue
        img, exif = img

        start_time = time.time()
        try:
            mask_results = masker.mask(img)
        except AssertionError as err:
            LOGGER.error(__name__, f"Got error '{str(err)}' while processing image {image_path}.", save=True)
            continue

        image_util.save_processed_img(img, mask_results, exif, input_path=input_path, output_path=output_path,
                                      filename=filename, draw_mask=args.draw_mask, local_json=args.local_json,
                                      remote_json=args.remote_json, local_mask=args.local_mask,
                                      remote_mask=args.remote_mask, mask_color=args.mask_color, blur=args.blur)

        time_delta = round(time.time() - start_time, 3)
        LOGGER.info(__name__, f"Masked image {image_path} in {time_delta} s.")

        if args.archive_folder is not None:
            os.makedirs(mirror_paths[1], exist_ok=True)
            archive(input_path, mirror_paths, filename, archive_json=args.archive_json, archive_mask=args.archive_mask,
                    delete_input_img=args.delete_input)
            # LOGGER.info(__name__, f"Archived image {image_path}")



if __name__ == '__main__':
    main()
