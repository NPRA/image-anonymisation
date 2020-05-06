import os
import time
import logging
import argparse
import numpy as np
from pycocotools.coco import COCO
from pycocotools.cocoeval import COCOeval
from pycocotools import mask as maskUtils

# os.environ["CUDA_VISIBLE_DEVICES"] = "-1"

from src.Masker import Masker
from config import LABEL_MAP
from src.Logger import LOGGER
from src.io.TreeWalker import TreeWalker
from src.io.tf_dataset import get_tf_dataset


def masker_category_to_annotation_category(masker_cat, coco):
    """
    Convert from masker category to annotation category, using the category name.

    :param masker_cat: Masker category
    :type masker_cat: int
    :param coco: COCO object representing the dataset
    :type coco: COCO
    :return: Annotation category
    :rtype: int
    """
    masker_cat_name = LABEL_MAP[int(masker_cat)]
    for _id, cat_dict in coco.cats.items():
        if cat_dict["name"] == masker_cat_name:
            return _id

    LOGGER.info(__name__, f"Category {masker_cat} ({masker_cat_name}) not found in annotations. This detection will be "
                          f"ignored.")
    return None


def mask_results_to_coco_results(image_id, mask_results, coco):
    """
    Convert masking results from `Masker.mask` to COCO-formatted results

    :param image_id: COCO-id of image
    :type image_id: int
    :param mask_results: Output from `Masker.mask`
    :type mask_results: dict
    :param coco: COCO object representing the dataset
    :type coco: COC
    :return: Converted results. Each element is a dict on the COCO format containing the results.
    :rtype: list of dict
    """
    results = []
    classes = mask_results["detection_classes"][0]
    boxes = mask_results["detection_boxes"][0].round(1)
    masks = mask_results["detection_masks"][0]
    scores = mask_results["detection_scores"][0]
    height, width = masks.shape[-2:]

    for i in range(int(mask_results["num_detections"])):
        cat_id = masker_category_to_annotation_category(classes[i], coco)
        if cat_id is not None:
            bbox = boxes[i]
            mask = (masks[i] > 0).astype(np.uint8)
            mask = maskUtils.encode(np.asfortranarray(mask))
            result = {
                "image_id": image_id,
                "category_id": cat_id,
                "bbox": [
                    bbox[1] * width,
                    bbox[0] * height,
                    (bbox[3] - bbox[1]) * width,
                    (bbox[2] - bbox[0]) * height
                ],
                "score": scores[i],
                "segmentation": mask,
            }
            results.append(result)
    return results


def get_results(coco, imgs_dir):
    """
    Get the masking results for all images in `imgs_dir`.

    :param coco: COCO object representing the dataset.
    :type coco: COC
    :param imgs_dir: Path to base directory with images to use for evaluation.
    :type imgs_dir: str
    :return: Masking results. Image IDs are keys, and masking results (output from `Masker.mask`) are values.
    :rtype: dict
    """
    LOGGER.info(__name__, "Building results.")

    tree_walker = TreeWalker(imgs_dir, [], skip_webp=False, precompute_paths=True)
    dataset = get_tf_dataset(tree_walker)
    dataset_iterator = iter(dataset)

    filename_to_image_id = {img_dict["file_name"]: _id for _id, img_dict in coco.imgs.items()}
    masker = Masker()
    results = {}

    for i, paths in enumerate(tree_walker.walk()):
        tic = time.time()

        img = next(dataset_iterator)
        mask_results = masker.mask(img)
        image_id = filename_to_image_id[paths.filename]
        results[image_id] = mask_results

        dt = time.time() - tic
        LOGGER.info(__name__, f"Processed image {i+1}/{tree_walker.n_valid_images} in {round(dt, 2)} s. "
                              f"File: {paths.filename}")
    return results


def get_args():
    """ Get the command line arguments """
    parser = argparse.ArgumentParser(description="Evaluate the anonymisation model.")
    parser.add_argument("-i", "-input-folder", dest="input_folder",
                        help="Base directory of images to use for evaluation.")
    parser.add_argument("-a", "-annotation-file", dest="annotation_file",
                        help="Path to a .json file containing the ground-truth annotations. The file must be formatted"
                             " according to the COCO annotation file guidelines.")
    parser.add_argument("--accumulate", action="store_true", dest="accumulate",
                        help="Accumulate the results for all images?")
    return parser.parse_args()


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format=LOGGER.fmt, datefmt=LOGGER.datefmt)
    args = get_args()
    # Create a COCO-dataset using the annotation file.
    coco = COCO(annotation_file=args.annotation_file)
    # Run the masker on all images
    results = get_results(coco, args.input_folder)
    # Convert the results to COCO-format
    converted_results = []
    for image_id, res in results.items():
        converted_results += mask_results_to_coco_results(image_id, res, coco)
    # Fill the results with relevant metadata
    coco_results = coco.loadRes(converted_results)
    
    # Run evaluation
    coco_eval = COCOeval(coco, coco_results, iouType="segm")
    if args.accumulate:
        print("Accumulated results")
        coco_eval.evaluate()
        coco_eval.accumulate()
        coco_eval.summarize()
    else:
        for image_id, image_dict in coco.imgs.items():
            print(90 * "=")
            print("Results for image:", image_dict["file_name"])
            coco_eval.params.imgIds = [image_id]
            coco_eval.evaluate()
            coco_eval.accumulate()
            coco_eval.summarize()
