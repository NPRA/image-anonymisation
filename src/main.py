import os
import time
import logging
import argparse

from src import image_util
from src.TreeWalker import TreeWalker
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

    parser.add_argument("--force-remasking", action="store_true", dest="force_remask",
                        help="When this flag is set, the masks will be recomputed even though the .webp file exists.")

    parser.add_argument("--lazy-paths", action="store_true", dest="lazy_paths",
                        help="When this flag is set, the file tree will be traversed during the masking process. "
                             "Otherwise, all paths will be identified and stored before the masking starts")

    parser.add_argument("--mask-color", dest="mask_color", default=None, nargs=3, type=int,
                        help="RGB tuple [0-255] indicating the masking color. Setting this option will override the "
                             "colors in config.py.")

    args = parser.parse_args()
    return args


def main():
    """Run the masking."""
    logging.basicConfig(level=logging.INFO)
    args = get_args()

    base_input_dir = os.path.abspath(args.input_folder)
    base_output_dir = os.path.abspath(args.output_folder)
    LOGGER.base_input_dir = base_input_dir
    LOGGER.base_output_dir = base_output_dir

    tree_walker = TreeWalker(base_input_dir, base_output_dir, skip_webp=(not args.force_remask),
                             precompute_paths=(not args.lazy_paths))
    masker = Masker()

    for input_path, output_path, filename in tree_walker.walk():
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
                                      remote_mask=args.remote_mask, mask_color=args.mask_color)

        time_delta = round(time.time() - start_time, 3)
        LOGGER.info(__name__, f"Successfully masked image {image_path} in {time_delta} s.")


if __name__ == '__main__':
    main()
