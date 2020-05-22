import os
import pytest
import numpy as np

from src.io import exif_util

EXPECTED_KEYS = set(exif_util.EXIF_TEMPLATE.keys())


def test_exif_from_file(get_tmp_data_dir):
    tmp_dir = get_tmp_data_dir(subdirs=["real"])
    image_path = os.path.join(tmp_dir, "real", "Fy50_Rv003_hp01_f1_m01237.jpg")
    exif = exif_util.exif_from_file(image_path)
    assert set(exif.keys()) == EXPECTED_KEYS


def test_get_exif_bad_img(get_tmp_data_dir):
    tmp_dir = get_tmp_data_dir(subdirs=["fake"])
    image_path = os.path.join(tmp_dir, "fake", "test_2.jpg")

    exif = exif_util.exif_from_file(image_path)
    assert exif["exif_kvalitet"] == exif_util.EXIF_QUALITIES["nonexistent"]


def test_get_detected_objects_dict():
    detection_classes = np.array([6, 3, 6, 2, 6, 3, 4, 8, 8, 2, 2, 1, 6])
    expected_result = {
        "person": "1",
        "bicycle": "3",
        "car": "2",
        "motorcycle": "1",
        "bus": "4",
        "truck": "2"
    }
    objects_dict = exif_util.get_detected_objects_dict({"detection_classes": detection_classes})
    assert objects_dict == expected_result
