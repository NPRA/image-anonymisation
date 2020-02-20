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
1. In the Anaconda PowerShell Prompt, navigate to the root directory of the cloned repository.
1. Create the conda-environment by running: 
    ```Bash
    conda env create -f environment.yml
    ```
    This will create a new environment named `image-anonymisation`.
1. Activate the environment by running: 
    ```Bash
    conda activate image-anonymisation
    ```

#### Installing `tf_object_detection`
**Note:** The following step requires `git` to be installed. If `git` is not installed, it can be installed
to the conda-environment directly by running `conda install git`.
 
`tf-object detection` can be installed by running included PowerShell script Anaconda PowerShell Prompt 
(make sure that the `image-anonymisation` environment is activated before running the script.):

```Bash
.\install-tf-object-detection.ps1
```
  
## Usage
The program will traverse the file-tree rooted at the input folder, and mask all .jpg images within the tree. The masked 
images will be written to an output directory with identical structure as the input folder. The program should be  
executed as a python-module from the root directory:
```Bash
pyhton -m src.main -i <input folder> -o <output folder> <options>
```
See below for a complete usage description.
```Bash
usage: main.py [-h] [-i INPUT_FOLDER] [-o OUTPUT_FOLDER] [-m] [-rj] [-lj]
               [-rm] [-lm] [--force-remasking] [--lazy-paths]
               [--mask-color MASK_COLOR MASK_COLOR MASK_COLOR]

Image anonymisation

optional arguments:
  -h, --help            show this help message and exit
  -i INPUT_FOLDER, --input-folder INPUT_FOLDER
                        Base directory for input images.
  -o OUTPUT_FOLDER, --output-folder OUTPUT_FOLDER
                        Base directory for masked (output) images and metadata
                        files
  -m, --draw-mask       Apply the mask to the image file?
  -rj, --remote-json    Write the EXIF .json file to the output (remote)
                        directory?
  -lj, --local-json     Write the EXIF .json file to the input (local)
                        directory?
  -rm, --remote-mask    Write mask file to the output (remote) directory?
  -lm, --local-mask     Write the mask file to the input (local) directory?
  --force-remasking     When this flag is set, the masks will be recomputed
                        even though the .webp file exists.
  --lazy-paths          When this flag is set, the file tree will be traversed
                        during the masking process. Otherwise, all paths will
                        be identified and stored before the masking starts
  --mask-color MASK_COLOR MASK_COLOR MASK_COLOR
                        RGB tuple [0-255] indicating the masking color.
                        Setting this option will override the colors in
                        config.py.
```

#### Additional configuration
Additional configuration variables are listed in `src/config.py`. Edit these at your own risk! 


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