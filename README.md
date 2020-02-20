# image-anonymisation
Using pre-trained tensorflow models to remove vehicles and people from images

## Getting started
#### Clone or download the code

**Option 1:** 
With Git: `git clone https://github.com/NPRA/image-anonymisation.git` (Requires `git` to be installed)

**Option 2:**
Manual download: Select "Clone or download" and "Download ZIP" above. Then extract the downloaded archive to a suitable 
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
`tf-object detection` can be installed by running included PowerShell script Anaconda PowerShell Prompt 
(make sure that the `image-anonymisation` environment is activated before running the script.):

```Bash
.\install-tf-object-detection.ps1
```
  
## Usage
The script will recursively search \<inputfolder\> for .jpg files and mask off all cars, trucks, busses, bikes, motorcycles and people it finds in the photos. The recursive folder structure will be recreated in the \<outputfolder\>.
```Bash
python maskerMappe.py -i <inputfolder> -o <outputfolder>
```

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