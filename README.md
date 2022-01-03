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
2. Run the installer as Administrator
3. Select "C++ build tools" during installation.

#### Installing Anaconda
1. Download the [installer](https://www.anaconda.com/distribution/).
2. Run installer as Administrator.
3. Select "Install for all users" during installation.

#### Creating the conda-environment
1. Open an "Anaconda PowerShell Prompt" as Administrator.

2. In the Anaconda PowerShell Prompt, navigate to the root directory of the cloned repository.

3. Create the conda-environment by running:
    ```Bash
    conda env create -f environment.yml
    ```

   This will create a new environment named `image-anonymisation`.
4. Activate the environment by running:
    ```Bash
    conda activate image-anonymisation
    ```
   NOTE: If you are unable to run the script in a terminal with conda initialized, you can use the
   `bin/run.ps1` (PowerShell only) script, with the `-conda_path` argument to invoke the application.

#### Installing the Oracle Instant Client
[Oracle Instant Client](https://www.oracle.com/database/technologies/instant-client/downloads.html)
(or any other Oracle Database installation which contains the Oracle Client libraries) is required when
using the optional database functionality. Download the client, and add the path to the `instantclient_xx_x`
folder to the `PATH` environment variable.

NOTE: If you do not want to modify the `PATH` variable, you can use `bin/run.ps1`, with the `-oracle_path` argument
to invoke the application instead.

#### Proxy setup
If Anaconda fails to create the environment above due to a HTTP error, you might need to configure Anaconda to use
a proxy. Set the following environment variables:
```
HTTPS_PROXY=<your_proxy>
```
and
```
HTTP_PROXY=<your_proxy>
```
(These are only required for installation and model downloading, and can therefore be removed after the environment has
been created, and the model file has been downloaded.)

You should now be able to create the environment with the same command as above.

### Manual proxy configuration in conda and pip

If you are unable to set the environment variables, you can specify the proxy to anaconda and pip directly.

1. In `~/.condarc` add the following lines:
    ```yaml
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
    pip install cx-oracle==7.3.0 func-timeout==4.3.5 iso8601==0.1.12 m2r==0.2.1 opencv-python==4.2.0.32 pillow==7.0.0 --proxy <your_proxy>
    ```

   The `webp` package requires a little more work. First, install `importlib_resources` and `conan`:
    ```Bash
    pip install importlib_resources>=1.0.0  conan>=1.8.0 --proxy <your_proxy>
    ```

   Now, `conan` has to be configured to use the proxy server. In `~/.conan/conan.conf` under `[proxies]`, add the lines:
    ```python
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
                          [-l LOG_FOLDER] [--skip-clear-cache] [-k CONFIG_FILE]

Image anonymisation

optional arguments:
  -h, --help            show this help message and exit
  -i INPUT_FOLDER, --input-folder INPUT_FOLDER
                        Base directory for input images.
  -o OUTPUT_FOLDER, --output-folder OUTPUT_FOLDER
                        Base directory for masked (output) images and metadata
                        files
  -a ARCHIVE_FOLDER, --archive-folder ARCHIVE_FOLDER
                        Optional base directory for archiving original images.
  -l LOG_FOLDER, --log-folder LOG_FOLDER
                        Optional path to directory of log file. The log file
                        will be named <log\folder>\<timestamp> <hostname>.log
  --skip-clear-cache    Disables the clearing of cache files at startup.
  -k CONFIG_FILE        Path to custom configuration file. See the README for
                        details. Default is config\default_config.yml
```

Note: Make sure that the conda environment is activated before executing the command above.

#### Batch script and PowerShell script.
The anonymisation can be ran without manually activating the conda environment, by running either `bin/run-with-prompt.bat` or `bin/run.ps1`.
The latter also works when conda is not initialized in the shell, as long as the `conda_path` parameter is specified correctly.

## Documentation
The HTML documentation can be built from the `docs` directory by running
```
.\make.bat html
```
For a detailed in-depth documentation of the architecture and system, look here: [Image Anonymisation Wiki](docs/wiki/WikiDocs.md) 

## Configuration
The user-specifiable configuration parameters can be found in [config/default_config.yml](config/default_config.yml). The available parameters are listed below.

#### Miscellaneous configuration parameters
* `data_eier`: The name of who owns the data. E.g. "Statens Vegvesen"
* `image_type`: The type of images to be processed. Either "planar" or "360".
* `draw_mask`: Apply the mask to the output image?
* `delete_input`: Delete the original image from the input directory when the masking is completed?
* `force_remask`: Recompute masks even though a .webp file exists in the output folder.
* `lazy_paths`: When `lazy_paths = True`, traverse the file tree during the masking process. Otherwise, all paths will be identified and stored before the masking starts.
* `file_access_retry_seconds`: Number of seconds to wait before (re)trying to access a file/directory which cannot currently be reached. This applies to both reading input files, and writing output files.
* `file_access_timeout_seconds`: Total number of seconds to wait before giving up on accessing a file/directory which cannot currently be reached. This also applies to both reading input files, and writing output files.
* `datetime_format`: Timestamp format. See https://docs.python.org/3.7/library/datetime.html#strftime-strptime-behavior for more information.
* `log_file_name`: Name of the log file. `{datetime}` will be replaced with a timestamp formatted as `datetime_format`. `{hostname}` will be replaced with the host name.
* `log_level`: Logging level for the application. This controls the log level for terminal logging and file logging (if it is enabled). Must be one of {"DEBUG", "INFO", "WARNING", "ERROR"}.
* `application_version`: Version number for the application. Will be written to JSON files and database.
* `exif_mappenavn`: Formatter for `mappenavn` in the JSON file. `relative_input_dir` is the path to the folder containing the image, relative to `exif_top_dir` below. For instance, if the image is located at `C:\Foo\Bar\Baz\Hello\World.jpg`, and `exif_top_dir = Bar`, then `relative_input_dir` will be `Baz\Hello`.
* `exif_top_dir`: Top directory for `relative_input_dir`. See above for an explanation.

#### File I/O parameters
* `remote_json`: Write the EXIF .json file to the output (remote) directory?
* `local_json`: Write the EXIF .json file to the input (local) directory?
* `archive_json`: Write the EXIF .json file to the archive directory?
* [Deprecated] `remote_mask`: Write mask file to the output (remote) directory?
* [Deprecated] `local_mask`: Write the mask file to the input (local) directory?
* [Deprecated] `archive_mask`: Write mask file to the archive directory?
* `remote_preview`: Write the preview file to the output (remote) directory
* `local_preveiw`: Write the preview file to the input (local) directory
* `archive_directory`: Write the preview file to the archive directory
* `separate_preview_directory`: Path to the location in where only the previews are stored.
* `preview_dim`: The dimensions on the form [height, width] of the thumbnail.
* `preview_center`: The percentage of each dimension of the original image where the center of the thumbnail should be located

#### Parameters for asynchronous execution
* `enable_async`: Enable asynchronous post-processing? When True, the file exports (anonymised image, mask file and JSON file) will be executed asynchronously in order to increase processing speed.
* `max_num_async_workers`: Maximum number of asynchronous workers allowed to be active simultaneously. Should be <= (CPU core count - 1)

#### Parameters for the masking model
* `model_type`: Type of masking model. Currently, there are three available models with varying speed and accuracy. The slowest model produces the most accurate masks, while the masks from the medium model are slightly worse. The masks from the "Fast" model are currently not recommended due to poor quality. Must be either "Slow", "Medium" or "Fast". "Medium" is recommended. Default: "Medium"
* `mask_dilation_pixels`: Approximate number of pixels for mask dilation. This will help ensure that an identified object is completely covered by the corresponding mask. Set `mask_dilation_pixels = 0` to disable mask dilation. Default: `4`
* `max_num_pixels`: Maximum number of pixels in images to be processed by the masking model. If the number of pixels exceeds this value, it will be resized before the masker is applied. This will NOT change the resolution of the output image.
* `use_cutouts`: Apply the cutout 'sliding window' method on the masking.
* `cutout_step_factor`: How many steps/pixels the sliding window should move in each direction [height,width] .
* `cutout_dim_downscale`: The downscale of the dimensions of the cutout by [height, width]. 
E.g if the value is [3,2], the height of the cutout is a third of the height of the original image, and the width is half the size.
#### Parameters controlling the appearance of the anonymised regions
* `mask_color`: "RGB tuple (0-255) indicating the masking color. Setting this option will override the colors specified below. Example: Setting `mask_color = [50, 50, 50]` will make all masks dark gray.
* `blur`: Blurring coefficient (1-100) which specifies the degree of blurring to apply within the mask. When this parameter is specified, the image will be blurred, and not masked with a specific color. Set `blur = None` to disable blurring, and use colored masks instead. Default: `15`
* `gray_blur`: Convert the image to grayscale before blurring? (Ignored if blurring is disabled) Default: `True`
* `normalized_gray_blur`: Normalize the gray level within each mask after blurring? This will make bright colors indistinguishable from dark colors. NOTE: Requires `gray_blur=True` Default: True

#### E-mail configuration
* `uncaught_exception_email`: Send an email if the program exits abnormally due to an uncaught exception.
* `processing_error_email`: Send an email if a processing error is encountered, but the program is able to continue
* `finished_email`: Send an email when the anonymisation finishes normally.
* `email_attach_log`: Attach the log file to emails?

#### Database configuration
* `write_exif_to_db`: Write the EXIF data to the database?
* `db_max_n_accumulated_rows`: Maximum number of rows to accumulate locally before writing all accumulated rows to the database.
* `db_max_n_errors`: If the number of failed insertions/updates exceeds this number, a RuntimeError will be raised.
* `db_max_cache_size`: If the number of cached rows exceeds this number, a RuntimeError will be raised.

### Custom configuration file
The application supports custom configuration files with the same structure as `config/default_config.yml`.
Note that custom configuration files should define all variables defined in `config/default_config.yml`.
Use the `-k` argument to specify a custom config file. (See [Usage](#usage) for details.)

## Email notifications
The application can send an email notification on an abnormal exit, a processing error, or on completion. These noticifations can be enabled/disabled
with the flags `uncaught_exception_email`, `processing_error_email` and `finished_email`, available in `config.py`. The email sending feature requires a
sender, receiver(s), and an SMTP-server in order to work. These can be specified by creating a file named `email_config.py` in the `config` directory, which
contains the following:

```python
# Sender's address
from_address = "noreply@somedomain.com"
# Receiver address(es)
to_addresses = ["receiver1@domain.com", "receiver2@domain.com", ...]
# SMTP-server address
smtp_host = "<smtp server address>"
# SMTP-server port
port = <smtp port>
```

## EXIF data to database
### Configuring the connection
Use the `scripts.db.create_db_config` script to create a database configuration file:
```
usage: python -m scripts.db.create_db_config [-h] --user USER --password PASSWORD --dsn DSN
                                             [--schema SCHEMA] --table_name TABLE_NAME

Create the db_config.py file, which configures the database connection.

optional arguments:
  -h, --help            show this help message and exit
  --user USER           Database username
  --password PASSWORD   Database password (will be encrypted)
  --dsn DSN             Data source name (DSN)
  --schema SCHEMA       Optional schema. Default is None
  --table_name TABLE_NAME
                        Database table name.
```

### Table specification
The program expects to find the table layout in the YAML file `config/db_tables/<table_name>.yml`. The file should contain the following keys:

* `pk_column`: The name of the `PRIMARY KEY` column.
* `columns`: A list of columns, where each element has the keys:
  * `name`: Name of the column.
  * `dtype`: Oracle SQL datatype for the column.
  * `formatter`: Name of a function in [formatters.py](src/db/formatters.py), which returns the column value from the given JSON-contents.
  * `extra`: Extra column contstraints, such as `NOT NULL` or `PRIMARY KEY`.
  * `spatial_metadata`: This is only required if `dtype` is `SDO_GEOMETRY`. Contains geometric metadata about the objects in the column.
    Expected keys are:
    * `dimension`: Number of dimensions. Must be `2` or `3`.
    * `srid`: SRID for the object's coordinate system.
    * `dim_elements`: A list where each element has `name`, `min`, `max` and `tol`. The elements are used to create the `DIMINFO` array in the spatial metadata table.

For a table named `my_table`, the contents of `config/db_tables/my_table.yml` might look like:
```yaml
pk_column: UUID
columns:
  # ID column. Used as primary key
  - name: UUID
    dtype: VARCHAR(255)
    formatter: uuid
    extra: PRIMARY KEY
  
  # Timestamp column
  - name: Timestamp
    dtype: DATE
    formatter: timestamp
    extra: NOT NULL
  
  # Optional position column
  - name: Position
    dtype: SDO_GEOMETRY
    formatter: position
    extra:
    spatial_metadata:
      dimension: 2
      srid: 4326
      dim_elements:
        - name: Longitude
          min: -180
          max: 180
          tol: 0.5

        - name: Latitude
          min: -90
          max: 90
          tol: 0.5  
```

Note that the example above expects to find the functions `uuid`, `timestamp` and `position`, in `src.db.formatters`.

### Writing to the database
When the parameters above have been configured correctly, the EXIF data can be written to the database by using the `json_to_db` script:
```
python -m scripts.db.json_to_db -i <base input folder>
```
This will recursively traverse `<base input folder>`, read all .json files, and write the contents to the specified database.

Database writing can also be done automatically during anonymisation. This is enabled by setting `write_exif_to_db = True` in `config.py`.

## Tests
The `tests/` directory provides a large number of tests which can be used to check that the application works as expected. Use the `pytest` command
to run the tests:

```Bash
pytest tests
```
Note that this will skip the tests marked as `slow` and `db`. Add the `--run-slow` to run the `slow` tests, and `--run-db` to run the `db` tests.

### Setting up the test database
The tests marked with `db` requires a test database to be running locally. The test database is a
[Single instance Oracle database (18c XE), running in a docker container](https://github.com/oracle/docker-images/tree/master/OracleDatabase/SingleInstance).
[Docker](https://www.docker.com/) is therefore required to build and run the test database.

To build the docker image, run:
```
.\tests\db\setup\build.ps1
```

To start the test database, run:
```
.\tests\db\setup\start.ps1
```

Note that the tests marked with `db` will fail if the test database is not running.

## Extra scripts
The following extra scripts are available:
* `scripts.create_json`: Traverses a directory tree and creates JSON-files for all `.jpg` files found in the tree.
* `scripts.check_folders`: Traverses a set of input/output/archive folders and checks that all files are present/not present, as specified in the config file.
* `scripts.evaluate`: Evaluates the current model on a specified testing dataset. Requires `pycocotools` to be installed.
* `scripts.db.create_table`: Creates the specified database table.
* `scripts.db.insert_geom_metadata`: Inserts the appropriate metadata for the specified table into the `MDSYS.USER_GEOM_METADATA` view.
* `scripts.db.json_to_db`: Traverses a directory tree and writes the contents of all found `.json` files to the specified database table.
* `scripts.create_preview`: Traverses a directory tree and creates preview images of all `.jpg` files found in the tree. 

Each script can be invoked by running:
```
python -m <script> <args>
```
Use the `-h` argument to get a description for each script, and a list of possible arguments.

