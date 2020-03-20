import os

from config import PROJECT_ROOT, MODELS_DIRECTORY
from Mask_RCNN.samples.coco.coco import CocoConfig

# Paths
DATA_DIR = os.path.join(PROJECT_ROOT, "data", "train")
COCO_DIR = os.path.join(DATA_DIR, "coco")
TRAIN_MODELS_DIR = os.path.join(MODELS_DIRECTORY, "train")

# COCO labels to use in training
CLASS_IDS = [1, 2, 3, 4, 6, 8]
# Number of epochs for each training stage
EPOCHS = (5, 5, 5, 5)


class CarCocoConfig(CocoConfig):
    NAME = "car_coco"
    GPU_COUNT = 1
    IMAGES_PER_GPU = 1
    NUM_CLASSES = len(CLASS_IDS) + 1
    STEPS_PER_EPOCH = 1000


class CarCocoConfigInference(CarCocoConfig):
    DETECTION_MIN_CONFIDENCE = 0.7
    # IMAGE_RESIZE_MODE = "none"
