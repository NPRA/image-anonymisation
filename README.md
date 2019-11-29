# image-anonymisation
Using pre-trained tensorflow models to remove vehicles and people from images

## Installation
If you have a CUDA capable GPU I highly suggest you install CUDA and cuDNN to speed up the script.

### Prerequisites
- python3.6 (or higher)
- pip

### GPU
If you want to use your GPU (suggested):
```
pip3 install numpy==1.16.4 tensorflow-gpu tf-object-detection pillow
```

### CPU
If you don't have a CUDA capable GPU you can still run the script on the CPU (Warning: it's going to be slow)
```Bash
pip3 install numpy==1.16.4 tensorflow tf-object-detection pillow
```
### Usage
The script will recursively search \<inputfolder\> for .jpg files and mask off all cars, trucks, busses, bikes, motorcycles and people it finds in the photos. The recursive folder structure will be recreated in the \<outputfolder\>.
```Bash
python3 maskerMappe.py -i <inputfolder> -o <outputfolder>
```
