import os
import tensorflow as tf

from src.io.load import check_input_img


def prepare_img(input_dir, _, filename):
    """
    Load the image named `filename` from `input_dir`, and check that is is valid.

    :param input_dir: Input directory. Expected to be a zero-dimensional string tensor.
    :type input_dir: tf.python.framework.ops.EagerTensor
    :param _: Ignored
    :type _: tf.python.framework.ops.EagerTensor
    :param filename: Name of image file. Expected to be a zero-dimensional string tensor.
    :type filename: tf.python.framework.ops.EagerTensor
    :return: Loaded image
    :rtype: tf.python.framework.ops.EagerTensor
    """
    input_path = tf.strings.join([input_dir, filename], separator=os.sep)
    img_data = tf.io.read_file(input_path)
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
    dataset = tf.data.Dataset.from_generator(
        tree_walker.walk,
        output_types=(tf.string, tf.string, tf.string),
        output_shapes=([], [None], []),
    )
    dataset = dataset.map(prepare_img, num_parallel_calls=tf.data.experimental.AUTOTUNE)
    dataset = dataset.prefetch(tf.data.experimental.AUTOTUNE)
    return dataset


@tf.function
def check_input_img_tf(img):
    tf.numpy_function(check_input_img, [img], tf.int32)

