import os

from config import model_type


# =============================================================
# Configuration constants below. Change these at your own risk!
# =============================================================

#: Number of parallel calls to tf.dataset.map and tf.dataset.prefetch. Set `TF_DATASET_NUM_PARALLEL_CALLS = "auto"` to
#: use tf.data.experimental.AUTOTUNE. This might yield a small gain in performance.
TF_DATASET_NUM_PARALLEL_CALLS = 1

#: Actual name of the masking model. Controlled by the value of `model_type`
MODEL_NAME = {
    "Slow": "mask_rcnn_inception_resnet_v2_atrous_coco_2018_01_28",
    "Medium": "mask_rcnn_resnet101_atrous_coco_2018_01_28",
    "Fast": "mask_rcnn_inception_v2_coco_2018_01_28",
}[model_type]

# Root directory for the project
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))

# Directory containing saved models
GRAPH_DIRECTORY = os.path.join(PROJECT_ROOT, "models")

# Directory for cache files
CACHE_DIRECTORY = os.path.join(PROJECT_ROOT, "_cache")

# Full path to the saved model
MODEL_PATH = os.path.join(GRAPH_DIRECTORY, MODEL_NAME)

#: Base URL for model downloading
DOWNLOAD_BASE = 'http://download.tensorflow.org/models/object_detection/'

#: List of the strings that is used to add correct label for each box.
PATH_TO_LABELS = 'mscoco_label_map.pbtxt'

#: COCO labels to mask in input images
MASK_LABELS = (1, 2, 3, 4, 6, 8)
#: Masking colors. <COCO label id>: <RGB color>
LABEL_COLORS = {
    1: (255, 255, 255),
    2: (0, 0, 255),
    3: (255, 0, 0),
    4: (255, 255, 0),
    6: (0, 255, 255),
    8: (0, 255, 0)
}

#: Default color for labels not contained in `LABEL_COLORS`
DEFAULT_COLOR = (100, 100, 100)

#: Label map for the COCO dataset.
LABEL_MAP = {
    1: "person",
    2: "bicycle",
    3: "car",
    4: "motorcycle",
    5: "airplane",
    6: "bus",
    7: "train",
    8: "truck",
    9: "boat",
    10: "traffic light",
    11: "fire hydrant",
    13: "stop sign",
    14: "parking meter",
    15: "bench",
    16: "bird",
    17: "cat",
    18: "dog",
    19: "horse",
    20: "sheep",
    21: "cow",
    22: "elephant",
    23: "bear",
    24: "zebra",
    25: "giraffe",
    27: "backpack",
    28: "umbrella",
    31: "handbag",
    32: "tie",
    33: "suitcase",
    34: "frisbee",
    35: "skis",
    36: "snowboard",
    37: "sports ball",
    38: "kite",
    39: "baseball bat",
    40: "baseball glove",
    41: "skateboard",
    42: "surfboard",
    43: "tennis racket",
    44: "bottle",
    46: "wine glass",
    47: "cup",
    48: "fork",
    49: "knife",
    50: "spoon",
    51: "bowl",
    52: "banana",
    53: "apple",
    54: "sandwich",
    55: "orange",
    56: "broccoli",
    57: "carrot",
    58: "hot dog",
    59: "pizza",
    60: "donut",
    61: "cake",
    62: "chair",
    63: "couch",
    64: "potted plant",
    65: "bed",
    67: "dining table",
    70: "toilet",
    72: "tv",
    73: "laptop",
    74: "mouse",
    75: "remote",
    76: "keyboard",
    77: "cell phone",
    78: "microwave",
    79: "oven",
    80: "toaster",
    81: "sink",
    82: "refrigerator",
    84: "book",
    85: "clock",
    86: "vase",
    87: "scissors",
    88: "teddy bear",
    89: "hair drier",
    90: "toothbrush",
}
