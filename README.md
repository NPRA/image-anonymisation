# image-anonymisation
Using pre-trained tensorflow models to remove vehicles and people from images

## Getting started
Clone (`git clone https://github.com/NPRA/image-anonymisation.git`), or download (and extract) this repository.

#### Installing Anaconda
1. Download the [installer](https://www.anaconda.com/distribution/).
1. Run installer as Administrator.
1. Select "Install for all users" during installation.

#### Creating the conda environment
1. Open an "Anaconda PowerShell Prompt" as Administrator.
1. In the Anaconda PowerShell Prompt, navigate to the root directory of the cloned repository.
1. Create the environment: `conda env create -f environment.yml`. This will create a new environment named `image-anonymisation`.
1. Activate the environment: `conda activate image-anonymisation`.

#### Installing `tf_object_detection`
Run the PowerShell script `install-tf-object-detection.ps1` in the Anaconda PowerShell Prompt.  
 
## Usage
The script will recursively search \<inputfolder\> for .jpg files and mask off all cars, trucks, busses, bikes, motorcycles and people it finds in the photos. The recursive folder structure will be recreated in the \<outputfolder\>.
```Bash
python maskerMappe.py -i <inputfolder> -o <outputfolder>
```
