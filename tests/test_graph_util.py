import os
from shutil import rmtree
import numpy as np
import tensorflow as tf

from src import graph_util
from config import PROJECT_ROOT


def _check_load_model(model_path):
    """
    Check that the model at `model_path` can be loaded, and that it can process a simple test image.

    :param model_path: Full path to model directory.
    :type model_path: str
    """
    model = tf.saved_model.load(os.path.join(model_path, "saved_model"))
    model = model.signatures["serving_default"]
    test_img = tf.constant(np.zeros((1, 64, 64, 3)), tf.uint8)
    model(test_img)


def _check_model_dir(model_path):
    """
    Check that the given model directory
        - exists;
        - is not empty;
        - contains a `saved_model` directory; and
        - contains a `saved_model/saved_model.pb`

    :param model_path: Full path to model directory
    :type model_path: str
    """
    assert os.path.isdir(model_path), f"Path to extracted model not found '{model_path}'"
    assert os.listdir(model_path), f"Model directory is empty '{model_path}'"

    saved_model_path = os.path.join(model_path, "saved_model")
    assert os.path.isdir(saved_model_path), f"Path to saved model not found '{saved_model_path}'"

    saved_model_files = os.listdir(saved_model_path)
    assert saved_model_files, f"Saved model directory is empty '{saved_model_path}'"
    assert "saved_model.pb" in saved_model_files, f"Could not find model file 'saved_model.pb' in model directory " \
                                                  f"'{saved_model_path}'"


def test_download_model():
    """
    Test that all three model (slow, medium, and fast) can be downloaded, extracted, and ran.
    """
    model_names = [
        'mask_rcnn_inception_resnet_v2_atrous_coco_2018_01_28',
        "mask_rcnn_resnet101_atrous_coco_2018_01_28",
        "mask_rcnn_inception_v2_coco_2018_01_28",
    ]
    base_model_path = os.path.join(PROJECT_ROOT, "tests", "tmp")
    download_base = 'http://download.tensorflow.org/models/object_detection/'

    for model_name in model_names:
        model_path = os.path.join(base_model_path, model_name)
        graph_util.download_model(download_base, model_name, model_path, extract_all=True)
        _check_model_dir(model_path)
        _check_load_model(model_path)

    if os.path.isdir(base_model_path):
        rmtree(base_model_path)
    else:
        raise RuntimeError("Could not find download-path for downloaded testing models.")
