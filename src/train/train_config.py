import os

from config import MODELS_DIRECTORY
from Mask_RCNN.samples.coco.coco import CocoConfig

#: Path to base directory for trained models
TRAIN_MODELS_DIR = os.path.join(MODELS_DIRECTORY, "train")

#: COCO labels to use in training
CLASS_IDS = [1, 2, 3, 4, 6, 8]
#: Number of epochs for each training stage
EPOCHS = (3, 3, 5, 5)


class CarCocoConfig(CocoConfig):
    """ Training configuration class for the Mask R-CNN model. """
    #: Name of the model
    NAME = "car_coco"
    #: Number of GPUs to use
    GPU_COUNT = 1
    #: Number of images simultaneously processed by each GPU
    IMAGES_PER_GPU = 1
    #: Number of classes in the dataset
    NUM_CLASSES = len(CLASS_IDS) + 1
    #: Number of steps (batches) in each epoch.
    STEPS_PER_EPOCH = 1000
    #: Backbone network. Must be either 'resnet50' or 'resnet101'
    BACKBONE = "resnet101"


class CarCocoConfigInference(CarCocoConfig):
    """ Inference configuration for the Mask R-CNN model. """
    #: Minimum confidence for a detection to be included in the results.
    DETECTION_MIN_CONFIDENCE = 0.7
