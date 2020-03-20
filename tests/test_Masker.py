import os
import numpy as np
import tensorflow as tf
from PIL import Image

from src.Masker import Masker
from config import LABEL_MAP

LABEL_MAP_FLIPPED = {value: key for key, value in LABEL_MAP.items()}
IMG_DIR = os.path.join("tests", "data", "objects")


def test_Masker():
    masker = Masker()
    img = tf.zeros((1, 1018, 2703, 3), dtype=tf.uint8)
    results = masker.mask(img)

    assert "num_detections" in results
    assert "detection_boxes" in results
    assert "detection_masks" in results
    assert "detection_classes" in results
    assert "detection_scores" in results

    mask_shape = results["detection_masks"].shape
    assert mask_shape[2] == img.shape[1]
    assert mask_shape[3] == img.shape[2]


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

        found_objects = list(mask_results["detection_classes"][0].astype(int))
        for object_name in expected_objects:
            class_id = LABEL_MAP_FLIPPED[object_name]
            assert class_id in found_objects, f"Expected object '{object_name}' to be found in image '{image_path}'." \
                                              f" Found classes {found_objects} = " \
                                              f"{[LABEL_MAP[o] for o in found_objects]} instead."
