import os
import json
import numpy as np
from pathlib import Path
from skimage.draw import polygon as draw_polygon
from collections import namedtuple

from Mask_RCNN.mrcnn.utils import Dataset

# a label and all meta information
Label = namedtuple( 'Label' , [

    'name'        , # The identifier of this label, e.g. 'car', 'person', ... .
                    # We use them to uniquely name a class

    'id'          , # An integer ID that is associated with this label.
                    # The IDs are used to represent the label in ground truth images
                    # An ID of -1 means that this label does not have an ID and thus
                    # is ignored when creating ground truth images (e.g. license plate).
                    # Do not modify these IDs, since exactly these IDs are expected by the
                    # evaluation server.

    'trainId'     , # Feel free to modify these IDs as suitable for your method. Then create
                    # ground truth images with train IDs, using the tools provided in the
                    # 'preparation' folder. However, make sure to validate or submit results
                    # to our evaluation server using the regular IDs above!
                    # For trainIds, multiple labels might have the same ID. Then, these labels
                    # are mapped to the same class in the ground truth images. For the inverse
                    # mapping, we use the label that is defined first in the list below.
                    # For example, mapping all void-type classes to the same ID in training,
                    # might make sense for some approaches.
                    # Max value is 255!

    'category'    , # The name of the category that this label belongs to

    'categoryId'  , # The ID of this category. Used to create ground truth images
                    # on category level.

    'hasInstances', # Whether this label distinguishes between single instances or not

    'ignoreInEval', # Whether pixels having this class as ground truth label are ignored
                    # during evaluations or not

    'color'       , # The color of this label
    ] )

# LABELS = [
#     #       name                     id    trainId   category            catId     hasInstances   ignoreInEval   color
#     Label('person'               , 24 ,       11 , 'human'           , 6       , True         , False        , (220, 20, 60)),
#     Label('rider'                , 25 ,       12 , 'human'           , 6       , True         , False        , (255,  0,  0)),
#     Label('car'                  , 26 ,       13 , 'vehicle'         , 7       , True         , False        , (  0,  0,142)),
#     Label('truck'                , 27 ,       14 , 'vehicle'         , 7       , True         , False        , (  0,  0, 70)),
#     Label('bus'                  , 28 ,       15 , 'vehicle'         , 7       , True         , False        , (  0, 60,100)),
#     Label('caravan'              , 29 ,      255 , 'vehicle'         , 7       , True         , True         , (  0,  0, 90)),
#     Label('trailer'              , 30 ,      255 , 'vehicle'         , 7       , True         , True         , (  0,  0,110)),
#     Label('train'                , 31 ,       16 , 'vehicle'         , 7       , True         , False        , (  0, 80,100)),
#     Label('motorcycle'           , 32 ,       17 , 'vehicle'         , 7       , True         , False        , (  0,  0,230)),
#     Label('bicycle'              , 33 ,       18 , 'vehicle'         , 7       , True         , False        , (119, 11, 32)),
# ]
LABELS = [
    #       name                     id    trainId   category            catId     hasInstances   ignoreInEval   color
    Label('person'               ,  1 ,       11 , 'human'           , 6       , True         , False        , (220, 20, 60)),
    Label('rider'                ,  2 ,       12 , 'human'           , 6       , True         , False        , (255,  0,  0)),
    Label('car'                  ,  3 ,       13 , 'vehicle'         , 7       , True         , False        , (  0,  0,142)),
    Label('truck'                ,  4 ,       14 , 'vehicle'         , 7       , True         , False        , (  0,  0, 70)),
    Label('bus'                  ,  5 ,       15 , 'vehicle'         , 7       , True         , False        , (  0, 60,100)),
    Label('caravan'              ,  6 ,      255 , 'vehicle'         , 7       , True         , True         , (  0,  0, 90)),
    Label('trailer'              ,  7 ,      255 , 'vehicle'         , 7       , True         , True         , (  0,  0,110)),
    Label('train'                ,  8 ,       16 , 'vehicle'         , 7       , True         , False        , (  0, 80,100)),
    Label('motorcycle'           ,  9 ,       17 , 'vehicle'         , 7       , True         , False        , (  0,  0,230)),
    Label('bicycle'              , 10 ,       18 , 'vehicle'         , 7       , True         , False        , (119, 11, 32)),
]

LABEL_NAME_TO_ID = {l.name: l.id for l in LABELS}
LABEL_ID_TO_NAME = {l.id: l.name for l in LABELS}


class CityScapeDataset(Dataset):
    # From https://github.com/markstrefford/Mask_RCNN/blob/master/samples/cityscape/cityscape.py

    def load_cityscapes(self, image_dir, annotation_dir, subset):
        for label in LABELS:
            self.add_class(source="cityscapes", class_id=label.id, class_name=label.name)

        # Train or validation dataset?
        assert subset in ["train", "val"]
        image_dir = os.path.join(image_dir, subset)
        annotation_dir = os.path.join(annotation_dir, subset)

        image_list = Path(image_dir).glob('**/*.png')
        for count, image_path in enumerate(image_list):
            city, image_file = str(image_path).split(os.sep)[-2:]

            # Get JSON file
            json_file = image_file.replace('_leftImg8bit.png', '_gtFine_polygons.json')
            json_filepath = os.path.join(annotation_dir, city, json_file)

            # Load mask polygons json
            # From https://stackoverflow.com/a/55016816/1378071 as cityscapes json wouldn't load without this!
            with open(json_filepath, encoding='utf-8', errors='ignore') as json_data:
                mask_json = json.load(json_data, strict=False)

            h, w = mask_json['imgHeight'], mask_json['imgWidth']

            # Get masks for each object
            objects = list(mask_json['objects'])

            polygons = []
            classes = []
            for obj in objects:
                obj_class = obj['label']
                obj_polygons = obj['polygon']

                if obj_class not in LABEL_NAME_TO_ID or not obj_polygons:
                    continue

                polygon = np.array(obj_polygons).astype(int)
                # Move points outside image to the image border.
                polygon[:, 0] = np.where(polygon[:, 0] < w - 1, polygon[:, 0], w - 1)
                polygon[:, 1] = np.where(polygon[:, 1] < h - 1, polygon[:, 1], h - 1)
                polygons.append(polygon)
                classes.append(LABEL_NAME_TO_ID[obj_class])

            image_id = count
            self._image_ids.append(image_id)
            self.add_image('cityscapes', image_id=image_id, path=image_path, width=w, height=h, polygons=polygons,
                           classes=np.array(classes))

    def load_mask(self, image_id):
        """Generate instance masks for an image.
       Returns:
        masks: A bool array of shape [height, width, instance count] with
            one mask per instance.
        class_ids: a 1D array of class IDs of the instance masks.
        """
        # If not a cityscape dataset image, delegate to parent class.
        image_info = self.image_info[image_id]
        if image_info["source"] != "cityscapes":
            return super(self.__class__, self).load_mask(image_id)

        # Convert polygons to a bitmap mask of shape
        # [height, width, instance_count]
        info = self.image_info[image_id]
        mask = np.zeros([info["height"], info["width"], len(info["polygons"])], dtype=np.uint8)
        for i, p in enumerate(info["polygons"]):
            # Get indexes of pixels inside the polygon and set them to 1
            rr, cc = draw_polygon(p[:, 1], p[:, 0])
            mask[rr, cc, i] = 1

        # Return mask, and array of class IDs of each instance.
        return mask.astype(np.bool), info["classes"]

    def image_reference(self, image_id):
        """Return the path of the image."""
        info = self.image_info[image_id]
        if info["source"] == "cityscapes":
            return info["path"]
        else:
            super(self.__class__, self).image_reference(image_id)


if __name__ == '__main__':
    import matplotlib
    matplotlib.use('TkAgg')
    import matplotlib.pyplot as plt
    from Mask_RCNN.mrcnn import visualize
    from Mask_RCNN.mrcnn.utils import extract_bboxes

    ds = CityScapeDataset()
    ds.load_cityscapes(image_dir="data\\train\\cityscapes\\images",
                       annotation_dir="data\\train\\cityscapes\\annotations",
                       subset="val")

    image_ids = np.random.choice(ds.image_ids, size=5)

    for image_id in image_ids:
        image_info = ds.image_info[image_id]
        img = ds.load_image(image_id)
        masks, classes = ds.load_mask(image_id)
        boxes = extract_bboxes(masks)

        fig, ax = plt.subplots(figsize=(10, (img.shape[1] / img.shape[0]) * 10))
        visualize.display_instances(img, boxes, masks, image_info["classes"],
                                    LABEL_ID_TO_NAME, np.ones(masks.shape[-1]), ax=ax)
        plt.show()
