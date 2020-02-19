"""
Configuration variables.
"""
import os


PROJECT_ROOT = r"C:\Users\dantro\Repos\image-anonymisation"
GRAPH_DIRECTORY = os.path.join(PROJECT_ROOT, "graphs")

MODEL_NAME = 'mask_rcnn_inception_resnet_v2_atrous_coco_2018_01_28'
# MODEL_NAME = 'mask_rcnn_inception_v2_coco_2018_01_28'
# MODEL_NAME = 'mask_rcnn_inception_resnet_v2_atrous_coco_2018_01_28'
# MODEL_NAME = 'ssd_mobilenet_v1_coco_2017_11_17'
MODEL_PATH = os.path.join(GRAPH_DIRECTORY, MODEL_NAME)

DOWNLOAD_BASE = 'http://download.tensorflow.org/models/object_detection/'

# Path to frozen detection graph. This is the actual model that is used for the object detection.
PATH_TO_FROZEN_GRAPH = os.path.join(MODEL_PATH, 'frozen_inference_graph.pb')

# List of the strings that is used to add correct label for each box.
PATH_TO_LABELS = 'mscoco_label_map.pbtxt'

# COCO labels to mask in input images
MASK_LABELS = (1, 2, 3, 4, 6, 8)

# Masking colors <label id>: <RGB color>
DEFAULT_COLOR = (100, 100, 100)
LABEL_COLORS = {
    1: (255, 255, 255),
    2: (0, 0, 255),
    3: (255, 0, 0),
    4: (255, 255, 0),
    6: (0, 255, 255),
    8: (0, 255, 0)
}
