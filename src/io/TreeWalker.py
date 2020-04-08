import os
from src.Logger import LOGGER


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

    def _get_mirror_paths(self, input_path):
        return [input_path.replace(self.input_folder, mirror_base, 1) for mirror_base in self.mirror_folders]

    def _path_is_valid(self, input_path, mirror_paths, filename):
        if not filename.endswith(self.ext):
            return False

        input_filepath = os.path.join(input_path, filename)
        if not os.access(input_filepath, os.R_OK):
            LOGGER.info(__name__, f"Could not read image file '{input_filepath}'")
            return False

        if self.skip_webp:
            webp_path = os.path.join(input_path, self._to_webp(filename))
            if os.path.exists(webp_path):
                LOGGER.info(__name__, f"Mask already found for '{input_filepath}' at '{webp_path}'.")
                self.n_skipped_images += 1
                return False

        self.n_valid_images += 1
        return True

    def _walk(self):
        for input_path, _, file_names in os.walk(self.input_folder):
            mirror_paths = self._get_mirror_paths(input_path)
            for filename in file_names:
                if self._path_is_valid(input_path, mirror_paths, filename):
                    yield input_path, mirror_paths, filename

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
