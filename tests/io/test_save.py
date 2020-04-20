import os
import pickle
import pytest
import atexit
import numpy as np
from PIL import Image
from shutil import rmtree

from src.io.TreeWalker import Paths
from src.io import save

from tests.helpers import check_file_exists


@pytest.fixture
def image_info(get_tmp_data_dir):
    tmp_dir = get_tmp_data_dir(subdirs=["fake"])
    atexit.register(rmtree, tmp_dir)

    tmp_in = os.path.join(tmp_dir, "fake")
    tmp_out = os.path.join(tmp_dir, "out")
    tmp_arch = os.path.join(tmp_dir, "arch")
    paths = Paths(
        base_input_dir=tmp_in,
        base_mirror_dirs=[tmp_out, tmp_arch],
        input_dir=tmp_in,
        mirror_dirs=[tmp_out, tmp_arch],
        filename="test_2.jpg"
    )
    img = np.array(Image.open(paths.input_file))[None, ...]
    with open(os.path.join(paths.input_dir, "test_2_mask_results.pkl"), "rb") as f:
        mask_results = pickle.load(f)

    return img, mask_results, paths


@pytest.mark.parametrize("local_mask,remote_mask", [
    (True, True),
    (False, False)
])
def test_save_processed_img(image_info, local_mask, remote_mask):
    img, mask_results, paths = image_info
    save.save_processed_img(img, mask_results, paths, draw_mask=True, local_mask=local_mask, remote_mask=remote_mask,
                            mask_color=None, blur=15, gray_blur=True,
                            normalized_gray_blur=True)

    check_file_exists(paths.output_file)
    check_file_exists(paths.output_webp, invert=not remote_mask)
    check_file_exists(paths.input_webp, invert=not local_mask)


@pytest.mark.parametrize("archive_mask,archive_json", [
    (True, True),
    (False, False)
])
def test_archive_without_extra_files(image_info, archive_mask, archive_json):
    paths = image_info[2]

    os.makedirs(paths.output_dir)

    with open(paths.output_file, "w") as f:
        f.write("Output image")
    with open(paths.output_webp, "w") as f:
        f.write("Output webp")
    with open(paths.output_json, "w") as f:
        f.write("Output json")

    save.archive(paths, archive_mask=archive_mask, archive_json=archive_json, assert_output_mask=True)

    check_file_exists(paths.archive_file)
    check_file_exists(paths.archive_json, invert=not archive_json)
    check_file_exists(paths.archive_webp, invert=not archive_mask)


def test_archive_raises_assertion_error(image_info):
    paths = image_info[2]

    os.makedirs(paths.output_dir)
    with open(paths.output_file, "w") as f:
        f.write("Output image")

    with pytest.raises(AssertionError):
        save.archive(paths, archive_mask=False, archive_json=False, assert_output_mask=True)


def test_draw_mask_on_img(image_info):
    img, mask_results, _ = image_info
    mask_color = [100, 100, 100]
    masked_img = img.copy()
    save._draw_mask_on_img(masked_img, mask_results, mask_color=mask_color)
    mask = mask_results["detection_masks"].any(axis=1)
    mask_color = np.array(mask_color).reshape((1, 1, 1, -1))

    assert np.allclose(masked_img[mask], mask_color), "Got wrong color in colored mask!"
    assert np.allclose(img[~mask], masked_img[~mask]), "Expected masked image an input image to be equal outside mask."


def test_blur_mask_on_img(image_info):
    img, mask_results, _ = image_info

    masked_img = img.copy()
    mask = mask_results["detection_masks"].any(axis=1)
    save._blur_mask_on_img(masked_img, mask, blur_factor=15, gray_blur=True, normalized_gray_blur=True)
    assert not np.allclose(masked_img[mask], img[mask]), "Input image and masked image are equal at masked locations."
    assert np.allclose(img[~mask], masked_img[~mask]), "Expected masked image an input image to be equal outside mask."
