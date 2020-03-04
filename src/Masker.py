import os
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'
import tensorflow as tf
import numpy as np
import tarfile

import config
from src.Logger import LOGGER


class Masker:
    """
    Implements the masking functionality. Uses a pre-trained TensorFlow model to compute masks for images. Model
    configuration is done in `config`.
    """
    def __init__(self):
        self._init_model()

    def _init_model(self):
        """
        Initialize the TensorFlow-graph
        """
        # Download and extract model
        if not os.path.exists(config.MODEL_PATH):
            LOGGER.info(__name__, "Could not find the model graph file. Downloading...")
            download_model(config.DOWNLOAD_BASE, config.MODEL_NAME, config.MODEL_PATH, extract_all=True)
            LOGGER.info(__name__, "Model graph file downloaded.")

        model = tf.saved_model.load(os.path.join(config.MODEL_PATH, "saved_model"))
        self.model = model.signatures["serving_default"]

    def mask(self, image):
        """
        Run the masking on `image`.
        :param image: Input image. Must be a 4D color image array with shape (1, height, width, 3)
        :type image: np.ndarray
        :return: Dictionary containing masking results. Content depends on the model used.
        :rtype: dict
        """
        masking_results = self.model(image)
        num_detections = masking_results["num_detections"].numpy().squeeze()
        reframed_masks = _reframe_masks(masking_results, tf.constant(image.shape, tf.int32))

        masking_results = tensor_dict_to_numpy(masking_results, ignore_keys=("detection_masks", "num_detections"))
        masking_results["detection_masks"] = reframed_masks.numpy()[None, ...]
        masking_results["num_detections"] = num_detections
        return masking_results


def tensor_dict_to_numpy(input_dict, ignore_keys=tuple()):
    """
    Convert all values of type `tf.Tensor` in a dictionary to `np.ndarray` by calling the `.numpy()` method.

    :param input_dict: Dictionary containing tensors to convert.
    :type input_dict: dict
    :param ignore_keys: Optional iterable with keys to ignore
    :type ignore_keys: tuple | list
    :return: Converted dictionary containing original keys and converted tensors. Keys in `ignore_keys` will not be
             included.
    :rtype: dict
    """
    output_dict = {}
    for key, value in input_dict.items():
        if key not in ignore_keys:
            if hasattr(value, "numpy"):
                output_dict[key] = value.numpy()
            else:
                output_dict[key] = value
    return output_dict


def download_model(download_base, model_name, model_path, extract_all=False):
    """
    Download a pre-trained model.

    :param download_base: Base URL for downloading
    :type download_base: str
    :param model_name: Name of model-file (without the .tar.gz extension)
    :type model_name: str
    :param model_path: Directory where the downloaded model shoud be stored.
    :type model_path: str
    """
    os.makedirs(model_path, exist_ok=True)

    tf.keras.utils.get_file(model_path + ".tar.gz", download_base + model_name + ".tar.gz")
    tar_file = tarfile.open(model_path + '.tar.gz')

    if extract_all:
        tar_file.extractall(os.path.dirname(model_path))
    else:
        if not os.path.isdir(model_path):
            os.makedirs(model_path)

        for file in tar_file.getmembers():
            file_name = os.path.basename(file.name)
            if 'frozen_inference_graph.pb' in file_name:
                tar_file.extract(file, os.path.dirname(model_path))
    tar_file.close()


@tf.function
def _reframe_masks(masking_results, image_shape):
    num_detections = tf.cast(tf.squeeze(masking_results["num_detections"]), tf.int32)
    if num_detections > 0:
        masks = masking_results["detection_masks"][0, :num_detections]
        boxes = masking_results["detection_boxes"][0, :num_detections]
        reframed_masks = _reframe_box_masks_to_image_masks(masks, boxes, image_shape[1], image_shape[2])
        reframed_masks = tf.cast(reframed_masks > 0.5, tf.int32)
    else:
        reframed_masks = tf.zeros((num_detections, image_shape[1], image_shape[2]), dtype=tf.int32)
    return reframed_masks


@tf.function
def _reframe_box_masks_to_image_masks(box_masks, boxes, image_height, image_width):
    """
    Convert from box-masks to image-masks. Adapted from
    https://github.com/tensorflow/models/blob/master/research/object_detection/utils/ops.py

    :param box_masks: Masks for each box.
    :type box_masks: tf.Tensor
    :param boxes: Box coordinates. The coordinates should be relative to image size
    :type boxes: tf.Tensor.
    :param image_height: Height of image
    :type image_height: int
    :param image_width: Width of image
    :type image_width: int
    :return: Whole-image masks
    :rtype: tf.Tensor
    """
    def transform_boxes_relative_to_boxes(boxes, reference_boxes):
        boxes = tf.reshape(boxes, [-1, 2, 2])
        min_corner = tf.expand_dims(reference_boxes[:, 0:2], 1)
        max_corner = tf.expand_dims(reference_boxes[:, 2:4], 1)
        transformed_boxes = (boxes - min_corner) / (max_corner - min_corner)
        return tf.reshape(transformed_boxes, [-1, 4])

    box_masks_expanded = tf.expand_dims(box_masks, axis=3)
    num_boxes = tf.shape(box_masks_expanded)[0]
    unit_boxes = tf.concat(
        [tf.zeros([num_boxes, 2]), tf.ones([num_boxes, 2])], axis=1)
    reverse_boxes = transform_boxes_relative_to_boxes(unit_boxes, boxes)

    reframed = tf.image.crop_and_resize(
        image=box_masks_expanded,
        boxes=reverse_boxes,
        box_indices=tf.range(num_boxes),
        crop_size=[image_height, image_width],
        extrapolation_value=0.0)
    reframed = tf.squeeze(reframed, axis=3)
    return reframed


