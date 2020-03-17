import os

from config import PROJECT_ROOT, MODELS_DIRECTORY


CLASS_IDS = [1, 2, 3, 4, 6, 8]
DATA_DIR = os.path.join(PROJECT_ROOT, "data", "train")
COCO_DIR = os.path.join(DATA_DIR, "coco")

TRAIN_MODELS_DIR = os.path.join(MODELS_DIRECTORY, "train")