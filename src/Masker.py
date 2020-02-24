import os
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'
import tensorflow as tf

from src import config
from src import graph_util
from src.Logger import LOGGER


class Masker:
    """
    Implements the masking functionality. Uses a pre-trained TensorFlow model to compute masks for images. Model
    configuration is done in `src.config`.
    """
    def __init__(self):
        self._init_model()

    def _init_model(self):
        """
        Initialize the TensorFlow-graph
        """
        # Download and extract model
        if not os.path.exists(config.PATH_TO_FROZEN_GRAPH):
            LOGGER.info(__name__, "Could not find the model graph file. Downloading...")
            graph_util.download_model(config.DOWNLOAD_BASE, config.MODEL_NAME, config.MODEL_PATH, extract_all=True)
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
        assert image.ndim == 4, "Expected a 4D image tensor (batch, height, width, channel)."
        assert image.shape[0] == 1, "Batch size != 1 is currently not supported."

        masking_results = self.model(tf.constant(image, tf.uint8))

        num_detections = int(masking_results["num_detections"].numpy().squeeze())
        if num_detections > 0:
            masks = masking_results["detection_masks"][0, :num_detections]
            boxes = masking_results["detection_boxes"][0, :num_detections]
            reframed_masks = reframe_box_masks_to_image_masks(masks, boxes, image.shape[1], image.shape[2])
            reframed_masks = tf.cast(reframed_masks > 0.5, tf.int32)
        else:
            reframed_masks = tf.zeros((num_detections, image.shape[1], image.shape[2]))

        masking_results = tensor_dict_to_numpy(masking_results, ignore_keys=("detection_masks", "num_detections"))
        masking_results["detection_masks"] = reframed_masks.numpy()[None, ...]
        masking_results["num_detections"] = num_detections
        return masking_results


def reframe_box_masks_to_image_masks(box_masks, boxes, image_height, image_width):
    """The default function when there are more than 0 box masks."""
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


def tensor_dict_to_numpy(input_dict, ignore_keys=tuple()):
    output_dict = {}
    for key, value in input_dict.items():
        if key not in ignore_keys and hasattr(value, "numpy"):
            output_dict[key] = value.numpy()
    return output_dict
