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