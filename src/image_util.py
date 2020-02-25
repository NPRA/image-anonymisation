"""
Utility functions for working with images.
"""
import os
import webp
import numpy as np
from PIL import Image, UnidentifiedImageError
from cv2 import blur as cv2_blur

import config
from src.exif_util import get_exif, write_exif
from src.Logger import LOGGER
from src.mscoco_label_map import LABEL_MAP


def load_image(image_path, read_exif=True):
    """
    Reads the image at 'image_path' and returns it as an array. None is returned i the image could not be loaded.

    :param image_path: Path to image. Must end with '.jpg'
    :type image_path: str
    :param read_exif: Read the EXIF data from the input image?
    :type read_exif: bool
    :return: Image array
    :rtype: (np.ndarray, dict | None) | None
    """
    assert os.path.exists(image_path), f"Could not find image at '{image_path}'"
    assert image_path.endswith(".jpg"), f"Expected image with .jpg extension. Got '{image_path}'"

    try:
        pil_img = Image.open(image_path)
        img = np.array(pil_img)

        if read_exif:
            exif = get_exif(pil_img)
        else:
            exif = None
    except (FileNotFoundError, ValueError, IndexError, RuntimeError, UnidentifiedImageError) as e:
        raise AssertionError(str(e))

    assert img.ndim == 3, f"Got wrong number of dimensions ({img.ndim} != 3) for loaded image '{image_path}'"
    assert img.shape[2] == 3, f"Got wrong number of channels ({img.shape[2]} != 3) for loaded image '{image_path}'"
    return np.expand_dims(img, 0), exif


def save_processed_img(img, mask_results, exif, input_path, output_path, filename, draw_mask=False, local_json=False,
                       remote_json=False, local_mask=False, remote_mask=False, json_objects=True, mask_color=None,
                       blur=None):
    """
    Save an image which has been processed by the masker.

    :param img: Input image
    :type img: np.ndarray
    :param mask_results: Dictionary containing masking results. Format must be as returned by Masker.mask.
    :type mask_results: dict
    :param exif: Exif data for input image.
    :type exif: dict
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
    """
    os.makedirs(output_path, exist_ok=True)

    # Compute a single boolean mask from all the detection masks.
    detection_masks = mask_results["detection_masks"]
    assert detection_masks.ndim == 4, f"Expected detection_masks to be 4D (batch, mask_index, height, width). " \
                                      f"Got {detection_masks.ndim}."
    agg_mask = np.isin(detection_masks, config.MASK_LABELS).any(axis=1)

    if draw_mask:
        if blur is not None:
            _blur_mask_on_img(img, agg_mask, blur_factor=blur)
        else:
            _draw_mask_on_img(img, mask_results, mask_color=mask_color)

    json_filename = os.path.splitext(filename)[0] + ".json"
    webp_filename = os.path.splitext(filename)[0] + ".webp"

    if json_objects:
        exif["detected_objects"] = _get_detected_objects_dict(mask_results)

    if local_mask:
        _save_mask(agg_mask, os.path.join(input_path, webp_filename))
    if remote_mask:
        _save_mask(agg_mask, os.path.join(output_path, webp_filename))
    if local_json:
        write_exif(exif, os.path.join(input_path, json_filename))
    if remote_json:
        write_exif(exif, os.path.join(output_path, json_filename))

    pil_img = Image.fromarray(img[0].astype(np.uint8))
    pil_img.save(os.path.join(output_path, filename))


def _get_detected_objects_dict(mask_results):
    objs = mask_results["detection_classes"].squeeze()[:int(mask_results["num_detections"])]
    if objs.size > 0:
        # Find unique objects and count them
        objs, counts = np.unique(objs, return_counts=True)
        # Convert object from id to string
        objs = [LABEL_MAP[int(obj_id)] for obj_id in objs]
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


def _blur_mask_on_img(img, mask, blur_factor):
    if blur_factor < 1:
        return
    ksize = int((blur_factor / 1000) * img.shape[2])
    blurred = cv2_blur(img[0], (ksize, ksize))[None, ...]
    img[mask] = blurred[mask]


def _save_mask(mask, output_filepath):
    mask = np.tile(mask[0, :, :, None], (1, 1, 3)).astype(np.uint8)
    webp.imwrite(output_filepath, mask, pilmode="RGB")
