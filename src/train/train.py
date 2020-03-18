import os
import re
import imgaug
# os.environ["CUDA_VISIBLE_DEVICES"] = "-1"
import tensorflow as tf

from Mask_RCNN.mrcnn.model import MaskRCNN
from Mask_RCNN.samples.coco.coco import CocoConfig, CocoDataset
import src.train.config as train_config


if __name__ == '__main__':
    coco_config = train_config.CarCocoConfig()
    weights_path = os.path.join(train_config.TRAIN_MODELS_DIR, "mask_rcnn_coco.h5")
    model = MaskRCNN(mode="training", config=coco_config, model_dir=train_config.TRAIN_MODELS_DIR)

    # Initialize weights
    session = tf.compat.v1.keras.backend.get_session()
    init = tf.compat.v1.global_variables_initializer()
    session.run(init)

    # Load weights
    print("Loading weights ")
    exclude_load_layers = ["mrcnn_bbox_fc", "mrcnn_class_logits", "mrcnn_mask"]
    model.load_weights(weights_path, by_name=True, exclude=exclude_load_layers)
    # model.load_weights(weights_path, by_name=True)

    # Model summary
    with open(os.path.join(train_config.TRAIN_MODELS_DIR, "model_summary.txt"), "w") as f:
        model.keras_model.summary(print_fn=lambda s: f.write(s + "\n"))

    # Loading data
    print("Loading data")
    dataset_train = CocoDataset()
    dataset_train.load_coco(train_config.COCO_DIR, "train", year="2017", auto_download=False,
                            class_ids=train_config.CLASS_IDS)
    dataset_train.prepare()

    # Validation dataset
    dataset_val = CocoDataset()
    dataset_val.load_coco(train_config.COCO_DIR, "val", year="2017", auto_download=False,
                          class_ids=train_config.CLASS_IDS)
    dataset_val.prepare()

    # Image Augmentation
    # Right/Left flip 50% of the time
    # augmentation = imgaug.augmenters.Fliplr(0.5)
    augmentation = None

    # *** This training schedule is an example. Update to your needs ***

    uninitialized_layers = re.compile("mrcnn_(bbox_fc|class_logits|mask)")
    print("Training unitinialized layers")
    model.train(dataset_train, dataset_val,
                learning_rate=coco_config.LEARNING_RATE,
                epochs=3,
                layers=uninitialized_layers,
                augmentation=augmentation)

    # Training - Stage 1
    print("Training network heads")
    model.train(dataset_train, dataset_val,
                learning_rate=coco_config.LEARNING_RATE,
                epochs=3,
                layers='heads',
                augmentation=augmentation)

    # Training - Stage 2
    # Finetune layers from ResNet stage 4 and up
    # print("Fine tune Resnet stage 4 and up")
    # model.train(dataset_train, dataset_val,
    #             learning_rate=coco_config.LEARNING_RATE,
    #             epochs=5,
    #             layers='4+',
    #             augmentation=augmentation)
    #
    # # Training - Stage 3
    # # Fine tune all layers
    # print("Fine tune all layers")
    # model.train(dataset_train, dataset_val,
    #             learning_rate=coco_config.LEARNING_RATE / 10,
    #             epochs=5,
    #             layers='all',
    #             augmentation=augmentation)
