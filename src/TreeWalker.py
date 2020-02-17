import os
import logging


LOGGER = logging.getLogger(__name__)


class TreeWalker:
    def __init__(self, input_folder, output_folder, skip_webp=True):
        LOGGER.info(f"Initializing file tree walker at '{input_folder}'.")
        self.input_folder = input_folder
        self.output_folder = output_folder
        self.skip_webp = skip_webp

    @staticmethod
    def _jpg_to_webp(path):
        return path[:-4] + ".webp"

    def _get_output_path(self, input_path):
        return input_path.replace(self.input_folder, self.output_folder, 1)

    def _path_is_valid(self, input_path, output_path, filename):
        if not filename.endswith(".jpg"):
            return False

        input_filepath = os.path.join(input_path, filename)
        if not os.access(input_filepath, os.R_OK):
            LOGGER.info(f"Could not read image file '{input_filepath}'")
            return False

        if self.skip_webp:
            webp_path = os.path.join(output_path, self._jpg_to_webp(filename))
            if os.path.exists(webp_path):
                LOGGER.info(f"Mask already found for '{input_filepath}' at '{webp_path}'.")
                return False

        return True

    def walk(self):
        for input_path, _, file_names in os.walk(self.input_folder):
            output_path = self._get_output_path(input_path)
            for filename in file_names:
                if self._path_is_valid(input_path, output_path, filename):
                    yield input_path, output_path, filename
