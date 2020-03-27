"""
Configuration variables.
"""
import os


# ======================================
# Miscellaneous configuration parameters
# ======================================

#: Apply the mask to the output image?
draw_mask = True

#: Delete the original image from the input directory when the masking is completed?
delete_input = False

#: Recompute masks even though a .webp file exists in the input folder.
force_remask = False

#: When `lazy_paths = True`, traverse the file tree during the masking process.
#: Otherwise, all paths will be identified and stored before the masking starts.
lazy_paths = False

#: Number of seconds to wait before (re)trying to access a file/directory which cannot currently be reached. This
#: applies to both reading input files, and writing output files.
file_access_retry_seconds = 10

#: Total number of seconds to wait before giving up on accessing a file/directory which cannot currently be reached.
#: This also applies to both reading input files, and writing output files.
file_access_timeout_seconds = 60

#: Format of datetime identifiers. See https://docs.python.org/3.7/library/datetime.html#strftime-strptime-behavior for
#: more information.
datetime_format = "%Y-%m-%d %H.%M.%S"

#: Name of the log file. `{datetime}` will be replaced with a timestamp formatted as `datetime_format`. {hostname}
#: will be replaced with the host name.
log_file_name = "{datetime} {hostname}.log"

#: If the program exits due to an ungaught exception, an email will be sent to this address.
#: Set `uncaught_exception_email = None` to disable this feature.
uncaught_exception_email = None


# ===================
# File I/O parameters
# ===================

#: Write the EXIF .json file to the output (remote) directory?
remote_json = True

#: Write the EXIF .json file to the input (local) directory?
local_json = False

#: Write the EXIF .json file to the archive directory?
archive_json = False

#: Write mask file to the output (remote) directory?
remote_mask = True

#: Write the mask file to the input (local) directory?
local_mask = False

#: Write mask file to the archive directory?
archive_mask = False


# ================================
# Parameters for the masking model
# ================================

#: Type of masking model. Currently, there are three available models with varying speed and accuracy.
#: The slowest model produces the most accurate masks, while the masks from the medium model are slightly worse.
#: The masks from the `Fast` model are currently not recommended due to poor quality. Must be either "Slow", "Medium" or
#: "Fast". "Medium" is recommended.
model_type = "Medium"

#: Approximate number of pixels for mask dilation. This will help ensure that an identified object is completely covered
#: by the corresponding mask. Set `mask_dilation_pixels = 0` to disable mask dilation.
mask_dilation_pixels = 0

# ===============================================================
# Parameters controlling the appearance of the anonymised regions
# ===============================================================

#: "RGB tuple [0-255] indicating the masking color. Setting this option will override the
#: colors specified below. Example: Setting `mask_color = (50, 50, 50)` will make all masks
#: dark gray.
mask_color = None

#: Blurring coefficient [1-100] which specifies the degree of blurring to apply within the
#: mask. When this parameter is specified, the image will be blurred, and not masked with a
#: specific color. Set `blur = None` to disable blurring, and use colored masks instead.
blur = 10

#: Convert the image to grayscale before blurring? (Ignored if blurring is disabled)
gray_blur = True

#: Normalize the gray level within each mask after blurring? This will make bright colors indistinguishable from dark
#: colors. NOTE: Requires gray_blur=True
normalized_gray_blur = True

#: Masking model weights. This weights file should be a result from a training run. The file should be placed in the
#: `models` directory.
weights_file = "mask_rcnn_car_coco.h5"


# =============================================================
# Configuration constants below. Change these at your own risk!
# =============================================================

#: Number of parallel calls to tf.dataset.map and tf.dataset.prefetch. Set `TF_DATASET_NUM_PARALLEL_CALLS = "auto"` to
#: use tf.data.experimental.AUTOTUNE. This might yield a small gain in performance.
TF_DATASET_NUM_PARALLEL_CALLS = 1

#: Root directory for the project
PROJECT_ROOT = os.path.dirname(os.path.realpath(__file__))

#: Directory containing saved models
MODELS_DIRECTORY = os.path.join(PROJECT_ROOT, "models")
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
