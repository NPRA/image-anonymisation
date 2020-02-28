import os
import pytest
import pickle
import numpy as np
from PIL import Image
from shutil import copy2, rmtree

from src.image_util import load_image, save_processed_img
from src.main import archive
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


def test_save_processed_img():
    tmp_dir = os.path.join(PROJECT_ROOT, "tests", "data", "tmp")
    tmp_in = os.path.join(tmp_dir, "in")
    tmp_out = os.path.join(tmp_dir, "out")
    tmp_archive = os.path.join(tmp_dir, "archive")
    os.makedirs(tmp_in)
    os.makedirs(tmp_out)
    os.makedirs(tmp_archive)

    orig_img = os.path.join(PROJECT_ROOT, "tests", "data", "in", "test_2.jpg")
    tmp_img = os.path.join(tmp_in, "test_2.jpg")
    copy2(orig_img, tmp_img)

    img = np.array(Image.open(tmp_img))[None, ...]
    exif = {"Foo": "Bar"}
    with open(os.path.join(PROJECT_ROOT, "tests", "data", "in", "test_2_mask_results.pkl"), "rb") as f:
        mask_results = pickle.load(f)

    # Test with all file-writes enabled
    save_processed_img(img, mask_results, exif, input_path=tmp_in, output_path=tmp_out, filename="test_2.jpg",
                       draw_mask=True, local_json=True, remote_json=True, local_mask=True, remote_mask=True,
                       json_objects=True, mask_color=None, blur=None)

    # Check that all expected files exist
    assert os.path.isfile(os.path.join(tmp_in, "test_2.json"))
    assert os.path.isfile(os.path.join(tmp_in, "test_2.webp"))
    assert os.path.isfile(os.path.join(tmp_out, "test_2.jpg"))
    assert os.path.isfile(os.path.join(tmp_out, "test_2.json"))
    assert os.path.isfile(os.path.join(tmp_out, "test_2.webp"))

    # Test with mask_color enabled
    save_processed_img(img, mask_results, exif, input_path=tmp_in, output_path=tmp_out, filename="test_2.jpg",
                       draw_mask=True, local_json=False, remote_json=False, local_mask=False, remote_mask=False,
                       json_objects=False, mask_color=[100, 100, 100], blur=None)

    # Test with blur enabled
    save_processed_img(img, mask_results, exif, input_path=tmp_in, output_path=tmp_out, filename="test_2.jpg",
                       draw_mask=True, local_json=False, remote_json=False, local_mask=False, remote_mask=False,
                       json_objects=False, mask_color=None, blur=50)

    # Test archiving
    archive(tmp_in, [tmp_out, tmp_archive], "test_2.jpg", archive_mask=True, archive_json=True, delete_input_img=True)
    assert not os.path.exists(os.path.join(tmp_in, "test_2.jpg"))
    assert os.path.isfile(os.path.join(tmp_archive, "test_2.jpg"))
    assert os.path.isfile(os.path.join(tmp_archive, "test_2.json"))
    assert os.path.isfile(os.path.join(tmp_archive, "test_2.webp"))

    rmtree(tmp_dir)
