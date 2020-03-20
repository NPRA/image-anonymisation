import os
import numpy as np
from PIL import Image
import cv2

import config
from Mask_RCNN.mrcnn.model import MaskRCNN
from src.train import train_config
from src.Logger import LOGGER


class Masker:
    """
    Implements the masking functionality. Uses a pre-trained TensorFlow model to compute masks for images. Model
    configuration is done in `config`.
    """
    def __init__(self):
        LOGGER.info(__name__, "Initializing Mask R-CNN model")
        self.coco_config = train_config.CarCocoConfigInference()
        self.model = MaskRCNN(mode="inference", config=self.coco_config, model_dir=train_config.TRAIN_MODELS_DIR)

        weights_path = os.path.join(config.MODELS_DIRECTORY, config.weights_file)
        LOGGER.info(__name__, f"Loading weights from file '{weights_path}'")
        self.model.load_weights(weights_path, by_name=True)

    def mask(self, image, mask_dilation_pixels=0, return_raw_results=False):
        """
        Run the masking on `image`.

        :param image: Input image. Must be a 4D color image array with shape (1, height, width, 3)
        :type image: np.ndarray
        :param mask_dilation_pixels: Approximate number of pixels for mask dilation. This will help ensure that an
                                    identified object is completely covered by the corresponding mask. Set
                                    `mask_dilation_pixels = 0` to disable mask dilation.
        :type mask_dilation_pixels: int
        :param return_raw_results: Return the masking results directly from `MaskRCNN.detect`?
        :type return_raw_results: bool
        :return: Dictionary containing masking results. Content depends on the model used.
        :rtype: dict
        """
        if not isinstance(image, np.ndarray):
            image = image.numpy()
        if image.ndim == 4:
            image = image[0]
        # Run prediction
        results = self.model.detect([image], verbose=0)[0]
        if return_raw_results:
            return results

        # Convert the results to expected format. Only include the detections we are interested in.
        # From MaskRCNN.detect():
        #   rois: [N, (y1, x1, y2, x2)] detection bounding boxes
        #   class_ids: [N] int class IDs
        #   scores: [N] float probability scores for the class IDs
        #   masks: [H, W, N] instance binary masks
        detections_to_mask = np.isin(results["class_ids"], config.MASK_LABELS)
        mask_results = {
            "num_detections": detections_to_mask.sum(),
            "detection_boxes": np.expand_dims(results["rois"][detections_to_mask], 0),
            "detection_classes": np.expand_dims(results["class_ids"][detections_to_mask], 0),
            "detection_scores": np.expand_dims(results["scores"][detections_to_mask], 0),
            "detection_masks": np.expand_dims(
                np.transpose(results["masks"], (2, 0, 1))[detections_to_mask, :, :], 0
            ).astype(bool)
        }

        # Dilate masks?
        if mask_dilation_pixels > 0:
            dilate_masks(mask_results, mask_dilation_pixels)
        return mask_results


def dilate_masks(mask_results, mask_dilation_pixels):
    """
    Dilate the masks.

    :param mask_results: Results from `Masker.mask`
    :type mask_results: dict
    :param mask_dilation_pixels: Approximate number of pixels to dilate
    :type mask_dilation_pixels: int
    """
    masks = mask_results["detection_masks"]
    kernel_size = 2 * mask_dilation_pixels + 1
    kernel = np.ones((kernel_size, kernel_size)).astype(np.uint8)
    for i in range(int(mask_results["num_detections"])):
        mask = masks[0, i, :, :]
        dilated = cv2.dilate(mask, kernel, iterations=1)
        masks[0, i, :, :] = dilated


if __name__ == '__main__':
    # Simple test code which applies the masker to all images in the input directory, and writes ouput images
    # with drawn masks, classifications, and scores.
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
    tree_walker = TreeWalker(input_folder=args.input_folder, mirror_folders=[args.output_folder], skip_webp=False,
                             precompute_paths=True)
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
