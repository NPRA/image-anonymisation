"""
Utility functions for working with images.
"""
import os
import uuid
import json
import webp
import logging
import numpy as np
from PIL import Image

from src import config
from src.exif_util import fiksutf8, get_labeled_exif, pyntxml, fiskFraviatechXML

LOGGER = logging.getLogger(__name__)


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
    if not os.path.exists(image_path):
        LOGGER.warning(f"Could not find image at '{image_path}'")
        return None
    if not image_path.endswith(".jpg"):
        LOGGER.warning(f"Expected image with .jpg extension. Got '{image_path}'")
        return None

    try:
        pil_img = Image.open(image_path)
        img = np.array(pil_img)

        if read_exif:
            exif = _get_exif(pil_img, image_path)
        else:
            exif = None

    except (FileNotFoundError, ValueError, IndexError, RuntimeError) as e:
        LOGGER.warning(f"Got Exception '{str(e)}' while importing image '{image_path}'.")
        return None

    if img.ndim != 3:
        LOGGER.warning(f"Got wrong number of dimensions ({img.ndim} != 3) for loaded image '{image_path}'")
        return None
    if img.shape[2] != 3:
        LOGGER.warning(f"Got wrong number of channels ({img.shape[2]} != 3) for loaded image '{image_path}'")
        return None

    img = np.expand_dims(img, 0)
    return img, exif


def save_processed_img(img, mask_results, output_filepath, exif=None, draw_mask=False, exif_json=False,
                       mask_webp=False):
    """
    Save an image which has been processed by the masker.

    :param img: Input image
    :type img: np.ndarray
    :param mask_results: Dictionary containing masking results. Format must be as returned by Masker.mask.
    :type mask_results: dict
    :param output_filepath: Path to output image. Must end with '.jpg'
    :type output_filepath: str
    :param exif: Exif data for input image.
    :type exif: dict
    :param draw_mask: Draw the mask on the image?
    :type draw_mask: bool
    :param exif_json: Write a .json file containing the EXIF-data of the image?
    :type exif_json: bool
    :param mask_webp: Export the mask as a separate .webp image?
    :type mask_webp: bool
    """
    assert output_filepath.endswith(".jpg")
    os.makedirs(os.path.dirname(output_filepath), exist_ok=True)

    # Compute a single boolean mask from all the detection masks.
    detection_masks = mask_results["detection_masks"]
    assert detection_masks.ndim == 4, f"Expected detection_masks to be 4D (batch, mask_index, height, width). " \
                                      f"Got {detection_masks.ndim}."
    agg_mask = np.isin(detection_masks, config.MASK_LABELS).any(axis=1)

    if draw_mask:
        _draw_mask_on_img(img, agg_mask)

    if mask_webp:
        _save_mask(agg_mask, output_filepath)

    if exif_json:
        _write_exif(exif, output_filepath)

    pil_img = Image.fromarray(img[0].astype(np.uint8))
    pil_img.save(output_filepath)


def _save_mask(mask, output_filepath):
    output_filepath = output_filepath[:-4] + ".webp"
    mask = np.tile(mask[0, :, :, None], (1, 1, 3)).astype(np.uint8)
    webp.imwrite(output_filepath, mask, pilmode="RGB")


def _draw_mask_on_img(img, mask):
    fill_color = np.array([0, 0, 0])
    img[mask] = fill_color


def _get_exif(img, image_path):
    # img.verify()
    exif = img._getexif()
    if exif is None:
        LOGGER.error(f"No EXIF data found for file {image_path}.")
        exif = {}

    labeled = get_labeled_exif(exif)

    # Fisker ut XML'en som er stappet inn som ikke-standard exif element
    xmldata = pyntxml(labeled)
    if xmldata is not None:
        # Fisker ut mer data fra viatech xml
        viatekmeta = fiskFraviatechXML(xmldata)
    else:
        LOGGER.error(f"Unable to clean XML-data for file {image_path}.")
        viatekmeta = {}

    # Bildetittel - typisk etelleranna med viatech Systems
    XPTitle = ''
    if 'XPTitle' in labeled.keys():
        XPTitle = labeled['XPTitle'].decode('utf16')

    viatekmeta['exif_xptitle'] = XPTitle
    viatekmeta['bildeuiid'] = str(uuid.uuid4())
    return viatekmeta


def _write_exif(exif, output_filepath):
    output_filepath = output_filepath[:-4] + ".json"
    with open(output_filepath, "w") as out_file:
        json.dump(exif, out_file, indent=4, ensure_ascii=False)
