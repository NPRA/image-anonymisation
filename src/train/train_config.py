import os

from config import MODELS_DIRECTORY
from Mask_RCNN.samples.coco.coco import CocoConfig

#: Path to base directory for trained models
TRAIN_MODELS_DIR = os.path.join(MODELS_DIRECTORY, "train")

#: Number of epochs for each training stage
EPOCHS = (0, 5, 200, 0)


# ===============================
# Configuration for COCO training
# ===============================

#: COCO labels to use in training
COCO_CLASS_IDS = [1, 2, 3, 4, 6, 8]


class CarCocoConfig(CocoConfig):
    """ Training configuration class for the Mask R-CNN model. """
    #: Name of the model
    NAME = "car_coco"
    #: Number of GPUs to use
    GPU_COUNT = 1
    #: Number of images simultaneously processed by each GPU
    IMAGES_PER_GPU = 1
    #: Number of classes in the dataset
    NUM_CLASSES = len(COCO_CLASS_IDS) + 1
    #: Number of steps (batches) in each epoch.
    STEPS_PER_EPOCH = 100
    #: Backbone network. Must be either 'resnet50' or 'resnet101'
    BACKBONE = "resnet101"

    # WEIGHT_DECAY = 0.0001
    WEIGHT_DECAY = 0.0
    VALIDATION_STEPS = 10
    IMAGE_MIN_DIM = 512
    IMAGE_MAX_DIM = 704


class CarCocoConfigInference(CarCocoConfig):
    """ Inference configuration for the Mask R-CNN model. """
    #: Minimum confidence for a detection to be included in the results.
    DETECTION_MIN_CONFIDENCE = 0.7


# =====================================
# Configuration for Cityscapes training
# =====================================

#: Cityscapes labels to use in training
CITYSCAPES_CLASS_IDS = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]


class CityScapesConfig(CocoConfig):
    #: Name of the model
    NAME = "cityscapes"
    #: Number of GPUs to use
    GPU_COUNT = 1
    #: Number of images simultaneously processed by each GPU
    IMAGES_PER_GPU = 1
    #: Number of classes in the dataset
    NUM_CLASSES = len(CITYSCAPES_CLASS_IDS) + 1
    #: Number of steps (batches) in each epoch.
    STEPS_PER_EPOCH = 100
    #: Backbone network. Must be either 'resnet50' or 'resnet101'
    BACKBONE = "resnet50"

    WEIGHT_DECAY = 0


class CityScapesConfigInference(CityScapesConfig):
    """ Inference configuration for the Mask R-CNN model. """
    #: Minimum confidence for a detection to be included in the results.
    DETECTION_MIN_CONFIDENCE = 0.7