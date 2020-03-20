import os
import numpy as np
import tensorflow as tf
from PIL import Image

from src.Masker import Masker
from config import LABEL_MAP

LABEL_MAP_FLIPPED = {value: key for key, value in LABEL_MAP.items()}
IMG_DIR = os.path.join("tests", "data", "objects")


def _check_detections_are_valid(results, image_shape):
    assert "num_detections" in results
    num_detections = int(results["num_detections"])

    expected_shapes = {
        "detection_boxes": (1, num_detections, 4),
        "detection_classes": (1, num_detections),
        "detection_scores": (1, num_detections),
        "detection_masks": (1, num_detections, image_shape[0], image_shape[1])
    }

    for key, expected_shape in expected_shapes.items():
        assert key in results, f"Could not find key '{key}' in mask_results."
        assert results[key].shape == expected_shape, f"Expected mask_results['{key}'] to have shape {expected_shape}," \
                                                     f"but got shape {results[key].shape} instead."


def test_Masker():
    masker = Masker()
    img = tf.zeros((1, 1018, 2703, 3), dtype=tf.uint8)
    results = masker.mask(img)
    _check_detections_are_valid(results, img.shape[1:])


def test_masker_finds_objects():
    object_files = [
        ("bus.jpg", ["bus"]),
        ("car.jpg", ["car"]),
        ("motorcycle.jpg", ["motorcycle"]),
        ("person_1.jpg", ["person"]),
        ("person_2.jpg", ["person"]),
    ]

    masker = Masker()

    for filename, expected_objects in object_files:
        image_path = os.path.join(IMG_DIR, filename)
        img = np.array(Image.open(image_path))[None, ...]
        mask_results = masker.mask(img)
        _check_detections_are_valid(mask_results, img.shape[1:])

        found_objects = list(mask_results["detection_classes"][0].astype(int))
        for object_name in expected_objects:
            class_id = LABEL_MAP_FLIPPED[object_name]
            assert class_id in found_objects, f"Expected object '{object_name}' to be found in image '{image_path}'." \
                                              f" Found classes {found_objects} = " \
                                              f"{[LABEL_MAP[o] for o in found_objects]} instead."
