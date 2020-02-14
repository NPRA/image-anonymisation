mkdir tmp
cd tmp

# Clone the TensorFlow/models repo
git clone https://github.com/tensorflow/models
# cp -r ..\TensorFlow\models .

# Get protobuf
wget https://github.com/protocolbuffers/protobuf/releases/download/v3.11.3/protoc-3.11.3-win32.zip -OutFile protoc-3.11.3-win32.zip
Expand-Archive -LiteralPath protoc-3.11.3-win32.zip -DestinationPath .
cp bin/protoc.exe models/research

# Install
cd models\research
Get-ChildItem object_detection/protos/*.proto | foreach {protoc "object_detection/protos/$($_.Name)" --python_out=.}
python setup.py build
python setup.py install

# Cleanup
cd ..\..\..
rm -r tmp
