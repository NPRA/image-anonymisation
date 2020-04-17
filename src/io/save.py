import os
import webp
import numpy as np
from shutil import copy2
from PIL import Image
import cv2

import config
from src.Logger import LOGGER
from src.io.file_access_guard import wait_until_path_is_found


def save_processed_img(img, mask_results, paths, draw_mask=False, local_mask=False, remote_mask=False, mask_color=None,
                       blur=None, gray_blur=True, normalized_gray_blur=True):
    """
    Save an image which has been processed by the masker.

    :param img: Input image
    :type img: np.ndarray
    :param mask_results: Dictionary containing masking results. Format must be as returned by Masker.mask.
    :type mask_results: dict
    :param paths: Paths object representing the image file.
    :type paths: src.io.TreeWalker.Paths
    :param draw_mask: Draw the mask on the image?
    :type draw_mask: bool
    :param local_mask: Write the Mask file to the input directory?
    :type local_mask: bool
    :param remote_mask: Write the Mask file to the output directory?
    :type remote_mask: bool
    :param mask_color: Mask color. All masks in the output image will have this color. If `mask_color` is None, the
                       colors in `config` will be used.
    :type mask_color: list | None
    :param blur: When `blur` is not None, the image will be blurred instead of colored at the masked locations. `blur`
                 should be a number in [1 - 1000] indicating the size of the mask used in for blurring. Specifically,
                 `mask_size = (blur / 1000) * image_width`.
    :type blur: int | float | None
    :param gray_blur: Convert the image to grayscale before blurring?
    :type gray_blur: bool
    :param normalized_gray_blur: Normalize the gray level within each mask after blurring? This will make bright colors
                                 indistinguishable from dark colors. NOTE: Requires gray_blur=True.
    :type normalized_gray_blur: bool
    :returns: 0
    :rtype: int
    """
    # Make the output directory
    os.makedirs(paths.output_dir, exist_ok=True)

    # Compute a single boolean mask from all the detection masks.
    detection_masks = mask_results["detection_masks"]
    agg_mask = (detection_masks > 0).any(axis=1)

    if draw_mask and mask_results["num_detections"] > 0:
        if blur is not None:
            _blur_mask_on_img(img, agg_mask, blur_factor=blur, gray_blur=gray_blur,
                              normalized_gray_blur=normalized_gray_blur)
        else:
            _draw_mask_on_img(img, mask_results, mask_color=mask_color)

    # Save masked image
    pil_img = Image.fromarray(img[0].astype(np.uint8))
    pil_img.save(paths.output_file)

    if local_mask:
        wait_until_path_is_found([paths.input_dir])
        _save_mask(agg_mask, paths.input_webp)
    if remote_mask:
        wait_until_path_is_found([paths.output_dir])
        _save_mask(agg_mask, paths.output_webp)
    return 0


def archive(paths, archive_mask=False, archive_json=False, delete_input_img=False,
            assert_output_mask=True):
    """
    Copy the input image file (and possibly some output files) to the archive directory.

    :param paths: Paths object representing the image file.
    :type paths: src.io.TreeWalker.Paths
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
    os.makedirs(paths.archive_dir, exist_ok=True)

    if assert_output_mask:
        assert os.path.isfile(paths.output_webp), f"Archiving aborted. Output mask '{paths.output_webp}' not found."

    _copy_file(paths.input_file, paths.archive_file)
    if archive_mask:
        _copy_file(paths.output_webp, paths.archive_webp)
    if archive_json:
        _copy_file(paths.output_json, paths.archive_json)
    return 0


def _copy_file(source_file, destination_file):
    if os.path.exists(destination_file):
        LOGGER.warning(__name__, f"Archive file {destination_file} already exists. The existing file will be "
                                 f"overwritten.")
    copy2(source_file, destination_file)


def _draw_mask_on_img(img, mask_results, mask_color=None):
    detection_masks = mask_results["detection_masks"]
    if mask_color is not None:
        mask = (detection_masks > 0).any(axis=1)
        img[mask] = np.array(mask_color)
    else:
        detection_classes = mask_results["detection_classes"][0]
        for i in range(len(detection_classes)):
            detected_label = detection_classes[i]
            mask = detection_masks[:, i, ...] > 0
            img[mask] = config.LABEL_COLORS.get(detected_label, config.DEFAULT_COLOR)


def _blur_mask_on_img(img, mask, blur_factor, gray_blur=True, normalized_gray_blur=True):
    ksize = int((blur_factor / 1000) * img.shape[2])
    if ksize < 3:
        # Return if the kernel size is very small. Filtering with this kernel size would have no effect.
        return
    if gray_blur and normalized_gray_blur:
        _apply_normalized_gray_blur(img, mask, ksize)
    elif gray_blur:
        _apply_gray_blur(img, mask, ksize)
    else:
        _apply_color_blur(img, mask, ksize)


def _apply_color_blur(img, mask, ksize):
    blurred = cv2.blur(img[0], (ksize, ksize))[None, ...]
    img[mask] = blurred[mask]


def _apply_gray_blur(img, mask, ksize):
    gray = cv2.cvtColor(img[0], cv2.COLOR_RGB2GRAY)
    blurred = cv2.blur(gray, (ksize, ksize))[None, :, :, None]
    img[mask] = blurred[mask]


def _apply_normalized_gray_blur(img, mask, ksize):
    large_ksize = int(1.2 * ksize)
    default_gray_value = 100
    gray = cv2.cvtColor(img[0], cv2.COLOR_RGB2GRAY)
    blurred = cv2.blur(gray, (ksize, ksize))[None, :, :, None]
    blurred_large = cv2.blur(gray, (large_ksize, large_ksize))[None, :, :, None]
    img[mask] = blurred[mask] - blurred_large[mask] + default_gray_value


def _save_mask(mask, output_webp):
    mask = np.tile(mask[0, :, :, None], (1, 1, 3)).astype(np.uint8)
    webp.imwrite(output_webp, mask, pilmode="RGB")
