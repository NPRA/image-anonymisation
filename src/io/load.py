import os
import numpy as np
from PIL import Image, UnidentifiedImageError

from src.io.exif_util import get_exif


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


def check_input_img(img):
    """
    Check that the given image (represented as a numpy array) is valid for masking.

    :param img: Input image
    :type img: np.ndarray
    """
    assert img.ndim == 4, "Expected a 4D image tensor (batch, height, width, channel)."
    assert img.shape[0] == 1, "Batch size != 1 is currently not supported."
    assert img.shape[3] == 3, "Image must have 3 channels."
    assert (np.array(img.shape) > 0).all(), "All image dimensions must be > 0."
    assert np.isfinite(img).all(), "Got non-finite numbers in input image."
    assert ((img >= 0) & (img <= 255)).all(), "Expected all pixel-values to be in [0, ..., 255]."
    return 0
