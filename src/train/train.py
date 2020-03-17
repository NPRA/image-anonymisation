import os
import imgaug

from Mask_RCNN.mrcnn.model import MaskRCNN
from Mask_RCNN.samples.coco.coco import CocoConfig, CocoDataset
import src.train.config as train_config


class CarCocoConfig(CocoConfig):
    IMAGES_PER_GPU = 1
    # Number of classes + background
    NUM_CLASSES = len(train_config.CLASS_IDS) + 1


if __name__ == '__main__':
    coco_config = CarCocoConfig()
    weights_path = os.path.join(train_config.TRAIN_MODELS_DIR, "mask_rcnn_coco.h5")
    model = MaskRCNN(mode="training", config=coco_config, model_dir=train_config.TRAIN_MODELS_DIR)

    # Load weights
    print("Loading ImageNet weights ")
    model.load_weights(weights_path, by_name=True)

    # Loading data
    print("Loading data")
    dataset_train = CocoDataset()
    dataset_train.load_coco(train_config.COCO_DIR, "train", year="2017", auto_download=False, class_ids=train_config.CLASS_IDS)
    dataset_train.prepare()

    # Validation dataset
    dataset_val = CocoDataset()
    dataset_val.load_coco(train_config.COCO_DIR, "val", year="2017", auto_download=False, class_ids=train_config.CLASS_IDS)
    dataset_val.prepare()

    # Image Augmentation
    # Right/Left flip 50% of the time
    augmentation = imgaug.augmenters.Fliplr(0.5)

    # *** This training schedule is an example. Update to your needs ***

    # Training - Stage 1
    # print("Training network heads")
    model.train(dataset_train, dataset_val,
                learning_rate=coco_config.LEARNING_RATE,
                epochs=5,
                layers='heads',
                augmentation=augmentation)

    # Training - Stage 2
    # Finetune layers from ResNet stage 4 and up
    print("Fine tune Resnet stage 4 and up")
    model.train(dataset_train, dataset_val,
                learning_rate=coco_config.LEARNING_RATE,
                epochs=5,
                layers='4+',
                augmentation=augmentation)

    # Training - Stage 3
    # Fine tune all layers
    print("Fine tune all layers")
    model.train(dataset_train, dataset_val,
                learning_rate=coco_config.LEARNING_RATE / 10,
                epochs=5,
                layers='all',
                augmentation=augmentation)
