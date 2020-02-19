import os
import logging
from shutil import copy2


class Logger:
    def __init__(self):
        self.base_input_dir = None
        self.base_output_dir = None
        self.input_path = None
        self.output_path = None
        self.filename = None

    def set_state(self, input_path, output_path, filename):
        self.input_path = input_path
        self.output_path = output_path
        self.filename = filename

    def _get_error_output_path(self):
        error_extension = "_error"
        abs_error_path = self.base_output_dir + error_extension

        if self.output_path != self.base_output_dir:
            rel_path = self.output_path.replace(self.base_output_dir + os.sep, "", 1)
            rel_error_path = os.path.join(*[d + error_extension for d in rel_path.split(os.sep)])
            abs_error_path = os.path.join(abs_error_path, rel_error_path)
        os.makedirs(abs_error_path, exist_ok=True)
        return abs_error_path

    def _save_error_img(self, output_path):
        copy2(os.path.join(self.input_path, self.filename), os.path.join(output_path, self.filename))

    def _save_error_msg(self, output_path, msg):
        msg_filename = os.path.join(output_path, self.filename[:-4] + "_error.txt")
        with open(msg_filename, "w") as error_file:
            error_file.write(msg)

    def _save_error(self, output_path, message):
        self._save_error_img(output_path)
        self._save_error_msg(output_path, message)

    def _log(self, level, namespace, msg, *args, save=False, **kwargs):
        logger = logging.getLogger(namespace)
        logger.log(level, msg, *args, **kwargs)
        if save:
            output_path = self._get_error_output_path()
            logger.log(level, f"Copying image file to {output_path} for manual inspection.")
            self._save_error(output_path, msg)

    def info(self, namespace, *args, **kwargs):
        self._log(logging.INFO, namespace, *args, **kwargs)

    def warning(self, namespace, *args, **kwargs):
        self._log(logging.WARNING, namespace, *args, **kwargs)

    def error(self, namespace, *args, **kwargs):
        self._log(logging.ERROR, namespace, *args, **kwargs)


LOGGER = Logger()
