import os

from config import PROJECT_ROOT, MODELS_DIRECTORY
from Mask_RCNN.samples.coco.coco import CocoConfig


CLASS_IDS = [1, 2, 3, 4, 6, 8]
DATA_DIR = os.path.join(PROJECT_ROOT, "data", "train")
COCO_DIR = os.path.join(DATA_DIR, "coco")

TRAIN_MODELS_DIR = os.path.join(MODELS_DIRECTORY, "train")


class CarCocoConfig(CocoConfig):
    GPU_COUNT = 1
    IMAGES_PER_GPU = 1
    # Number of classes + background
    NUM_CLASSES = len(CLASS_IDS) + 1
    STEPS_PER_EPOCH = 1000


class CarCocoConfigInference(CarCocoConfig):
    DETECTION_MIN_CONFIDENCE = 0.9
