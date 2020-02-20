"""
Configuration variables.
"""
import os


#: Root directory for the project
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
#: Directory containing saved mdoels
GRAPH_DIRECTORY = os.path.join(PROJECT_ROOT, "graphs")

#: Name of the masking model
# Slow
# MODEL_NAME = 'mask_rcnn_inception_resnet_v2_atrous_coco_2018_01_28'
# Medium
MODEL_NAME = "mask_rcnn_resnet101_atrous_coco_2018_01_28"
# Fast
# MODEL_NAME = "mask_rcnn_inception_v2_coco_2018_01_28"

#: Full path to the saved model
MODEL_PATH = os.path.join(GRAPH_DIRECTORY, MODEL_NAME)

#: Base URL for model downloading
DOWNLOAD_BASE = 'http://download.tensorflow.org/models/object_detection/'

#: Path to frozen detection graph. This is the actual model that is used for the object detection.
PATH_TO_FROZEN_GRAPH = os.path.join(MODEL_PATH, 'frozen_inference_graph.pb')

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
