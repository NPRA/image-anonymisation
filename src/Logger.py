import os
import sys
import logging
import traceback
from shutil import copy2

import config


class Logger:
    def __init__(self):
        self.base_input_dir = None
        self.base_output_dir = None
        self.input_path = None
        self.output_path = None
        self.filename = None
        self.namespace = "image-anonymisation"
        self.logger = logging.getLogger(self.namespace)
        self.fmt = "%(asctime)s (%(levelname)s): %(message)s"
        self.datefmt = config.datetime_format

    def set_log_file(self, log_file_path, level=logging.INFO):
        file_handler = logging.FileHandler(log_file_path)
        file_handler.setLevel(level)
        file_handler.setFormatter(logging.Formatter(self.fmt, datefmt=self.datefmt))
        self.logger.addHandler(file_handler)

    def set_state(self, input_path, output_path, filename):
        self.input_path = input_path
        self.output_path = output_path
        self.filename = filename

    def get_state(self):
        return dict(input_path=self.input_path, output_path=self.output_path, filename=self.filename)

    def _get_error_output_path(self):
        error_extension = "_error"
        abs_error_path = self.base_output_dir + error_extension

        if self.output_path != self.base_output_dir:
            rel_path = self.output_path.replace(self.base_output_dir + os.sep, "", 1)
            rel_error_path = os.path.join(*[d + error_extension for d in rel_path.split(os.sep)])
            abs_error_path = os.path.join(abs_error_path, rel_error_path)
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
        logger = self.logger
        logger.log(level, msg, *args, **kwargs)
        if save:
            # Try to create the error directory. Abort saving if it fails.
            output_path = self._get_error_output_path()
            try:
                os.makedirs(output_path, exist_ok=True)
            except FileNotFoundError as err:
                logger.log(logging.ERROR, f"Got error '{str(err)}' while trying to save error image.")
                return
            
            image_path = os.path.join(self.input_path, self.filename)
            # Can we reach the input image?
            if not os.path.exists(image_path):
                logger.log(logging.ERROR, f"Could not copy image to error directory: Input image '{image_path}' not "
                                          f"found.")
            else:
                # Save image
                logger.log(logging.INFO, f"Copying image file to {output_path} for manual inspection.")
                self._save_error(output_path, msg)

    def info(self, namespace, *args, **kwargs):
        self._log(logging.INFO, namespace, *args, **kwargs)

    def warning(self, namespace, *args, **kwargs):
        self._log(logging.WARNING, namespace, *args, **kwargs)

    def error(self, namespace, *args, **kwargs):
        self._log(logging.ERROR, namespace, *args, **kwargs)


LOGGER = Logger()


def config_string():
    """
    Write the config variables to a string suitable for logging.

    :return: Config string
    :rtype: str
    """
    start_line = 5
    stop_string = "# Configuration constants below."
    stop_offset = -3

    config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), "config.py")
    with open(config_path, "r") as config_file:
        lines = config_file.readlines()

    stop_idx = start_line
    while stop_string not in lines[stop_idx]:
        stop_idx += 1

    lines = lines[start_line: (stop_idx + stop_offset)]
    config_str = "".join(lines)
    config_str = 40 * "#" + " CONFIG START " + 40 * "#" + "\n" + config_str + "\n" + \
        40 * "#" + " CONFIG END " + 40 * "#"
    return config_str


def email_excepthook(etype, ex, tb):
    send_email(etype, ex, tb)
    sys.__excepthook__(etype, ex, tb)


def send_email(etype, ex, tb):
    # TODO: Actually send an email.
    print(40 * "#" + " Message starts " + 40 * "#")
    tb_string = "".join(traceback.format_exception(etype, ex, tb))
    print(tb_string)
    print(40 * "#" + " Message ends " + 40 * "#")

