import os
import re
import logging
import argparse
import numpy as np
import tensorflow as tf

from Mask_RCNN.mrcnn.model import MaskRCNN
from Mask_RCNN.samples.coco.coco import CocoDataset
from src.train import train_config
from src.train.CityScapesDataset import CityScapeDataset
from src.train.augmentation import get_agumentations
from src.Logger import LOGGER


def get_args():
    """ Get the command-line arguments. """
    parser = argparse.ArgumentParser(formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("--data-type", dest="data_type",
                        help="Type of dataset. Must be either `coco` or `cityscapes`.")

    parser.add_argument("--data-folder", dest="data_folder",
                        help="Path to the data folder.\n"
                             "The folder is expected to contain the following directories:\n"
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
    """
    Initialize the training procedure

    :return: Command line arguments, masking model, and the masking model's config.
    :rtype: (argparse.Namespace, MaskRcnn, train_config.CarCocoConfig)
    """
    logging.basicConfig(level=logging.INFO, format=LOGGER.fmt, datefmt=LOGGER.datefmt)
    # EE has to be disabled for training
    tf.compat.v1.disable_eager_execution()

    args = get_args()
    if args.data_type == "coco":
        model_config = train_config.CarCocoConfig()
    elif args.data_type == "cityscapes":
        model_config = train_config.CityScapesConfig()
    else:
        raise ValueError(f"Got invalid data type '{args.data_type}'")

    model = MaskRCNN(mode="training", config=model_config, model_dir=train_config.TRAIN_MODELS_DIR)

    if args.resume is not None:
        weights_path = os.path.abspath(args.resume)
        exclude_load_layers = None
    else:
        if args.data_type == "coco":
            # Load pre-trained COCO-weights
            weights_path = os.path.join(train_config.TRAIN_MODELS_DIR, "mask_rcnn_coco.h5")
            # Weights for these layers are not loaded as their number of units is compatible
            # with the full COCO dataset, and not the subset we are using.
            exclude_load_layers = ["mrcnn_bbox_fc", "mrcnn_class_logits", "mrcnn_mask"]
        else:
            # Load pre-trained ImageNet weights
            weights_path = os.path.join(train_config.TRAIN_MODELS_DIR,
                                        "resnet50_weights_tf_dim_ordering_tf_kernels_notop.h5")
            exclude_load_layers = None

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

    return args, model, model_config


def load_coco_datasets(args):
    dataset_train = CocoDataset()
    dataset_train.load_coco(args.data_folder, "train", year=args.data_year, auto_download=False,
                            class_ids=train_config.COCO_CLASS_IDS)
    dataset_train.prepare()

    # Do we have a validation dataset?
    val_path = os.path.join(args.data_folder, "val" + args.data_year)
    if os.path.isdir(val_path) and os.listdir(val_path):
        dataset_val = CocoDataset()
        dataset_val.load_coco(args.data_folder, "val", year=args.data_year, auto_download=False,
                              class_ids=train_config.COCO_CLASS_IDS)
        dataset_val.prepare()
    else:
        LOGGER.info(__name__, f"No validation dataset found at '{val_path}'")
        dataset_val = None

    return dataset_train, dataset_val


def load_cityscapes_datasets(args):
    image_dir = os.path.join(args.data_folder, "images")
    annotation_dir = os.path.join(args.data_folder, "annotations")

    dataset_train = CityScapeDataset()
    dataset_train.load_cityscapes(image_dir=image_dir, annotation_dir=annotation_dir, subset="train")
    dataset_train.prepare()

    val_path = os.path.isdir(os.path.join(image_dir, "val"))
    if val_path:
        dataset_val = CityScapeDataset()
        dataset_val.load_cityscapes(image_dir=image_dir, annotation_dir=annotation_dir, subset="val")
        dataset_val.prepare()
    else:
        LOGGER.info(__name__, f"No validation images found at '{val_path}'")
        dataset_val = None

    return dataset_train, dataset_val


def load_datasets(args):
    """
    Load the training and validation datasets. These are represented as `CocoDataset`s from Mask_RCNN.

    :param args: Command line arguments
    :type args: argparse.Namespace
    :return: Training and validation datasets. If the data directory does not have a `val` subdirectory, the validation
             dataset will be None
    :rtype: (CocoDataset, CocoDataset | None)
    """
    # Load data
    LOGGER.info(__name__, "Loading data")
    if args.data_type == "coco":
        return load_coco_datasets(args)
    elif args.data_type == "cityscapes":
        return load_cityscapes_datasets(args)
    else:
        raise ValueError(f"Got invalid data type '{args.data_type}'")


def run_training(model, model_config, dataset_train, dataset_val, augmentation):
    """
    Trains `model` on `dataset_train`

    :param model: Model to train
    :type model: MaskRCNN
    :param model_config: The model's config
    :type model_config: train_config.CarCocoConfig | train_config.CityScapesConfig
    :param dataset_train: Training dataset
    :type dataset_train: CocoDataset
    :param dataset_val: Validation dataset. If None, the training will be performed without validation data.
    :type dataset_val: CocoDataset | None
    :param augmentation: Use image augmentation in training?
    :type augmentation: bool
    """
    # Compute cumulative epoch count
    cumulative_epochs = np.cumsum(train_config.EPOCHS)
    # Run training
    LOGGER.info(__name__, "Training unitinialized layers")
    uninitialized_layers = re.compile("mrcnn_(bbox_fc|class_logits|mask)")
    model.train(dataset_train, dataset_val,
                learning_rate=model_config.LEARNING_RATE,
                epochs=cumulative_epochs[0],
                layers=uninitialized_layers,
                augmentation=augmentation)

    LOGGER.info(__name__, "Training network heads")
    model.train(dataset_train, dataset_val,
                learning_rate=model_config.LEARNING_RATE,
                epochs=cumulative_epochs[1],
                layers='heads',
                augmentation=augmentation)

    # Finetune layers from ResNet stage 4 and up
    LOGGER.info(__name__, "Fine tune Resnet stage 4 and up")
    model.train(dataset_train, dataset_val,
                learning_rate=model_config.LEARNING_RATE,
                epochs=cumulative_epochs[2],
                layers='4+',
                augmentation=augmentation)

    # # Fine tune all layers
    LOGGER.info(__name__, "Fine tune all layers")
    model.train(dataset_train, dataset_val,
                learning_rate=model_config.LEARNING_RATE / 10,
                epochs=cumulative_epochs[3],
                layers='all',
                augmentation=augmentation)


def main():
    """
    Initialize the training process and run training.

    :return: Path to the resulting trained weights
    :rtype: str
    """
    # Setup
    args, model, model_config = initialize()
    dataset_train, dataset_val = load_datasets(args)
    # Image Augmentation
    if args.augmentation:
        # Image augmentations
        augmentation = get_agumentations()
    else:
        augmentation = None
    # Train
    run_training(model, model_config, dataset_train, dataset_val, augmentation)
    return model.log_dir


if __name__ == '__main__':
    main()
