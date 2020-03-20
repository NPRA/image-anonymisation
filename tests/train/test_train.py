import os
from unittest import mock
from shutil import copy2, rmtree

from src.train.train_config import CarCocoConfig, TRAIN_MODELS_DIR
from src.train.train import main


class FakeArgs:
    data_folder = os.path.join("tests", "data", "train")
    data_year = ""
    summary_file = None
    resume = None
    augmentation = True

    def __call__(self, *args, **kwargs):
        return self


class FakeCarCocoConfig(CarCocoConfig):
    NAME = "test"
    STEPS_PER_EPOCH = 5
    VALIDATION_STEPS = 1


class FakeTrainConfig:
    TRAIN_MODELS_DIR = os.path.join("tests", "tmp")
    CLASS_IDS = [1, 2, 3, 4, 6, 8]
    EPOCHS = (1, 1, 0, 0)
    CarCocoConfig = FakeCarCocoConfig


def test_train():
    args = FakeArgs()
    train_config = FakeTrainConfig()

    # Copy the initial weights file to the temporary models directory.
    os.makedirs(train_config.TRAIN_MODELS_DIR)
    initial_weights_file = "mask_rcnn_coco.h5"
    copy2(os.path.join(TRAIN_MODELS_DIR, initial_weights_file),
          os.path.join(train_config.TRAIN_MODELS_DIR, initial_weights_file))

    # Run training with mocks
    with mock.patch("src.train.train.train_config", new=train_config):
        with mock.patch("src.train.train.get_args", new=args):
            trained_model_dir = main()

    # Check that the trained model's directory exists
    assert os.path.isdir(trained_model_dir), f"Could not find trained model directory at '{trained_model_dir}'."
    # Check that all weights are properly saved
    weights_filename = "mask_rcnn_test_{:04d}.h5"
    n_epochs = sum(train_config.EPOCHS)
    for epoch in range(1, n_epochs + 1):
        weights_path = os.path.join(trained_model_dir, weights_filename.format(epoch))
        assert os.path.isfile(weights_path), f"Could not find trained model weights at '{weights_path}'."
    
    # Cleanup
    rmtree(train_config.TRAIN_MODELS_DIR)
