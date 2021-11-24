import os
import tensorflow as tf
import numpy as np
import tarfile
import cv2

import config
from src.Logger import LOGGER


class Masker:
    """
    Implements the masking functionality. Uses a pre-trained TensorFlow model to compute masks for images. Model
    configuration is done in `config`.

    :param mask_dilation_pixels: Approximate number of pixels for mask dilation. This will help ensure that an
                                 identified object is completely covered by the corresponding mask. Set
                                 `mask_dilation_pixels = 0` to disable mask dilation.
    :type mask_dilation_pixels: int
    :param max_num_pixels: Maximum number of pixels in images to be processed by the masking model. If the number of
                           pixels exceeds this value, it will be resized before the masker is applied. This will NOT
                           change the resolution of the output image.
    :type max_num_pixels: int
    """

    def __init__(self, mask_dilation_pixels=0, max_num_pixels=10000):
        self.mask_dilation_pixels = mask_dilation_pixels
        self.max_num_pixels = int(max_num_pixels)
        self._init_model()

    def _init_model(self):
        """
        Initialize the TensorFlow-graph
        """
        saved_model_path = os.path.join(config.MODEL_PATH, "saved_model")
        # Download and extract model

        if not os.path.exists(saved_model_path):
            LOGGER.info(__name__, "Could not find the model graph file. Downloading...")
            download_model(config.DOWNLOAD_BASE, config.MODEL_NAME, config.MODEL_PATH, extract_all=True)
            LOGGER.info(__name__, "Model graph file downloaded.")

        model = tf.saved_model.load(saved_model_path)
        self.model = model.signatures["serving_default"]

    def mask(self, image):
        """
        Run the masking on `image`.
        
        :param image: Input image. Must be a 4D color image tensor with shape (1, height, width, 3)
        :type image: tf.python.framework.ops.EagerTensor
        :return: Dictionary containing masking results. Content depends on the model used.
        :rtype: dict
        """
        # Original image shape
        image_shape = image.shape
        # Resize the image if it is too large
        image = _maybe_resize_image(image, self.max_num_pixels)
        # Get results from model
        #LOGGER.debug(__name__, f"Before masking in masker")

        masking_results = self.model(image)
        #LOGGER.debug(__name__, f"After masking in masker")
        # Remove "uninteresting" detections. I.e. detections which are not relevant for anonymisation.
        masking_results = _filter_detections(masking_results)
        # Convert the number of detections to an int
        num_detections = masking_results["num_detections"].numpy().squeeze()
        # print(f"boxes?? {masking_results}")
        # Convert masks from normalized bbox coordinates to whole-image coordinates.
        reframed_masks = reframe_box_masks_to_image_masks(masking_results["detection_masks"][0],
                                                          masking_results["detection_boxes"][0],
                                                          image_shape[1], image_shape[2])
        # Convert the tf.Tensors to numpy-arrays
        masking_results = tensor_dict_to_numpy(masking_results, ignore_keys=("detection_masks", "num_detections"))
        masking_results["detection_masks"] = (reframed_masks.numpy()[None, ...] > 0.5)
        masking_results["num_detections"] = num_detections

        # Dilate masks?
        if self.mask_dilation_pixels > 0:
            dilate_masks(masking_results, self.mask_dilation_pixels)

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


def dilate_masks(mask_results, mask_dilation_pixels):
    masks = mask_results["detection_masks"]
    kernel_size = 2 * mask_dilation_pixels + 1
    kernel = np.ones((kernel_size, kernel_size)).astype(np.uint8)

    for i in range(int(mask_results["num_detections"])):
        mask = (masks[0, i, :, :] > 0).astype(np.uint8)
        masks[0, i, :, :] = cv2.dilate(mask, kernel, iterations=1).astype(bool)


def download_model(download_base, model_name, model_path, extract_all=False):
    """
    Download a pre-trained model.

    :param download_base: Base URL for downloading
    :type download_base: str
    :param model_name: Name of model-file (without the .tar.gz extension)
    :type model_name: str
    :param model_path: Directory where the downloaded model shoud be stored.
    :type model_path: str
    :param extract_all: When True, all files in the .tar.gz archive will be extracted. Otherwise, just extract
                        "frozen_inference_graph.pb"
    :type extract_all: bool
    """
    os.makedirs(model_path, exist_ok=True)

    tf.keras.utils.get_file(model_path + ".tar.gz", download_base + model_name + ".tar.gz")
    tar_file = tarfile.open(model_path + '.tar.gz')

    if extract_all:
        tar_file.extractall(os.path.dirname(model_path))
    else:
        os.makedirs(model_path, exist_ok=True)

        for file in tar_file.getmembers():
            file_name = os.path.basename(file.name)
            if 'frozen_inference_graph.pb' in file_name:
                tar_file.extract(file, os.path.dirname(model_path))
    tar_file.close()


@tf.function
def _maybe_resize_image(img, max_num_pixels):
    shape = tf.shape(img)

    def true_fn():
        h, w, = tf.cast(shape[1], tf.int64), tf.cast(shape[2], tf.int64)
        new_w = tf.cast(tf.sqrt(max_num_pixels * w / h), dtype=tf.int64)
        new_h = tf.cast(new_w * h / w, dtype=tf.int64)
        resized = tf.image.resize(img, (new_h, new_w), method=tf.image.ResizeMethod.BILINEAR)
        return tf.cast(resized, tf.uint8)

    def false_fn():
        return img

    return tf.cond(shape[1] * shape[2] > max_num_pixels, true_fn, false_fn)


def _filter_detections_numpy(num_detections, classes, scores, boxes, masks):
    """
    Remove detections which are not in `config.MASK_LABELS`.

    :param num_detections: Number of detections from model
    :type num_detections: int
    :param classes: Detected classes
    :type classes: np.ndarray
    :param scores: Detection scores
    :type scores: np.ndarray
    :param boxes: Detection bounding boxes
    :type boxes: np.ndarray
    :param masks: Detection masks
    :type masks: np.ndarray
    :return: A tuple of five arrays corresponding to each element in the input arguments, where the detections whose
             class is not in `config.MASK_LABELS` have been removed.
    :rtype: np.ndarray
    """
    class_mask = np.isin(classes[0], config.MASK_LABELS)
    class_mask[int(num_detections[0]):] = False
    num_detections = int(class_mask.sum())
    classes = classes[:, class_mask].astype(np.int32)
    scores = scores[:, class_mask].astype(np.float32)
    boxes = boxes[:, class_mask].astype(np.float32)
    masks = masks[:, class_mask].astype(np.float32)
    return num_detections, classes, scores, boxes, masks


@tf.function
def _filter_detections(masking_results):
    """
    TensorFlow wrapper for `_filter_detections_numpy`. Executes the function on the tensors in `masking_results`.

    :param masking_results: Result from masking model.
    :type masking_results: dict
    :return: Filtered results. Same format as `masking_results`.
    :rtype: dict
    """
    result_keys = ["num_detections", "detection_classes", "detection_scores", "detection_boxes", "detection_masks"]
    output_types = [tf.int32, tf.int32, tf.float32, tf.float32, tf.float32]
    input_tensors = [masking_results[k] for k in result_keys]
    filtered_tensors = tf.numpy_function(_filter_detections_numpy, inp=input_tensors, Tout=output_types)
    filtered_results = dict(zip(result_keys, filtered_tensors))
    return filtered_results


def reframe_box_masks_to_image_masks(box_masks, boxes, image_height, image_width):
    """
    From: https://github.com/tensorflow/models/blob/master/research/object_detection/utils/ops.py

    Transforms the box masks back to full image masks.
    Embeds masks in bounding boxes of larger masks whose shapes correspond to
    image shape.

    :param box_masks: A tf.float32 tensor of size [num_masks, mask_height, mask_width].
    :type box_masks: tf.python.framework.ops.EagerTensor
    :param boxes: A tf.float32 tensor of size [num_masks, 4] containing the box
                  corners. Row i contains [ymin, xmin, ymax, xmax] of the box
                  corresponding to mask i. Note that the box corners are in
                  normalized coordinates.
    :type boxes: tf.python.framework.ops.EagerTensor
    :param image_height: Image height. The output mask will have the same height as
                         the image height.
    :type image_height: int
    :param image_width: Image width. The output mask will have the same width as the
                        image width.
    :type image_width: int
    :return: A tf.float32 tensor of size [num_masks, image_height, image_width].
    :rtype: tf.python.framework.ops.EagerTensor
    """
    def reframe_box_masks_to_image_masks_default():
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
        return tf.image.crop_and_resize(
            image=box_masks_expanded,
            boxes=reverse_boxes,
            box_indices=tf.range(num_boxes),
            crop_size=[image_height, image_width],
            extrapolation_value=0.0)

    image_masks = tf.cond(
        tf.shape(box_masks)[0] > 0,
        reframe_box_masks_to_image_masks_default,
        lambda: tf.zeros([0, image_height, image_width, 1], dtype=tf.float32))
    return tf.squeeze(image_masks, axis=3)
