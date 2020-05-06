"""
Configuration variables.
"""

# ======================================
# Miscellaneous configuration parameters
# ======================================

#: Apply the mask to the output image?
draw_mask = True

#: Delete the original image from the input directory when the masking is completed?
delete_input = False

#: Recompute masks even though a .webp file exists in the input folder.
force_remask = False

#: When `lazy_paths = True`, traverse the file tree during the masking process.
#: Otherwise, all paths will be identified and stored before the masking starts.
lazy_paths = False

#: Number of seconds to wait before (re)trying to access a file/directory which cannot currently be reached. This
#: applies to both reading input files, and writing output files.
file_access_retry_seconds = 10

#: Total number of seconds to wait before giving up on accessing a file/directory which cannot currently be reached.
#: This also applies to both reading input files, and writing output files.
file_access_timeout_seconds = 60

#: Timestamp format. See https://docs.python.org/3.7/library/datetime.html#strftime-strptime-behavior for more
#: information.
datetime_format = "%Y-%m-%d %H.%M.%S"

#: Name of the log file. `{datetime}` will be replaced with a timestamp formatted as `datetime_format`. `{hostname}`
#: will be replaced with the host name.
log_file_name = "{datetime} {hostname}.log"

#: Logging level for the application. This controls the log level for terminal logging and file logging (if it is
#: enabled). Must be one of {"DEBUG", "INFO", "WARNING", "ERROR"}.
log_level = "DEBUG"


# ===================
# File I/O parameters
# ===================

#: Write the EXIF .json file to the output (remote) directory?
remote_json = True

#: Write the EXIF .json file to the input (local) directory?
local_json = False

#: Write the EXIF .json file to the archive directory?
archive_json = False

#: Write mask file to the output (remote) directory?
remote_mask = True

#: Write the mask file to the input (local) directory?
local_mask = False

#: Write mask file to the archive directory?
archive_mask = False

# =====================================
# Parameters for asynchronous execution
# =====================================

#: Enable asynchronous post-processing? When True, the file exports (anonymised image, mask file and JSON file) will be
#: executed asynchronously in order to increase processing speed.
enable_async = True

#: Maximum number of asynchronous workers allowed to be active simultaneously. Should be <= (CPU core count - 1)
max_num_async_workers = 2


# ================================
# Parameters for the masking model
# ================================

#: Type of masking model. Currently, there are three available models with varying speed and accuracy.
#: The slowest model produces the most accurate masks, while the masks from the medium model are slightly worse.
#: The masks from the "Fast" model are currently not recommended due to poor quality. Must be either "Slow", "Medium" or
#: "Fast". "Medium" is recommended.
#: Default: "Medium"
model_type = "Medium"

#: Approximate number of pixels for mask dilation. This will help ensure that an identified object is completely covered
#: by the corresponding mask. Set `mask_dilation_pixels = 0` to disable mask dilation.
#: Default: `4`
mask_dilation_pixels = 4

#: Maximum number of pixels in images to be processed by the masking model. If the number of pixels exceeds this value,
#: it will be resized before the masker is applied. This will NOT change the resolution of the output image.
max_num_pixels = 5E7


# ===============================================================
# Parameters controlling the appearance of the anonymised regions
# ===============================================================

#: "RGB tuple (0-255) indicating the masking color. Setting this option will override the
#: colors specified below. Example: Setting `mask_color = (50, 50, 50)` will make all masks
#: dark gray.
mask_color = None

#: Blurring coefficient (1-100) which specifies the degree of blurring to apply within the
#: mask. When this parameter is specified, the image will be blurred, and not masked with a
#: specific color. Set `blur = None` to disable blurring, and use colored masks instead.
#: Default: `15`
blur = 15

#: Convert the image to grayscale before blurring? (Ignored if blurring is disabled)
#: Default: `True`
gray_blur = True

#: Normalize the gray level within each mask after blurring? This will make bright colors indistinguishable from dark
#: colors. NOTE: Requires `gray_blur=True`
#: Default: True
normalized_gray_blur = True


# ====================
# E-mail configuration
# ====================
# Note: E-mail sending requires additional configuration. This is documented in the README.

#: Send an email if the program exits abnormally due to an uncaught exception.
uncaught_exception_email = False

#: Send an email if a processing error is encountered, but the program is able to continue
processing_error_email = False

#: Send an email when the anonymisation finishes normally.
finished_email = False


# ======================
# Database configuration
# ======================
# Note: Database writing requires additional configuration. This is documented in the README.

# When `write_exif_to_db = True`, the EXIF data will be written as a row to an Oracle database. The `src.db` module is
# responsible for the database writing.

#: Write the EXIF data to the database?
write_exif_to_db = True

#: Maximum number of rows to accumulate locally before writing all accumulated rows to the database.
db_max_n_accumulated_rows = 2

#: Format of the "Mappenavn" column in the database.
db_folder_name = "Vegbilder/{fylke}/{aar}/{strekningreferanse}/F{feltkode}_{aar}_{maaned}_{dag}"