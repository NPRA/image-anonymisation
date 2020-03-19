import tensorflow as tf

from src.Masker import Masker


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


# TODO: Performance check on small QA dataset.
