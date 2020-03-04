import os
import tensorflow as tf
from tensorflow.python.framework.errors_impl import InvalidArgumentError

from src.io.load import check_input_img


def prepare_img(input_dir, mirror_dirs, filename):
    input_path = tf.strings.join([input_dir, filename], separator=os.sep)
    img_data = tf.io.read_file(input_path)
    img = tf.image.decode_jpeg(img_data)
    # img = tf.cond(tf.io.is_jpeg(img_data), lambda: tf.image.decode_jpeg(img_data), lambda: tf.)
    img = tf.expand_dims(img, 0)
    check_input_img_tf(img)
    return img


def get_tf_dataset(tree_walker):
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

