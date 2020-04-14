import os
from src.Logger import LOGGER


class Paths:
    def __init__(self, base_input_dir, base_mirror_dirs, input_dir, mirror_dirs, filename):
        self.base_input_dir = base_input_dir
        self.base_mirror_dirs = base_mirror_dirs

        self.input_dir = input_dir
        self.mirror_dirs = mirror_dirs
        self.filename = filename

        # Names of .json and .webp files.
        self.json_filename = os.path.splitext(filename)[0] + ".json"
        self.webp_filename = os.path.splitext(filename)[0] + ".webp"

        # Paths to input files
        self.input_file = os.path.join(self.input_dir, self.filename)
        self.input_json = os.path.join(self.input_dir, self.json_filename)
        self.input_webp = os.path.join(self.input_dir, self.webp_filename)

        # Paths to output files
        if len(self.mirror_dirs) > 0:
            self.base_output_dir = self.base_mirror_dirs[0]
            self.output_dir = self.mirror_dirs[0]
            self.output_file = os.path.join(self.output_dir, self.filename)
            self.output_json = os.path.join(self.output_dir, self.json_filename)
            self.output_webp = os.path.join(self.output_dir, self.webp_filename)
        else:
            self.base_output_dir = self.output_dir = None
            self.output_file = self.output_json = self.output_webp = None

        # Paths to archive files
        if len(self.mirror_dirs) > 1:
            self.base_archive_dir = self.base_mirror_dirs[1]
            self.archive_dir = self.mirror_dirs[1]
            self.archive_file = os.path.join(self.archive_dir, self.filename)
            self.archive_json = os.path.join(self.archive_dir, self.json_filename)
            self.archive_webp = os.path.join(self.archive_dir, self.webp_filename)
        else:
            self.base_archive_dir = self.archive_dir = None
            self.archive_file = self.archive_json = self.archive_webp = None

        # Remaining mirror paths
        if len(self.mirror_dirs) > 2:
            self.remaining_mirror_dirs = self.mirror_dirs[2:]
        else:
            self.remaining_mirror_dirs = None

    @property
    def error_output_dir(self):
        error_extension = "_error"
        # Add the extension to the base output path
        base_error_path = self.base_output_dir + error_extension
        # Determine the error output path by replacing the base output path with the base error output path.
        error_output_dir = self.output_dir.replace(self.base_output_dir, base_error_path)
        return error_output_dir

    @property
    def error_output_file(self):
        return os.path.join(self.error_output_dir, self.filename)


class TreeWalker:
    """
    Traverses a file-tree and finds all valid files with extension `ext`.
    """
    def __init__(self, input_folder, mirror_folders, skip_webp=True, precompute_paths=True, ext="jpg"):
        """
        Initialize the file-tree walker.

        :param input_folder: Root directory for tree traversal.
        :type input_folder: str
        :param mirror_folders: List of directories to traverse in parallel to `input_folders`.
        :type mirror_folders: list of str
        :param skip_webp: Skip images that already have an associated .webp file in `output_folder`.
        :type skip_webp: bool
        :param precompute_paths: Traverse the whole tree during initialization? When this is true, `TreeWalker.walk`
                                 will return an iterator. Otherwise it will return a generator.
        :type precompute_paths: bool
        :param ext: File extension for files returned by `TreeWalker.walk`.
        :type ext: str
        """
        LOGGER.info(__name__, f"Initializing file tree walker at '{input_folder}'.")
        self.input_folder = input_folder
        self.mirror_folders = mirror_folders
        self.skip_webp = skip_webp
        self.precompute_paths = precompute_paths
        self.ext = ext
        self.n_valid_images = self.n_skipped_images = 0

        if self.precompute_paths:
            LOGGER.info(__name__, "Precomputing paths...")
            self.paths = [p for p in self._walk()]
            LOGGER.info(__name__, f"Found {self.n_valid_images} valid image paths.")
            if self.n_skipped_images > 0:
                LOGGER.info(__name__, f"Found {self.n_skipped_images} images with masks. These will be skipped.")
        else:
            self.paths = None

    def _to_webp(self, path):
        return path[:-len(self.ext)] + "webp"

    def _get_mirror_dirs(self, input_dir):
        return [input_dir.replace(self.input_folder, mirror_base, 1) for mirror_base in self.mirror_folders]

    def _path_is_valid(self, input_dir, mirror_dirs, filename):
        if not filename.endswith(self.ext):
            return False

        input_filepath = os.path.join(input_dir, filename)
        if not os.access(input_filepath, os.R_OK):
            LOGGER.info(__name__, f"Could not read image file '{input_filepath}'")
            return False

        if self.skip_webp:
            webp_path = os.path.join(input_dir, self._to_webp(filename))
            if os.path.exists(webp_path):
                LOGGER.info(__name__, f"Mask already found for '{input_filepath}' at '{webp_path}'.")
                self.n_skipped_images += 1
                return False

        self.n_valid_images += 1
        return True

    def _walk(self):
        for input_dir, _, file_names in os.walk(self.input_folder):
            mirror_dirs = self._get_mirror_dirs(input_dir)
            for filename in file_names:
                if self._path_is_valid(input_dir, mirror_dirs, filename):
                    # yield input_dir, mirror_dirs, filename
                    yield Paths(base_input_dir=self.input_folder, base_mirror_dirs=self.mirror_folders,
                                input_dir=input_dir, mirror_dirs=mirror_dirs, filename=filename)

    def walk(self):
        """
        Traverse the file tree in `input_folder`.

        :return: If `precompute_paths` is True, this will simply return an iterator whose elements are tuples with
                 elements:

                     - Full path to the current directory in `input_dir`
                     - Full path to the corresponding directories in `mirror_dirs`
                     - Name of current `ext`-file

                 Otherwise, it will call a generator returning a tuple with the same elements as above.
        :rtype: iterator | tuple of str
        """
        if not self.precompute_paths:
            return self._walk()
        else:
            return iter(self.paths)
