import os
import tensorflow as tf

import config
from src.io.load import check_input_img
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

