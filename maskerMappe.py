# coding: utf-8

import numpy as np
import os
import getopt
import urllib as urllib
import sys
import tarfile
import tensorflow as tf
import zipfile
import time
import warnings

#from distutils.version import StrictVersion
from collections import defaultdict
from io import StringIO
from PIL import Image

from object_detection.utils import ops as utils_ops
from object_detection.utils import label_map_util
from object_detection.utils import visualization_utils as vis_util

warnings.filterwarnings("ignore")

def main(argv):
    basepath = ''
    outputpath = ''
    try:
        opts, args = getopt.getopt(argv,"hi:o:",["ifolder=","ofolder="])
    except getopt.GetoptError:
        print ('usage: maskerMappe.py -i <inputfolder> -o <outputfolder>')
        sys.exit(2)
    if len(opts) < 2:
        print ('usage: maskerMappe.py -i <inputfolder> -o <outputfolder>')
        sys.exit(2)
    for opt, arg in opts:
        if opt == '-h':
            print ('usage: maskerMappe.py -i <inputfolder> -o <outputfolder>')
            sys.exit()
        elif opt in ("-i", "--ifolder"):
            basepath = arg
        elif opt in ("-o", "--ofolder"):
            outputpath = arg
        else:
            print ('usage: maskerMappe.py -i <inputfolder> -o <outputfolder>')
            sys.exit(2)
    graph = initModel()
    maskImages(basepath, outputpath, graph)

def initModel():
    # What model to download.
    MODEL_NAME = 'mask_rcnn_inception_resnet_v2_atrous_coco_2018_01_28'#'mask_rcnn_inception_v2_coco_2018_01_28'#'mask_rcnn_inception_resnet_v2_atrous_coco_2018_01_28'#'ssd_mobilenet_v1_coco_2017_11_17'#
    MODEL_FILE = MODEL_NAME + '.tar.gz'
    DOWNLOAD_BASE = 'http://download.tensorflow.org/models/object_detection/'

    # Path to frozen detection graph. This is the actual model that is used for the object detection.
    PATH_TO_FROZEN_GRAPH = MODEL_NAME + '/frozen_inference_graph.pb'

    # List of the strings that is used to add correct label for each box.
    PATH_TO_LABELS = 'mscoco_label_map.pbtxt'#os.path.join('/home/chskje/.local/lib/python3.6/site-packages/tensorflow/models/research/object_detection/data', 'mscoco_label_map.pbtxt')
    
    # Download and extract model
    if not os.path.isfile(PATH_TO_FROZEN_GRAPH):
        print("Could not find the model graph file. Downloading...")
        opener = urllib.request.URLopener()
        opener.retrieve(DOWNLOAD_BASE + MODEL_FILE, MODEL_FILE)
        tar_file = tarfile.open(MODEL_FILE)
        for file in tar_file.getmembers():
            file_name = os.path.basename(file.name)
            if 'frozen_inference_graph.pb' in file_name:
                tar_file.extract(file, os.getcwd())
        print("Model graph file downloaded.")
    
    # Load model graph
    detection_graph = tf.Graph()
    with detection_graph.as_default():
        od_graph_def = tf.compat.v1.GraphDef()
        with tf.io.gfile.GFile(PATH_TO_FROZEN_GRAPH, 'rb') as fid:
            serialized_graph = fid.read()
            od_graph_def.ParseFromString(serialized_graph)
            tf.import_graph_def(od_graph_def, name='')

    category_index = label_map_util.create_category_index_from_labelmap(PATH_TO_LABELS, use_display_name=True)
    return detection_graph


def load_image_into_numpy_array(image):
  (im_width, im_height) = image.size
  return np.array(image.getdata()).reshape(
      (im_height, im_width, 3)).astype(np.uint8)

# TODO: handle images with different resolution better
def run_inference_for_multiple_images(images, graph):
    with graph.as_default():
        with tf.compat.v1.Session() as sess:
            output_dict_array = []
            dict_time = []
            # Get handles to input and output tensors
            ops = tf.compat.v1.get_default_graph().get_operations()
            all_tensor_names = {output.name for op in ops for output in op.outputs}
            tensor_dict = {}
            for key in ['num_detections', 'detection_boxes', 'detection_scores',
                'detection_classes', 'detection_masks']:
                tensor_name = key + ':0'
                if tensor_name in all_tensor_names:
                    tensor_dict[key] = tf.get_default_graph().get_tensor_by_name(tensor_name)
            if 'detection_masks' in tensor_dict:
                detection_boxes = tf.squeeze(tensor_dict['detection_boxes'], [0])
                detection_masks = tf.squeeze(tensor_dict['detection_masks'], [0])
                # Reframe is required to translate mask from box coordinates to image coordinates and fit the image size.
                real_num_detection = tf.cast(tensor_dict['num_detections'][0], tf.int32)
                detection_boxes = tf.slice(detection_boxes, [0, 0], [real_num_detection, -1])
                detection_masks = tf.slice(detection_masks, [0, 0, 0], [real_num_detection, -1, -1])
                detection_masks_reframed = utils_ops.reframe_box_masks_to_image_masks(
                    detection_masks, detection_boxes, images[0].shape[0], images[0].shape[1])
                detection_masks_reframed = tf.cast(tf.greater(detection_masks_reframed, 0.5), tf.uint8)
                # Follow the convention by adding back the batch dimension
                tensor_dict['detection_masks'] = tf.expand_dims(detection_masks_reframed, 0)
            image_tensor = tf.get_default_graph().get_tensor_by_name('image_tensor:0')
            index = 0
            size = len(images)
            for image in images:
                # Run inference
                start = time.time()
                output_dict = sess.run(tensor_dict, feed_dict={image_tensor: np.expand_dims(image, 0)})
                end = time.time()
                print(f'{100*(index/size):3.1f}% inference time : {end - start}')
                #print(f'gpu: {res.gpu}%, gpu-mem: {res.memory}%')
 
                # all outputs are float32 numpy arrays, so convert types as appropriate
                output_dict['num_detections'] = int(output_dict['num_detections'][0])
                output_dict['detection_classes'] = output_dict['detection_classes'][0].astype(np.uint8)
                output_dict['detection_boxes'] = output_dict['detection_boxes'][0]
                output_dict['detection_scores'] = output_dict['detection_scores'][0]
                if 'detection_masks' in output_dict:
                    output_dict['detection_masks'] = output_dict['detection_masks'][0]
 
                output_dict_array.append(output_dict)
                dict_time.append(end - start)
                index += 1
    return output_dict_array, dict_time

# Find images in the input path recursively
def recurseFindFiles(path, pathArray, fileArray, depth=10):
    with os.scandir(path) as entries:
        for entry in entries:
            if entry.is_dir() and depth > 0:
                depth-=1
                recurseFindFiles(path+entry.name,pathArray,fileArray,depth)
            elif entry.is_file() and entry.name.endswith('jpg'):
                pathArray.append(path)
                fileArray.append(entry.name)

# Find images in the input path NOT recursively
def getImages(path):
    fileArray = []
    with os.scandir(path) as entries:
        for entry in entries:
            if entry.is_file() and entry.name.endswith('jpg'):
                fileArray.append(entry.name)
    return fileArray

def maskImages(basepath, outputpath, detection_graph):
    if not basepath.endswith(os.sep): 
        basepath = basepath+os.sep
    if not outputpath.endswith(os.sep): 
        outputpath = outputpath+os.sep
    

    pathArray = []
    fileArray = []
    recurseFindFiles(basepath, pathArray, fileArray, depth=10)
    
    current_milli_time = lambda: int(round(time.time() * 1000))
    images = []
    # Get image size (it needs to be the same for all images in the batch)
    im = Image.open(pathArray[0]+os.sep+fileArray[0])
    imHeight = im.height
    imWidth = im.width

    # Load Images TODO: Images should probably be loaded dynamically, maybe?
    print('\nLoading images:')
    index = 0
    size = len(pathArray)
    for ind in range(size): #TEST_IMAGE_PATHS:
        fullpath = pathArray[ind]+os.sep+fileArray[ind]
        startTime = current_milli_time()
        print(f'{100*(index/size):3.1f}% File: {fullpath}')
        image = Image.open(fullpath)
        image = image.resize((imWidth, imHeight), Image.ANTIALIAS) # TODO: this is probably expensive, and should be done changed
        # the array based representation of the image will be used later in order to prepare the
        # result image with boxes and labels on it.
        image_np = load_image_into_numpy_array(image)
        images.append(image_np)
        index += 1
    #
    # Run inference.
    print('\nRunning inference:')
    output_dicts, out_time = run_inference_for_multiple_images(images, detection_graph)

    # Apply mask and save the results of the detection. TODO: different colors for different object types
    ind = 0
    for output_dict in output_dicts:
        for maskIndex in range(0, len(output_dict['detection_masks'])):
            if output_dict['detection_classes'][maskIndex] in [1,2,3,4,6,8]:
                vis_util.draw_mask_on_image_array(images[ind],output_dict['detection_masks'][maskIndex],'black',1)
        fullpath = pathArray[ind]+os.sep+fileArray[ind]
        endpath = fullpath.replace(basepath,outputpath)
        im = Image.fromarray(images[ind])
        os.makedirs(os.path.dirname(endpath), exist_ok=True)
        im.save(endpath)
        ind = ind+1
    endTime = current_milli_time()
    delta = endTime-startTime
    print(f'elapsed time:\t{delta/1000}s\n')
    # to monitor GPU usage use command:  watch -d -n 0.5 nvidia-smi
    # in the terminal.

if __name__ == "__main__":
    main(sys.argv[1:])