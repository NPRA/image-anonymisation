import os
import time
import logging
import tensorflow as tf
from object_detection.utils import ops as utils_ops

from src import config
from src import graph_util

LOGGER = logging.getLogger(__name__)


class Masker:
    def __init__(self):
        self._init_model()

    def _init_model(self):
        # Download and extract model
        if not os.path.exists(config.PATH_TO_FROZEN_GRAPH):
            LOGGER.info("Could not find the model graph file. Downloading...")
            graph_util.download_model(config.DOWNLOAD_BASE, config.MODEL_NAME, config.MODEL_PATH)
            LOGGER.info("Model graph file downloaded.")

        self.graph = graph_util.load_graph(config.PATH_TO_FROZEN_GRAPH)
        with self.graph.as_default():
            self.width_placeholder = tf.compat.v1.placeholder(tf.int32, shape=[], name="image_width")
            self.height_placeholder = tf.compat.v1.placeholder(tf.int32, shape=[], name="image_height")
            self.input_image = self.graph.get_tensor_by_name('image_tensor:0')

            ops = self.graph.get_operations()
            all_tensor_names = {output.name for op in ops for output in op.outputs}
            self.output_tensors = {}
            for key in ['num_detections', 'detection_boxes', 'detection_scores',
                        'detection_classes', 'detection_masks']:
                tensor_name = key + ':0'
                if tensor_name in all_tensor_names:
                    self.output_tensors[key] = self.graph.get_tensor_by_name(tensor_name)
            if 'detection_masks' in self.output_tensors:
                detection_boxes = tf.squeeze(self.output_tensors['detection_boxes'], [0])
                detection_masks = tf.squeeze(self.output_tensors['detection_masks'], [0])

                # Reframe is required to translate mask from box coordinates to image coordinates and fit the image
                # size.
                real_num_detection = tf.cast(self.output_tensors['num_detections'][0], tf.int32)
                detection_boxes = tf.slice(detection_boxes, [0, 0], [real_num_detection, -1])
                detection_masks = tf.slice(detection_masks, [0, 0, 0], [real_num_detection, -1, -1])
                detection_masks_reframed = utils_ops.reframe_box_masks_to_image_masks(
                    detection_masks, detection_boxes, self.height_placeholder, self.width_placeholder)
                detection_masks_reframed = tf.cast(tf.greater(detection_masks_reframed, 0.5), tf.uint8)
                # Follow the convention by adding back the batch dimension
                self.output_tensors['detection_masks'] = tf.expand_dims(detection_masks_reframed, 0)

        self.sess = tf.compat.v1.Session(graph=self.graph)

    def mask(self, image):
        assert image.ndim == 4, "Expected a 4D image tensor (batch, height, width, channel)."
        feed_dict = {
            self.input_image: image,
            self.height_placeholder: image.shape[1],
            self.width_placeholder: image.shape[2],
        }
        out = self.sess.run(self.output_tensors, feed_dict=feed_dict)
        return out

    def close(self):
        self.sess.close()