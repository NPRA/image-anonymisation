import os
import webp
import numpy as np
from shutil import copy2
from PIL import Image
import cv2

import config
from src.Logger import LOGGER
from src.io.exif_util import write_exif, exif_from_file
from src.io.file_access_guard import wait_until_path_is_found


def save_processed_img(img, mask_results, input_path, output_path, filename, draw_mask=False, local_json=False,
                       remote_json=False, local_mask=False, remote_mask=False, json_objects=True, mask_color=None,
                       blur=None, gray_blur=True, normalized_gray_blur=True):
    """
    Save an image which has been processed by the masker.

    :param img: Input image
    :type img: np.ndarray
    :param mask_results: Dictionary containing masking results. Format must be as returned by Masker.mask.
    :type mask_results: dict
    :param input_path: Path to input directory
    :type input_path: str
    :param output_path: Path to output directory
    :type output_path: str
    :param filename: Name of image file
    :type filename: str
    :param draw_mask: Draw the mask on the image?
    :type draw_mask: bool
    :param local_json: Write the EXIF .json file to the input directory?
    :type local_json: bool
    :param remote_json: Write the EXIF .json file to the output directory?
    :type remote_json: bool
    :param local_mask: Write the Mask file to the input directory?
    :type local_mask: bool
    :param remote_mask: Write the Mask file to the output directory?
    :type remote_mask: bool
    :param json_objects: Add a dictionary containing the detected objects and their counts to the .json file?
    :type json_objects: bool
    :param mask_color: Mask color. All masks in the output image will have this color. If `mask_color` is None, the
                       colors in `config` will be used.
    :type mask_color: list | None
    :param blur: When `blur` is not None, the image will be blurred instead of colored at the masked locations. `blur`
                 should be a number in [1 - 1000] indicating the size of the mask used in for blurring. Specifically,
                 `mask_size = (blur / 1000) * image_width`.
    :type blur: int | float | None
    :param gray_blur: Convert the image to grayscale before blurring?
    :type gray_blur: bool

    :returns: 0
    :rtype: int
    """
    # Ensure that the output directory and input file both exist
    wait_until_path_is_found([os.path.join(input_path, filename), os.path.dirname(output_path)])
    os.makedirs(output_path, exist_ok=True)

    # Get EXIF data
    exif = exif_from_file(os.path.join(input_path, filename))

    # Compute a single boolean mask from all the detection masks.
    detection_masks = mask_results["detection_masks"]
    assert detection_masks.ndim == 4, f"Expected detection_masks to be 4D (batch, mask_index, height, width). " \
                                      f"Got {detection_masks.ndim}."
    agg_mask = np.isin(detection_masks, config.MASK_LABELS).any(axis=1)

    if draw_mask:
        if blur is not None:
            _blur_mask_on_img(img, agg_mask, blur_factor=blur, gray_blur=gray_blur,
                              normalized_gray_blur=normalized_gray_blur)
        else:
            _draw_mask_on_img(img, mask_results, mask_color=mask_color)

    # Save masked image
    pil_img = Image.fromarray(img[0].astype(np.uint8))
    pil_img.save(os.path.join(output_path, filename))

    # Save metadata and .webp mask
    json_filename = os.path.splitext(filename)[0] + ".json"
    webp_filename = os.path.splitext(filename)[0] + ".webp"
    if json_objects:
        exif["detected_objects"] = _get_detected_objects_dict(mask_results)
    if local_json:
        write_exif(exif, os.path.join(input_path, json_filename))
    if remote_json:
        write_exif(exif, os.path.join(output_path, json_filename))
    if local_mask:
        _save_mask(agg_mask, os.path.join(input_path, webp_filename))
    if remote_mask:
        _save_mask(agg_mask, os.path.join(output_path, webp_filename))
    return 0


def archive(input_path, mirror_paths, filename, archive_mask=False, archive_json=False, delete_input_img=False,
            assert_output_mask=True):
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
    :param assert_output_mask: Assert that the output mask exists before archiving?
    :type assert_output_mask: bool
    :returns: 0
    :rtype: int
    """
    # Ensure that the paths can be reached.
    wait_until_path_is_found([input_path, *mirror_paths])
    
    if assert_output_mask:
        output_mask = os.path.join(mirror_paths[0], os.path.splitext(filename)[0] + ".webp")
        assert os.path.isfile(output_mask), f"Archiving aborted. Output mask '{output_mask}' not found."

    input_jpg = _copy_file(input_path, mirror_paths[1], filename, ext=None)
    if archive_mask:
        _copy_file(mirror_paths[0], mirror_paths[1], filename, ext=".webp")
    if archive_json:
        _copy_file(mirror_paths[0], mirror_paths[1], filename, ext=".json")
    if delete_input_img:
        os.remove(input_jpg)
    return 0


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


def _get_detected_objects_dict(mask_results):
    objs = mask_results["detection_classes"].squeeze()[:int(mask_results["num_detections"])]
    if objs.size > 0:
        # Find unique objects and count them
        objs, counts = np.unique(objs, return_counts=True)
        # Convert object from id to string
        objs = [config.LABEL_MAP[int(obj_id)] for obj_id in objs]
        # Create dict
        objs = dict(zip(objs, counts.astype(str)))
    else:
        objs = {}
    return objs


def _draw_mask_on_img(img, mask_results, mask_color=None):
    detection_masks = mask_results["detection_masks"]
    if mask_color is not None:
        mask = np.isin(detection_masks, config.MASK_LABELS).any(axis=1)
        img[mask] = np.array(mask_color)
    else:
        detection_classes = mask_results["detection_classes"].squeeze()
        num_detections = int(mask_results["num_detections"])
        for i in range(num_detections):
            detected_label = int(detection_classes[i])
            if detected_label in config.MASK_LABELS:
                mask = detection_masks[:, i, ...] > 0
                img[mask] = config.LABEL_COLORS.get(detected_label, config.DEFAULT_COLOR)


def _blur_mask_on_img(img, mask, blur_factor, gray_blur=True, normalized_gray_blur=True):
    if blur_factor < 1:
        return
    ksize = int((blur_factor / 1000) * img.shape[2])
    if gray_blur:
        gray = cv2.cvtColor(img[0], cv2.COLOR_RGB2GRAY)
        blurred = cv2.blur(gray, (ksize, ksize))
        if normalized_gray_blur:
            blurred = _local_gray_normalization(blurred, ksize)
        blurred = blurred[None, :, :, None]
    else:
        blurred = cv2.blur(img[0], (ksize, ksize))[None, ...]
    img[mask] = blurred[mask]


def _local_gray_normalization(blurred, ksize):
    blurred = blurred.astype(np.float32)
    blurred_again = cv2.blur(blurred, (ksize, ksize))
    blurred_again[blurred_again < 0.1] = 0.1
    blurred /= blurred_again
    blurred *= 100
    return blurred.astype(np.uint8)


def _save_mask(mask, output_filepath):
    mask = np.tile(mask[0, :, :, None], (1, 1, 3)).astype(np.uint8)
    webp.imwrite(output_filepath, mask, pilmode="RGB")
