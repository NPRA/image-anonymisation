"""
Utility functions for loading pre-trained TensorFlow models (graphs).
"""
import os
import tarfile
import tensorflow as tf


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
