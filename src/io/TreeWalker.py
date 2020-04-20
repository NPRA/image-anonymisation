import os
import json
from uuid import uuid4

import config
from src.Logger import LOGGER


class Paths:
    """
    Object which holds the path-information about an image. `src.io.TreeWalker.TreeWalker.walk` returns instances of
    this class. Input directories and mirror directories and files are all available through dot-syntax.

    :param base_input_dir: Base directory for input files.
    :type base_input_dir: str
    :param base_mirror_dirs: Base directories for mirror files. The first element is assumed to be the output directory.
                             The second element is assumed to be the archive directory.
    :type base_mirror_dirs: list of str
    :param input_dir: Directory containing the file represented by the object.
    :type input_dir: str
    :param mirror_dirs: Mirror directories for the file represented by the object.
    :type mirror_dirs: list of str
    :param filename: Name of file represented by the object
    :type filename: str
    """
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

        self.cache_file = os.path.join(config.CACHE_DIRECTORY, str(uuid4()) + ".json")

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

    def create_cache_file(self):
        json_contents = {k: v for k, v in self.__dict__.items() if isinstance(k, str) or k is None}
        with open(self.cache_file, "w") as f:
            json.dump(json_contents, f)

    def remove_cache_file(self):
        if os.path.isfile(self.cache_file):
            os.remove(self.cache_file)
        else:
            LOGGER.warning(__name__, f"Attempted to remove cache file '{self.cache_file}', but is does not exist.")


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
            webp_path = os.path.join(mirror_dirs[0], self._to_webp(filename))
            if os.path.exists(webp_path):
                LOGGER.debug(__name__, f"Mask already found for '{input_filepath}' at '{webp_path}'.")
                self.n_skipped_images += 1
                return False

        self.n_valid_images += 1
        return True

    def _walk(self):
        for input_dir, _, file_names in os.walk(self.input_folder):
            mirror_dirs = self._get_mirror_dirs(input_dir)
            for filename in file_names:
                if self._path_is_valid(input_dir, mirror_dirs, filename):
                    yield Paths(base_input_dir=self.input_folder, base_mirror_dirs=self.mirror_folders,
                                input_dir=input_dir, mirror_dirs=mirror_dirs, filename=filename)

    def walk(self):
        """
        Traverse the file tree in `input_folder`.

        :return: If `precompute_paths` is True, this will simply return an iterator where each element is an instance of
                 `src.io.TreeWalker.Paths`.

                 Otherwise, it will call a generator returning the objects described above.
        :rtype: iterator | tuple of str
        """
        if not self.precompute_paths:
            return self._walk()
        else:
            return iter(self.paths)
