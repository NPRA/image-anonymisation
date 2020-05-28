import numpy as np
import tensorflow as tf

import config
from src.io.file_access_guard import wait_until_path_is_found


def prepare_img(input_file):
    """
    Load the image named `filename` from `input_dir`, and check that is is valid.

    :param input_file: Path to input image
    :type input_file: tf.string
    :return: Loaded image
    :rtype: tf.python.framework.ops.EagerTensor
    """
    tf.numpy_function(wait_until_path_is_found, [input_file], tf.int32)
    img_data = tf.io.read_file(input_file)
    img = tf.image.decode_jpeg(img_data)
    img = tf.expand_dims(img, 0)

    check_input_img_tf(img)
    return img


def get_tf_dataset(tree_walker):
    """
    Create an TensorFlow dataset using the given instance of `TreeWalker`.

    :param tree_walker: TreeWalker to use to locate images.
    :type tree_walker: src.io.TreeWalker.TreeWalker
    :return: A dataset that yields properly formatted and valid image tensors.
    :rtype: tf.data.Dataset
    """
    # Generator which picks out the input file from the `src.io.TreeWalker.Paths` object
    def input_file_generator():
        for paths in tree_walker.walk():
            yield paths.input_file

    dataset = tf.data.Dataset.from_generator(
        input_file_generator,
        output_types=tf.string,
        output_shapes=[],
    )

    if config.TF_DATASET_NUM_PARALLEL_CALLS == "auto":
        num_parallel_calls = tf.data.experimental.AUTOTUNE
    else:
        num_parallel_calls = int(config.TF_DATASET_NUM_PARALLEL_CALLS)

    dataset = dataset.map(prepare_img, num_parallel_calls=num_parallel_calls)
    dataset = dataset.prefetch(num_parallel_calls)
    return dataset


@tf.function
def check_input_img_tf(img):
    tf.numpy_function(check_input_img, [img], tf.int32)


def check_input_img(img):
    """
    Check that the given image (represented as a numpy array) is valid for masking.

    :param img: Input image
    :type img: np.ndarray
    """
    assert img.ndim == 4, "Expected a 4D image tensor (batch, height, width, channel)."
    assert img.shape[0] == 1, "Batch size != 1 is currently not supported."
    assert img.shape[3] == 3, "Image must have 3 channels."
    assert (np.array(img.shape) > 0).all(), "All image dimensions must be > 0."
    assert np.isfinite(img).all(), "Got non-finite numbers in input image."
    assert ((img >= 0) & (img <= 255)).all(), "Expected all pixel-values to be in [0, ..., 255]."
    return 0
