import os
import pytest
import numpy as np
import tensorflow as tf

from src.Masker import Masker, download_model


@pytest.mark.slow
def test_Masker():
    masker = Masker()
    img = tf.zeros((1, 1018, 2703, 3), dtype=tf.uint8)
    results = masker.mask(img)

    assert "num_detections" in results
    assert "detection_boxes" in results
    assert "detection_masks" in results
    assert "detection_classes" in results

    mask_shape = results["detection_masks"].shape
    assert mask_shape[2] == img.shape[1]
    assert mask_shape[3] == img.shape[2]


@pytest.mark.slow
def test_download_model(get_tmp_data_dir):
    """
    Test that all three model (slow, medium, and fast) can be downloaded, extracted, and ran.
    """
    tmp_dir = get_tmp_data_dir()
    model_names = [
        'mask_rcnn_inception_resnet_v2_atrous_coco_2018_01_28',
        "mask_rcnn_resnet101_atrous_coco_2018_01_28",
        "mask_rcnn_inception_v2_coco_2018_01_28",
    ]
    download_base = 'http://download.tensorflow.org/models/object_detection/'

    for model_name in model_names:
        model_path = os.path.join(tmp_dir, model_name)
        download_model(download_base, model_name, model_path, extract_all=True)
        _check_model_dir(model_path)
        _check_load_model(model_path)


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
