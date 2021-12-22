# Image Anonymisation
The Image Anonymisation for the Norwegian Public Road Administration(NPRA) is
an end-to-end solution for anonymisation of people and vehicles in images.
It supports the anonymisation of planar/field-of-view-images and 360°-images.
The project's main purpose is to provide anonymised road images to the NPRA’s public open source web application,
[Vegbilder](https://vegbilder.atlas.vegvesen.no/).
Vegbilder's source code can be found at [NPRA/Vegbilder](https://github.com/NPRA/VegBilder).

This Wiki-page is meant to be complimentary documentation of the development,
structure and implementation of this project, which does not fit in the repo's `README.md`-file


# Development Cycles
The first version of the image anonymisation was developed in 2019/2020.
It supported end-to-end image anonymisation "planar", also called "field-of-view", images.

The second version of the image anonymisation was developed in 2021/2022.
There were four main updates and differences to this version:
1. The anonymisation should support 360°-images in a satisfactory manner
2. The anonymisation should *not* output the `.wepb`-files
3. The anonymisation should be able to produce "previews" of the image of a desired dimension and position.
4. The output `.json`-file should have updated fields and values to comply with new standards.


#### Planar vs. 360°-images
There were notable differences that had an impact on
the choices that were made during the continuation of this project to support 360°-images.

1. The "flat" 360°-images were curved, consequently, making the objects to be detected curved and 
less likely to be detected fully.
2. The images were significantly larger in size
3. The exif-data is different in 360°-images.

#### Changes from V.1 to V.2

The following changes to V.1 was implemented to support the new features of V.2
and to tackle the issues raised in the section above:

* The user can enable the `use_cutouts`-configuration.
This will create a cutout and do a "sliding window" technique over the image
and predict anonymisation masks for each position of the cutout.
The dimension and how many steps the window should slide at a time (height-wise and length wise)
is also defined by the user in the `config`-file.

* The generated `.json`-file has new and updated fields

* The exif-data is read from the `RefLinkInfo`-exif tag for 360°-images.

* If the image does not contain either the `ImageProperties` or `RefLinkInfo`,
it will derive GPS-data from the `GPSInfo`-exif tag.

*  All output of `.wepb`-files are commented out.

* The user can enable preview-generation in the configuration.
This will produce a `.jpg`-image in the desired location

* A `create_json.py` script is added. This enables the user to *only* produce previews.

* [bugfix] `exif_feltkode` also parses lane codes for lanes such as public transport lanes, bike lanes, etc.
 They are denoted as "F\*number\*\*word character\*". E.g F5K


###### New/Changed JSON-fields
* `exif_dataeier`: Set in the config file by the user.
* `exif_camera`: Read from the exif data of the input image
* `exif_imagetype`: Set in the config file by the user.
* `exif_imagehigh`: Read from image data
* `exif_imagewidth`: Read from image data
* `exif_speed_ms`: [changed name] from `exif_speed`
* `exif_moh`: Read from the exif data of the input image
* `exif_strekningsnavn`: Read from the exif data of the input image.
* `exif_roadtype`: Read from the exif data of the input image.
* `exif_filnavn_preview`: Generated based on file name of the input image.


# Architecture


| The simplified architecture of the Image Anonymisation |
|    :----:   |
|![](SVV-ImageAnonymisationArchitecture.png "The architecture of the Image Anonymisation")     |

The image anonymisation consists of mainly six components
as well as multiple helper-scripts and classes.

#### Main components
* [`ImageProcessor`](#imageprocessor)
* [`Masker`](#masker)
* `ExifWorker`
* `SaveWorker`

#### Helper Classes
* `TreeWalker`
* `Path`
* `DatabaseClient.py`
* `Table.py`

##### ImageProcessor
The `ImageProcessor` will run the masker on either the image with or without the sliding window techinque.
If the sliding window is used, the masker is first used on the full image,
followed by the sliding windows.

| A visualisation of the cutout method |
|    :----:   |
|![](./SVV-CutoutMethod.png)     |
|The **first row** shows the input image and how the orange sliding window moves over it. The **second row** shows the mask result-building process|

The window will first slide width-wise, then height-wise.
This is implemented by using a double for-loop.
Each masking result for each window will have to be combined
to make up one result for the image itself.
One issue is that distinct windows may predict masks for the same object.
These masks may also be different from each other.
To address this issue a comparison is made for each mask.
If there is a overlap in pixels of the newly predicted mask in the window
compared to any of the previously predicted masks for the image,
the the mask is assumed to already exist.
If the mak already exist, it's predicted data should be updated in the following manner:

1. The outer edges should be moved to be defined by the outermost pixels from either the existing mask or the new mask.
2. The bounding boxes should be updated to be the outermost value from either the existing or the new mask.
3. The prediction score should be added to a pool of all the other prediction scores that were made for one mask.
The average of all prediction for one masked object will determine the final score of this mask.
4. The prediction class should be added to a pool of all the other prediction classes that were made for one mask.
The majority vote of all the predictions for one masked object will determine the final prediction class for this mask.

After the results for the image is finished,
ExifWorkers and SaveWorkers are dispatched.

##### Masker

The `Masker` will run the model prediction on the image it gets as an input.
It will download the appropriate model if it does not exist in the `/models`-folder in the repo.
Additionally it will filter out some of the predictions which are not relevant for this anonymisation case.

##### ExifWorker
The `ExifWorker` generates and saves the `.json`-file.
It will read the exif data of the image.
The quality of the data of the input image is evaluated to one of three levels.

0. The lowest level of quality.
This level is given to an image where the exif-data cannot be derived.
 1. This level is given to an image with many of the values are missing.
 Oftentimes if this level is achieved, some of the values may be found in the path and the file name of the image.
 2. This is the highest quality level where all the exif data that is not optional exists.

#### SaveWorker
The `SaveWorker` is responsible to save the anonymised image and the potential preview image.
Additionally it will draw on the masks after the definitions in the configuration-file.

##### TreeWalker
The `TreeWalker` is a helper-class that finds all the relevant files.
The `walk()`-function will traverse the file tree and generate instances of `Path`-objects for each relevant file it finds.

#### Path
The `Path` is a class that contain all the path information relevant for a specified image.
It contains the filename, output file paths, archive file paths, input file paths and preview paths.

#### SDOGeometry
The SDOGeometry class is a helper class to represent a `SDO_GEOMETRY` object in Oracle Database.

## Scripts

#### Helper Scripts
* `email_sender.py`
* I/O
    * `exif_util.py`
    * `file_access_guard.py`
    * `file_checker.py`
    * `save.py`
    * `tf_dataset.py`
* Database
    * `formatters.py`
    * `geometry.py`
##### email_sender.py    
The `email_sender.py` is a helper script to send emails.
The sending of email is configured in the accompanying `config`-file when running. 
It supports three different types of email messages: 
1. `critical` for critical errors which cause the program to exit abnormally
2. `error` for processing errors which do not cause the program to exit.
3. `finished` for when the program exists normally.

##### exif_util.py
The `exif_util.py` is a helper script to parse the exif-data of an image and create metadata for the output `.json`-file.
It will create a `dict` from a template and parse the exif data to 
fill the `dict` with values. 

First it will try to get data from the `ImageProperties`-tag. 
The `ImageProperties` is an `XML` that contains road information such as 
Road name and number, Lane name and number, etc. 
It also contain important GPS-information of where the image was taken.

If the `ImageProperties`-tag does not exist in the image's exif,
it will try to get data from the `ReflinkInfo`-tag.
The `ReflinkInfoTag` is an `XML` that contains much the same road information
as in the `ImageProperties`-tag, but in a different format, thus, these tags need to be handled differently.

If the image exif data does not contain any of these aforementioned tags,
as much data as possible needs to be extracted from the `GPSInfo`-tag and the file path.
The filename of the road images are standardized on a specific format, 
making the information extraction somewhat predictable.

The script also contains functionality for writing a `.json`-file with the filled in `dict`.

##### file_access_guard.py
The `file_access_guard.py` is a script to help determine the existence and access of a path. 
It traverses a `Path`-object.

##### file_checker.py
The `file_checker.py` is a helper script that handles all the logic regarding what files to expect as outputs.
It reports what files are expected as outputs, what files are missing compared to the expected files
and clearing cached files.

##### save.py
The `save.py` is a helper script that handles the writing of the output anonymised image and the preview image.
It will draw the masks defined from the mask-prediction according to the settings in the `config`-file.
After the masks have been drawn on the image, the image is written to one or more of the following places:
* The input folder
* The output folder
* The archive folder

The script also handles the cropping and writing of the preview image according to the specifications in the `config`-file.
The preview is output to one or more of the following places:
* The input folder
* The output folder
* The archive folder
* A separate folder path specified in the `config`-file

##### tf_dataset.py
The `tf_dataset.py` is a helper script that can create a [TensorFlow Dataset](https://www.tensorflow.org/api_docs/python/tf/data/Dataset) 
from the image files in a path. 
It also has validation checks to ensure that an image is represtented as a valid 4D-tensor.

##### formatters.py
The `formatters.py` is a helper script that is used to get the correct information from the `.json`-file 
on a format that is accepted by the database.
There is one formatter function for every field in the `.json`-file

##### geometry.py
The `geometry.py` is a helper script to convert an instance of the `src.db.SDOGeometry` class 
to a `SDO_GEOMETRY` Oracle database object type.

#### Extra Scripts
There are several extra scripts that serve their own functionalities when invoked. 

* `check_folders.py`
* `create_json.py`
* `create_preview.py`
* `evaluate.py`
* Database
    * `create_db_config.py`
    * `create_table.py`
    * `execute_sql.py`
    * `insert_geom_metadata.py`
    * `json_to_db.py`
    
##### check_folders.py
The `check_folders.py` script is a script that will traverse a file tree with the `TreeWalker`
and check if the expected files are in the input, output or archive folders depending on the accompanying `config`-file.
It will create a cumulative status of how many files that are either of the following statuses:
* `OK`
* `Missing`
* `None`

This script is invoked by running from root:
```
python -m script.check_folders <args>
```
##### create_json.py
The `create_json.py` script is a script that will create a `.json`-file for each of the valid image-files
found in the input folder path. 
It will traverse the input folder and use the `ExifWorker`-class to parse the exif-data in the input images
as well as write the output files to the desired locations.

This script is invoked by running from root:
```
python -m script.create_json.py <args>
```
##### create_preview.py
The `create_preview.py` script is a script that will traverse the file tree with the `TreeWalker` 
and for each image found, create a cropped preview of it. 
The preview's dimension and position is defined in the accompanying `config`-file.
The preview is written to the output locations also defined in the accompanying `config`-file.

This script is invoked by running from root:
```
python -m script.check_preview <args>
```

##### evaluate.py
The `evaluate.py` script is a script to evaluate the mask prediciton model. 
It will evaluate the model on the COCO-data set and accumulate results over all the entries.
To run this script, pycocotools is required

This script is invoked by running from root:
```
python -m script.evaluate <args>
```
## Configuration

# The Next Steps


