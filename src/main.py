import os
import time
import logging
import argparse

from src import image_util
from src.TreeWalker import TreeWalker
from src.Masker import Masker

LOGGER = logging.getLogger(__name__)


def get_args():
    """
    Parse command line arguments.

    :return: Parsed arguments
    :rtype: argparse.ArgumentParser
    """
    parser = argparse.ArgumentParser(description='Image anonymisation')
    parser.add_argument("-i", "--input-folder", dest="input_folder", help="Base directory for input images.")
    parser.add_argument("-o", "--output-folder", dest="output_folder", help="Base directory for masked (output) "
                                                                            "images and metadata files")
    parser.add_argument("-d", "--draw-mask", action="store_true", dest="draw_mask", help="Apply the mask to the image?")
    parser.add_argument("-e", "--exif-json", action="store_true", dest="exif_json", help="Export the EXIF header to a "
                                                                                         ".json file?")
    parser.add_argument("-m", "--mask-webp", action="store_true", dest="mask_webp", help="Save mask as separate .webp"
                                                                                         " file?")
    parser.add_argument("--force-remasking", action="store_true", dest="force_remask", help="When this flag is set, the"
                                                                                            " masks will be recomputed"
                                                                                            " even though the .webp "
                                                                                            "file exists.")
    parser.add_argument("--lazy-paths", action="store_true", dest="lazy_paths", help="When this flag is set, the file "
                                                                                     "tree will be traversed during the"
                                                                                     " masking process. Otherwise, all "
                                                                                     "paths will be identified and "
                                                                                     "stored before the masking starts")
    args = parser.parse_args()
    return args


def main():
    """Run the masking."""
    logging.basicConfig(level=logging.INFO)
    args = get_args()
    tree_walker = TreeWalker(args.input_folder, args.output_folder, skip_webp=(not args.force_remask),
                             precompute_paths=(not args.lazy_paths))
    masker = Masker()

    for input_path, output_path, filename in tree_walker.walk():
        image_path = os.path.join(input_path, filename)
        img, exif = image_util.load_image(image_path, read_exif=args.exif_json)
        if img is None:
            # TODO: Copy image to error directory
            continue

        start_time = time.time()
        mask_results = masker.mask(img)
        time_delta = round(time.time() - start_time, 3)
        LOGGER.info(f"Successfully masked image {image_path} in {time_delta} s.")

        output_filepath = os.path.join(output_path, filename)
        image_util.save_processed_img(img, mask_results, output_filepath, exif, args.draw_mask, args.exif_json,
                                      args.mask_webp)

    masker.close()


if __name__ == '__main__':
    main()
