import os
import pickle
import numpy as np
from PIL import Image
from shutil import copy2, rmtree
# from collections import namedtuple

from src.io.TreeWalker import Paths
from src.io.save import save_processed_img, archive
from config import PROJECT_ROOT


def test_save_processed_img():
    # Create a complete set of temporary directories
    tmp_dir = os.path.join(PROJECT_ROOT, "tests", "data", "tmp")
    tmp_in = os.path.join(tmp_dir, "in")
    tmp_out = os.path.join(tmp_dir, "out")
    tmp_archive = os.path.join(tmp_dir, "archive")
    os.makedirs(tmp_in)
    os.makedirs(tmp_out)
    os.makedirs(tmp_archive)

    # Copy the original image to the temporary input directory
    orig_img = os.path.join(PROJECT_ROOT, "tests", "data", "fake", "test_2.jpg")
    tmp_img = os.path.join(tmp_in, "test_2.jpg")
    copy2(orig_img, tmp_img)

    # Create a `src.io.TreeWalker.Paths` instance which holds the relevant path details.
    paths = Paths(
        base_input_dir="",
        base_mirror_dirs=["", ""],
        input_dir=tmp_in,
        mirror_dirs=[tmp_out, tmp_archive],
        filename="test_2.jpg"
    )

    img = np.array(Image.open(tmp_img))[None, ...]
    with open(os.path.join(PROJECT_ROOT, "tests", "data", "fake", "test_2_mask_results.pkl"), "rb") as f:
        mask_results = pickle.load(f)

    exif = {"Foo": "Bar"}
    # Test with all file-writes enabled
    save_processed_img(img, mask_results, exif, paths, draw_mask=True, local_json=True, remote_json=True,
                       local_mask=True, remote_mask=True, json_objects=True, mask_color=None, blur=None)

    # Check that all expected files exist
    assert os.path.isfile(os.path.join(tmp_in, "test_2.json"))
    assert os.path.isfile(os.path.join(tmp_in, "test_2.webp"))
    assert os.path.isfile(os.path.join(tmp_out, "test_2.jpg"))
    assert os.path.isfile(os.path.join(tmp_out, "test_2.json"))
    assert os.path.isfile(os.path.join(tmp_out, "test_2.webp"))

    # Test with mask_color enabled
    save_processed_img(img, mask_results, exif, paths, draw_mask=True, local_json=False, remote_json=False,
                       local_mask=False, remote_mask=False, json_objects=False, mask_color=[100, 100, 100], blur=None)

    # Test with blur enabled
    save_processed_img(img, mask_results, exif, paths, draw_mask=True, local_json=False, remote_json=False,
                       local_mask=False, remote_mask=False, json_objects=False, mask_color=None, blur=50)

    # Test archiving
    archive(paths, archive_mask=True, archive_json=True, delete_input_img=True)
    assert not os.path.exists(os.path.join(tmp_in, "test_2.jpg"))
    assert os.path.isfile(os.path.join(tmp_archive, "test_2.jpg"))
    assert os.path.isfile(os.path.join(tmp_archive, "test_2.json"))
    assert os.path.isfile(os.path.join(tmp_archive, "test_2.webp"))

    rmtree(tmp_dir)
