import os
import pytest
from unittest import mock
import tensorflow as tf
import numpy as np

from src.io.tf_dataset import get_tf_dataset, prepare_img
from config import PROJECT_ROOT

IMG_DIR = os.path.join(PROJECT_ROOT, "tests", "data", "fake")


class FakeTreeWalker:
    def __init__(self, input_paths, filenames):
        self.input_paths = input_paths
        self.filenames = filenames

    def walk(self):
        for input_path, filename in zip(self.input_paths, self.filenames):
            yield input_path, ["", ""], filename


def test_get_tf_dataset():
    """
    Check that `get_tf_dataset` finds all elements in the given `TreeWalker` instance
    """
    files = [str(i) for i in range(10)]
    tree_walker = FakeTreeWalker(files, files)

    with mock.patch("src.io.tf_dataset.prepare_img", new=lambda x, *_: x):
        dataset = get_tf_dataset(tree_walker)
        dataset_files = [f.numpy().decode("utf-8") for f in dataset]

    assert len(files) == len(dataset_files)
    for f1, f2 in zip(files, dataset_files):
        assert f1 == f2


def test_prepare_img_loads_files():
    """
    Test that images are properly loaded.
    """
    input_paths = [
        os.path.join(IMG_DIR, "%#{} _  _ _"),
        os.path.join(IMG_DIR, "åæø"),
        IMG_DIR
    ]
    files = [
        "test_0.jpg",
        "test_1.jpg",
        "test_2.jpg"
    ]
    tree_walker = FakeTreeWalker(input_paths, files)
    dataset = get_tf_dataset(tree_walker)

    control_images = []
    for p, f in zip(input_paths, files):
        img_data = tf.io.read_file(tf.constant(os.path.join(p, f), tf.string))
        control_images.append(tf.io.decode_jpeg(img_data).numpy())

    dataset_images = [img.numpy().squeeze() for img in dataset]

    for img_1, img_2 in zip(control_images, dataset_images):
        assert (img_1 == img_2).all()


def test_prepare_imgs_bad_image_tensor():
    """
    Check that `prepare_img` raises an `tf.errors.UnknownError` when the input image tensor is invalid.
    """
    bad_imgs = {
        "Negative values":      np.full((1, 100, 200, 3), -1),
        "NaNs":                 np.full((1, 100, 200, 3), np.nan),
        "Infs":                 np.full((1, 100, 200, 3), np.inf),
        "Zero dimension":       np.empty((1, 0, 100, 3)),
        "Wrong channel number": np.ones((1, 100, 100, 1), dtype=np.uint8),
        "Wrong batch number":   np.ones((5, 100, 100, 3), dtype=np.uint8),
        "Wrong ndim":           np.ones((2, 2), dtype=np.uint8),
    }

    for _, img_array in bad_imgs.items():
        with mock.patch("tensorflow.io.read_file", new=lambda *_: tf.constant("")):
            with mock.patch("tensorflow.image.decode_jpeg", new=lambda *_: tf.constant(img_array)):
                with mock.patch("src.io.tf_dataset.wait_until_path_is_found", new=lambda *_, **__: None):
                    with pytest.raises(tf.errors.UnknownError):
                        prepare_img("", "", "")


def test_prepare_imgs_bad_image_file():
    """
    Check that `prepare_img` raises the proper exceptions on corrupted and missing files.
    """
    img_dir = tf.constant(IMG_DIR, tf.string)

    corrupted_filename = tf.constant("corrupted.jpg", tf.string)
    with pytest.raises(tf.errors.InvalidArgumentError):
        prepare_img(img_dir, "", corrupted_filename)

    non_existing_filename = tf.constant("foobar.jpg", tf.string)
    with pytest.raises(FileNotFoundError):
        prepare_img(img_dir, "", non_existing_filename)
