"""
Utility functions for working with images.
"""
import os
import uuid
import json
import webp
import numpy as np
from PIL import Image

from src import config
from src.exif_util import get_labeled_exif, pyntxml, fiskFraviatechXML
from src.Logger import LOGGER


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
        LOGGER.warning(__name__, f"Could not find image at '{image_path}'")
        return None
    if not image_path.endswith(".jpg"):
        LOGGER.warning(__name__, f"Expected image with .jpg extension. Got '{image_path}'")
        return None

    try:
        pil_img = Image.open(image_path)
        img = np.array(pil_img)

        if read_exif:
            exif = _get_exif(pil_img, image_path)
        else:
            exif = None
    except (FileNotFoundError, ValueError, IndexError, RuntimeError) as e:
        LOGGER.warning(__name__, f"Got Exception '{str(e)}' while importing image '{image_path}'.", save=True)
        return None

    if img.ndim != 3:
        LOGGER.warning(__name__, f"Got wrong number of dimensions ({img.ndim} != 3) for loaded image '{image_path}'",
                       save=True)
        return None
    if img.shape[2] != 3:
        LOGGER.warning(__name__, f"Got wrong number of channels ({img.shape[2]} != 3) for loaded image '{image_path}'",
                       save=True)
        return None

    img = np.expand_dims(img, 0)
    return img, exif


def save_processed_img(img, mask_results, exif, input_path, output_path, filename, draw_mask=False, local_json=False,
                       remote_json=False, local_mask=False, remote_mask=False):
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
    """
    os.makedirs(output_path, exist_ok=True)

    # Compute a single boolean mask from all the detection masks.
    detection_masks = mask_results["detection_masks"]
    assert detection_masks.ndim == 4, f"Expected detection_masks to be 4D (batch, mask_index, height, width). " \
                                      f"Got {detection_masks.ndim}."
    agg_mask = np.isin(detection_masks, config.MASK_LABELS).any(axis=1)

    if draw_mask:
        _draw_mask_on_img(img, agg_mask)

    json_filename = os.path.splitext(filename)[0] + ".json"
    webp_filename = os.path.splitext(filename)[0] + ".webp"

    if local_mask:
        _save_mask(agg_mask, os.path.join(input_path, webp_filename))
    if remote_mask:
        _save_mask(agg_mask, os.path.join(output_path, webp_filename))
    if local_json:
        _write_exif(exif, os.path.join(input_path, json_filename))
    if remote_json:
        _write_exif(exif, os.path.join(output_path, json_filename))

    pil_img = Image.fromarray(img[0].astype(np.uint8))
    pil_img.save(os.path.join(output_path, filename))


def _draw_mask_on_img(img, mask):
    fill_color = np.array([0, 0, 0])
    img[mask] = fill_color


def _save_mask(mask, output_filepath):
    mask = np.tile(mask[0, :, :, None], (1, 1, 3)).astype(np.uint8)
    webp.imwrite(output_filepath, mask, pilmode="RGB")


def _get_exif(img, image_path):
    # img.verify()
    exif = img._getexif()
    if exif is None:
        LOGGER.error(__name__, f"No EXIF data found for file {image_path}.")
        exif = {}

    labeled = get_labeled_exif(exif)

    # Fisker ut XML'en som er stappet inn som ikke-standard exif element
    xmldata = pyntxml(labeled)
    if xmldata is not None:
        # Fisker ut mer data fra viatech xml
        viatekmeta = fiskFraviatechXML(xmldata)
    else:
        err_msg = f"Unable to clean XML-data for file {image_path}."
        LOGGER.error(__name__, err_msg, save=True)
        viatekmeta = {}

    # Bildetittel - typisk etelleranna med viatech Systems
    XPTitle = ''
    if 'XPTitle' in labeled.keys():
        XPTitle = labeled['XPTitle'].decode('utf16')

    viatekmeta['exif_xptitle'] = XPTitle
    viatekmeta['bildeuiid'] = str(uuid.uuid4())
    return viatekmeta


def _write_exif(exif, output_filepath):
    with open(output_filepath, "w") as out_file:
        json.dump(exif, out_file, indent=4, ensure_ascii=False)
