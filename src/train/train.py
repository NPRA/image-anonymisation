import os
import re
import logging
import argparse
import imgaug
import numpy as np
import tensorflow as tf

from Mask_RCNN.mrcnn.model import MaskRCNN
from Mask_RCNN.samples.coco.coco import CocoDataset
from src.train import train_config
from src.Logger import LOGGER


def get_args():
    parser = argparse.ArgumentParser(formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("--data-folder", dest="data_folder",
                        help="Path to data. The folder is expected to contain the following directories:\n"
                             "- `train`: Contains the training images\n"
                             "- `val`: (Optional) Contains the validation images\n"
                             "- `annotations`: Contains COCO-formatted .json files with annotations.\n"
                             "Training annotations should be in `annotations/instances_train.json`")
    parser.add_argument("--data-year", dest="data_year", default="",
                        help="Optional year-identifier for the data folder. The year will be appended\n"
                             " to the folder and annotation names described above.")
    parser.add_argument("--resume", dest="resume", default=None,
                        help="If specified, the training will be resumed from this weight file.")
    parser.add_argument("--summary-file", dest="summary_file", default=None,
                        help="Optional filename for writing the model summary.")
    parser.add_argument("--enable-augmentation", dest="augmentation", action="store_true",
                        help="Enable image augmentation during training?")
    return parser.parse_args()


def initialize():
    logging.basicConfig(level=logging.INFO, format=LOGGER.fmt, datefmt=LOGGER.datefmt)
    # EE has to be disabled for training
    tf.compat.v1.disable_eager_execution()

    coco_config = train_config.CarCocoConfig()
    args = get_args()
    model = MaskRCNN(mode="training", config=coco_config, model_dir=train_config.TRAIN_MODELS_DIR)

    if args.resume is not None:
        weights_path = os.path.abspath(args.resume)
        exclude_load_layers = None
    else:
        weights_path = os.path.join(train_config.TRAIN_MODELS_DIR, "mask_rcnn_coco.h5")
        # Weights for these layers are not loaded as their number of units is compatible
        # with the full COCO dataset, and not the subset we are using.
        exclude_load_layers = ["mrcnn_bbox_fc", "mrcnn_class_logits", "mrcnn_mask"]

    # Initialize weights
    session = tf.compat.v1.keras.backend.get_session()
    init = tf.compat.v1.global_variables_initializer()
    session.run(init)

    # Load weights
    LOGGER.info(__name__, f"Loading weights from '{weights_path}'")
    model.load_weights(weights_path, by_name=True, exclude=exclude_load_layers)

    # Model summary
    if args.summary_file is not None:
        with open(args.summary_file, "w") as f:
            model.keras_model.summary(print_fn=lambda s: f.write(s + "\n"))

    return args, model, coco_config


def load_datasets(args):
    # Load data
    LOGGER.info(__name__, "Loading data")
    dataset_train = CocoDataset()
    dataset_train.load_coco(args.data_folder, "train", year=args.data_year, auto_download=False,
                            class_ids=train_config.CLASS_IDS)
    dataset_train.prepare()

    # Do we have a validation dataset?
    val_path = os.path.join(args.data_folder, "val" + args.data_year)
    if os.path.isdir(val_path) and os.listdir(val_path):
        dataset_val = CocoDataset()
        dataset_val.load_coco(args.data_folder, "val", year=args.data_year, auto_download=False,
                              class_ids=train_config.CLASS_IDS)
        dataset_val.prepare()
    else:
        LOGGER.info(__name__, f"No validation dataset found at '{val_path}'")
        dataset_val = None

    return dataset_train, dataset_val


def run_training(model, coco_config, dataset_train, dataset_val, augmentation):
    # Compute cumulative epoch count
    cumulative_epochs = np.cumsum(train_config.EPOCHS)
    # Run training
    LOGGER.info(__name__, "Training unitinialized layers")
    uninitialized_layers = re.compile("mrcnn_(bbox_fc|class_logits|mask)")
    model.train(dataset_train, dataset_val,
                learning_rate=coco_config.LEARNING_RATE,
                epochs=cumulative_epochs[0],
                layers=uninitialized_layers,
                augmentation=augmentation)

    LOGGER.info(__name__, "Training network heads")
    model.train(dataset_train, dataset_val,
                learning_rate=coco_config.LEARNING_RATE,
                epochs=cumulative_epochs[1],
                layers='heads',
                augmentation=augmentation)

    # Finetune layers from ResNet stage 4 and up
    LOGGER.info(__name__, "Fine tune Resnet stage 4 and up")
    model.train(dataset_train, dataset_val,
                learning_rate=coco_config.LEARNING_RATE,
                epochs=cumulative_epochs[2],
                layers='4+',
                augmentation=augmentation)

    # # Fine tune all layers
    LOGGER.info(__name__, "Fine tune all layers")
    model.train(dataset_train, dataset_val,
                learning_rate=coco_config.LEARNING_RATE / 10,
                epochs=cumulative_epochs[3],
                layers='all',
                augmentation=augmentation)


def main():
    # Setup
    args, model, coco_config = initialize()
    dataset_train, dataset_val = load_datasets(args)
    # Image Augmentation
    if args.augmentation:
        # Right/Left flip 50% of the time
        augmentation = imgaug.augmenters.Fliplr(0.5)
    else:
        augmentation = None
    # Train
    run_training(model, coco_config, dataset_train, dataset_val, augmentation)


if __name__ == '__main__':
    main()