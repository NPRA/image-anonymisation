# image-anonymisation
Using pre-trained TensorFlow models to remove vehicles and people from images

## Getting started
#### Clone or download the code

**Option 1 - With Git:** 
`git clone https://github.com/NPRA/image-anonymisation.git` (Requires `git` to be installed)

**Option 2 - Manual download:**
Select "Clone or download" and "Download ZIP" above. Then extract the downloaded archive to a suitable 
location.

#### Installing Build Tools for Visual Studio 2019
Build Tools for Visual Studio 2019 is required to build some of the package-dependencies. 
1. Download the [installer](https://visualstudio.microsoft.com/thank-you-downloading-visual-studio/?sku=BuildTools&rel=16). 
1. Run the installer as Administrator
1. Select "C++ build tools" during installation. 

#### Installing Anaconda
1. Download the [installer](https://www.anaconda.com/distribution/).
1. Run installer as Administrator.
1. Select "Install for all users" during installation.

#### Creating the conda-environment
1. Open an "Anaconda PowerShell Prompt" as Administrator.
2. In the Anaconda PowerShell Prompt, navigate to the root directory of the cloned repository.
3. Create the conda-environment by running:
    ```Bash
    conda env create -f environment.yml
    ```
    This will create a new environment named `image-anonymisation`.
5. Activate the environment by running:
    ```Bash
    conda activate image-anonymisation
    ```
4. Install `pycocotools`:
    ```Bash
    pip install git+https://github.com/philferriere/cocoapi.git#subdirectory=PythonAPI
    ```

#### Proxy setup
If Anaconda fails to create the environment above due to a HTTP error, you might need to configure Anaconda to use
a proxy:

1. Add `HTTPS_PROXY=<your_proxy> to the system environment variables.
2. In `~/.condarc` add the following lines:
    ```
    proxy_servers:
        https: <your_proxy>
    ```
3. You should now be able to create the conda environment with:
    ```Bash
    conda env create -f environment.yml
    ```
   Note that the `pip`-part of the installation will fail, but the conda packages will be installed.
4. Activate the environment:
    ```Bash
    conda activate image-anonymisation
    ```
5. The `pip`-packages will now have to be installed manually:
    ```Bash
    pip install opencv-python==4.2.0.32 pillow==7.0.0 --proxy <your_proxy>
    ```
    The `webp` package requires a little more trickery. First, install `importlib_resources` and `conan`:
    ```Bash
    pip install importlib_resources>=1.0.0  conan>=1.8.0 --proxy <your_proxy>
    ```
    Now, `conan` has to be configured to use the proxy server. In `~/.conan/conan.conf` under `[proxies]`, add the lines:
    ```
    http = <your_proxy>
    https = <your_proxy>  
    ```
    The `webp` package can now be installed with
    ```
    pip install webp==0.1.0a15 --proxy <your_proxy>
    ```
## Usage
The program will traverse the file-tree rooted at the input folder, and mask all .jpg images within the tree. The masked 
images will be written to an output directory with identical structure as the input folder. The program should be
executed as a python-module from the root directory:
```
usage: python -m src.main [-h] [-i INPUT_FOLDER] [-o OUTPUT_FOLDER] [-a ARCHIVE_FOLDER]

Image anonymisation

optional arguments:
  -h, --help            show this help message and exit
  -i INPUT_FOLDER, --input-folder INPUT_FOLDER
                        Base directory for input images.
  -o OUTPUT_FOLDER, --output-folder OUTPUT_FOLDER
                        Base directory for masked (output) images and metadata
                        files
  -a ARCHIVE_FOLDER, --archive-folder ARCHIVE_FOLDER
                        Base directory for archiving original images.
```
Note: Make sure that the conda environment is activated before executing the command above.

#### Batch script and PowerShell script.
The anonymisation can be ran without manually activating the conda environment, by running either `bin/run-with-prompt.bat` or `bin/run.ps1`.
The latter also works when conda is not initialized in the shell, as long as the `conda_path` parameter is specified correctly.

#### Additional configuration
Additional configuration variables are listed in `config.py`.

## Documentation
Buidling the documentation requires `sphinx` with the `m2r` extension. These can be installed with `conda` and `pip`:
```Bash
conda install sphinx
pip install m2r
``` 
The HTML documentation can then be build from the `docs` directory by running
```Bash
.\make.bat html
```

## Evaluating the current model
The anonymisation model can be evaluated by running the evaluation script:
```
usage: python -m src.evaluate [-h] [-i INPUT_FOLDER] [-a ANNOTATION_FILE] [--accumulate]

Evaluate the anonymisation model.

optional arguments:
  -h, --help            show this help message and exit
  -i INPUT_FOLDER, -input-folder INPUT_FOLDER
                        Base directory of images to use for evaluation.
  -a ANNOTATION_FILE, -annotation-file ANNOTATION_FILE
                        Path to a .json file containing the ground-truth
                        annotations. The file must be formatted according to
                        the COCO annotation file guidelines.
  --accumulate          Accumulate the results for all images?
```
Note that the annotations for the evaluation dataset must be on the [COCO format](http://cocodataset.org/#format-data).

## Training a new model
The current implementation supports fine-tuning the COCO model from [matterport/Mask_RCNN](https://github.com/matterport/Mask_RCNN) on the classes
we are interested in.

### Set-up
1. Make sure that the weight file [mask_rcnn_coco.h5](https://github.com/matterport/Mask_RCNN/releases/download/v2.0/mask_rcnn_coco.h5) is downloaded,
and placed in the `models` directory.
2. Initialize the `Mask_RCNN` submodule by running
    ```Bash
    git submodule init
    git submodule update
    ```
   Note: This step can be skipped if you cloned the repository with the `--recursive-submodules` flag.
3. Install the `mrcnn` package:
    ```Bash
    cd Mask_RCNN
    pip install -e .
    ```
### Downloading the COCO dataset
1. Download and extract [train2017.zip](http://images.cocodataset.org/zips/train2017.zip) and place the images in `data\train\coco\train2017`.
2. Download and extract [val2017.zip](http://images.cocodataset.org/zips/val2017.zip) and place the images in `data\train\coco\val2017`.
3. Download and extract [the annotations](http://images.cocodataset.org/annotations/annotations_trainval2017.zip) and place the files in `data\train\coco\annotations`.

### Training
After the steps above are completed, the training can be invoked by running training script:
```
usage: python src.train.train [-h] [--data-folder DATA_FOLDER] [--data-year DATA_YEAR]
                              [--resume RESUME] [--summary-file SUMMARY_FILE]
                              [--enable-augmentation]

optional arguments:
  -h, --help            show this help message and exit
  --data-folder DATA_FOLDER
                        Path to data. The folder is expected to contain the following directories:
                        - `train`: Contains the training images
                        - `val`: (Optional) Contains the validation images
                        - `annotations`: Contains COCO-formatted .json files with annotations.
                        Training annotations should be in `annotations/instances_train.json`
  --data-year DATA_YEAR
                        Optional year-identifier for the data folder. The year will be appended
                         to the folder and annotation names described above.
  --resume RESUME       If specified, the training will be resumed from this weight file.
  --summary-file SUMMARY_FILE
                        Optional filename for writing the model summary.
  --enable-augmentation
                        Enable image augmentation during training?
```
The training process will save the weights of the model after each epoch. These will be stored in `models/train/car_coco<timestamp>/mask_rcnn_car_coco_<epoch>.h5`.

#### Resuming a training session
If you want to resume a previously interrupted training session, you can use the `--resume` parameter in the training script:
```Bash
python -m src.train.train --resume \path\to\last\saved\weights.h5
```

#### Training configuration
Configuration variables for training are available in `src/train/train_config.py`.

### Using a trained model in the Masker
The weights used in `src.Masker.Masker` are specified by the `weights_file` parameter in `config.py`.
Use this parameter to change the weighs used in the masking model.

