import os
import numpy as np
from PIL import Image
import matplotlib
import cv2

# os.environ["CUDA_VISIBLE_DEVICES"] = "-1"

from Mask_RCNN.mrcnn import visualize
from Mask_RCNN.mrcnn.model import MaskRCNN
import src.train.config as train_config
from src.Logger import LOGGER

matplotlib.use('TkAgg')

WEIGHTS_FILE = os.path.join(train_config.TRAIN_MODELS_DIR, "coco20200318T1404", "mask_rcnn_coco_0001.h5")
RESULTS_KEYMAP = {
    "detection_boxes": "rois",
    "detection_classes": "class_ids",
    "detection_scores": "scores",
    "detection_masks": "masks"
}


class Masker:
    def __init__(self):
        LOGGER.info(__name__, "Initializing Mask R-CNN model")
        self.coco_config = train_config.CarCocoConfigInference()
        self.model = MaskRCNN(mode="inference", config=self.coco_config, model_dir=train_config.TRAIN_MODELS_DIR)

        LOGGER.info(__name__, f"Loading weights from file '{WEIGHTS_FILE}'")
        self.model.load_weights(WEIGHTS_FILE, by_name=True)

    def mask(self, image, mask_dilation_pixels=0, return_raw_resutls=False):
        if not isinstance(image, np.ndarray):
            image = image.numpy()
        if image.ndim == 4:
            image = image[0]

        res = self.model.detect([image], verbose=0)[0]

        if return_raw_resutls:
            return res

        # Returns a list of dicts, one dict per image. The dict contains:
        # rois: [N, (y1, x1, y2, x2)] detection bounding boxes
        # class_ids: [N] int class IDs
        # scores: [N] float probability scores for the class IDs
        # masks: [H, W, N] instance binary masks

        mask_results = {"num_detections": res["rois"].shape[0]}
        for out_key, in_key in RESULTS_KEYMAP.items():
            mask_results[out_key] = np.expand_dims(res[in_key], axis=0)
        mask_results["detection_masks"] = np.transpose(mask_results["detection_masks"], (0, 3, 1, 2))
        
        if mask_dilation_pixels > 0:
            dilate_masks(mask_results, mask_dilation_pixels)

        return mask_results


def dilate_masks(mask_results, mask_dilation_pixels):
    masks = mask_results["detection_masks"]
    classes = mask_results["detection_classes"]

    kernel_size = 2 * mask_dilation_pixels + 1
    kernel = np.ones((kernel_size, kernel_size)).astype(np.uint8)

    for i in range(int(mask_results["num_detections"])):
        mask = (masks[0, i, :, :] > 0).astype(np.uint8)
        dilated = cv2.dilate(mask, kernel, iterations=1)
        dilated[dilated > 0] = classes[0, i]
        masks[0, i, :, :] = dilated


if __name__ == '__main__':
    masker = Masker()

    image_file = r"C:\Users\dantro\Repos\SVV\image-anonymisation\data\eval\images\Fy08_Fv034_hp01_f1_m00048.jpg"
    img = np.array(Image.open(image_file))
    # img = np.zeros((1024, 1024, 3)).astype(np.uint8)

    print("Running detection")
    res = masker.mask(img, return_raw_resutls=True)
    class_names = ["BG", "person", "bicycle", "car", "motorcycle", "bus", "truck"]
    visualize.display_instances(img, res['rois'], res['masks'], res['class_ids'],
                                class_names, res['scores'])
