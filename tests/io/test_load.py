import os
import pytest
import numpy as np

from src.io.load import load_image
from config import PROJECT_ROOT

IMG_DIR = os.path.join(PROJECT_ROOT, "tests", "data", "in")


def test_load_image():
    # Non-existing image
    with pytest.raises(AssertionError):
        load_image("foobar.jpg")
    # Not a .jgp file
    with pytest.raises(AssertionError):
        load_image(os.path.join(IMG_DIR, "imgs.txt"))
    # Corrupted .jpg file
    with pytest.raises(AssertionError):
        load_image(os.path.join(IMG_DIR, "corrupted.jpg"))
    # No EXIF data
    with pytest.raises(AssertionError):
        load_image(os.path.join(IMG_DIR, "test_2.jpg"))

    img, exif = load_image(os.path.join(IMG_DIR, "åæø", "test_1.jpg"), read_exif=False)
    assert exif is None, f"Expected exif to be None when read_exif=False"
    assert isinstance(img, np.ndarray), f"Got image with wrong type: {type(img)}"

    # Image checks. Same as in Masker.mask()
    assert img.ndim == 4, "Expected a 4D image tensor (batch, height, width, channel)."
    assert img.shape[0] == 1, "Batch size != 1 is currently not supported."
    assert img.shape[3] == 3, "Image must have 3 channels."
    assert (np.array(img.shape) > 0).all(), "All image dimensions must be > 0."
    assert np.isfinite(img).all(), "Got non-finite numbers in input image."
    assert ((img >= 0) & (img <= 255)).all(), "Expected all pixel-values to be in [0, ..., 255]."
