import os
import webp
import logging
import numpy as np
from PIL import Image

from src import config

LOGGER = logging.getLogger(__name__)


def load_image(image_path):
    if not os.path.exists(image_path):
        LOGGER.warning(f"Could not find image at '{image_path}'")
        return None
    if not image_path.endswith(".jpg"):
        LOGGER.warning(f"Expected image with .jpg extension. Got '{image_path}'")
        return None

    try:
        img = Image.open(image_path)
        img = np.array(img)
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
    return img


def save_processed_img(img, mask_results, output_filepath, draw_mask=False, exif_json=False, mask_webp=False):
    assert output_filepath.endswith(".jpg")
    os.makedirs(os.path.dirname(output_filepath), exist_ok=True)

    # Compute a single boolean mask from all the detection masks.
    detection_masks = mask_results["detection_masks"]
    assert detection_masks.ndim == 4, f"Expected detection_masks to be 4D (batch, mask_index, height, width). " \
                                      f"Got {detection_masks.ndim}."
    agg_mask = np.isin(detection_masks, config.MASK_LABELS).any(axis=1)

    if draw_mask:
        draw_mask_on_img(img, agg_mask)

    if mask_webp:
        save_mask(agg_mask, output_filepath)

    pil_img = Image.fromarray(img[0].astype(np.uint8))
    pil_img.save(output_filepath)


def save_mask(mask, output_filepath):
    output_filepath = output_filepath[:-4] + ".webp"
    mask = np.tile(mask[0, :, :, None], (1, 1, 3)).astype(np.uint8)
    webp.imwrite(output_filepath, mask, pilmode="RGB")


def draw_mask_on_img(img, mask):
    fill_color = np.array([0, 0, 0])
    img[mask] = fill_color
