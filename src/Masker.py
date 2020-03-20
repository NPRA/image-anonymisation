import os
import numpy as np
from PIL import Image
import cv2
os.environ["CUDA_VISIBLE_DEVICES"] = "-1"

import config
from Mask_RCNN.mrcnn.model import MaskRCNN
from src.train import train_config
from src.Logger import LOGGER

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

        weights_path = os.path.join(config.MODELS_DIRECTORY, config.weights_file)
        LOGGER.info(__name__, f"Loading weights from file '{weights_path}'")
        self.model.load_weights(weights_path, by_name=True)

    def mask(self, image, mask_dilation_pixels=0, return_raw_results=False):
        if not isinstance(image, np.ndarray):
            image = image.numpy()
        if image.ndim == 4:
            image = image[0]
        # Run prediction
        results = self.model.detect([image], verbose=0)[0]
        if return_raw_results:
            return results

        # Convert results to expected format.
        mask_results = {"num_detections": results["rois"].shape[0]}
        for out_key, in_key in RESULTS_KEYMAP.items():
            mask_results[out_key] = np.expand_dims(results[in_key], axis=0)
        mask_results["detection_masks"] = np.transpose(mask_results["detection_masks"], (0, 3, 1, 2))

        # Dilate masks?
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
    import argparse
    import matplotlib
    from tqdm import tqdm
    matplotlib.use('TkAgg')
    import matplotlib.pyplot as plt
    from Mask_RCNN.mrcnn import visualize
    from src.io.TreeWalker import TreeWalker

    parser = argparse.ArgumentParser()
    parser.add_argument("-i", dest="input_folder")
    parser.add_argument("-o", dest="output_folder")
    args = parser.parse_args()
    tree_walker = TreeWalker(input_folder=args.input_folder, mirror_folders=[args.output_folder], skip_webp=False, precompute_paths=True)
    masker = Masker()

    class_names = ["BG", "person", "bicycle", "car", "motorcycle", "bus", "truck"]
    for input_path, mirror_dirs, filename in tqdm(tree_walker.walk()):
        img = np.array(Image.open(os.path.join(input_path, filename)))
        res = masker.mask(img, return_raw_results=True)

        fig, ax = plt.subplots(figsize=(10, (img.shape[1] / img.shape[0]) * 10))
        visualize.display_instances(img, res['rois'], res['masks'], res['class_ids'],
                                    class_names, res['scores'], ax=ax)

        os.makedirs(mirror_dirs[0], exist_ok=True)
        output_image = os.path.join(mirror_dirs[0], os.path.splitext(filename)[0] + ".png")
        fig.tight_layout()
        plt.savefig(output_image, dpi=600, bbox_inches="tight")
        plt.clf()
