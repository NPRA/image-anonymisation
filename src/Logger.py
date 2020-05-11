import os
import logging
from shutil import copy2

import config


class FileHandler(logging.StreamHandler):
    def __init__(self, file_path):
        super().__init__()
        self.file_path = file_path

    def emit(self, record):
        msg = self.formatter.format(record)
        try:
            with open(self.file_path, "a+") as f:
                f.write(msg + "\n")
        except (FileNotFoundError, OSError):
            print(f"Log file '{self.file_path}' not reachable.")


class Logger:
    def __init__(self):
        self.paths = None
        self.namespace = "image-anonymisation"
        self.logger = logging.getLogger(self.namespace)
        self.fmt = "[%(asctime)s %(levelname)s]: %(message)s"
        self.datefmt = config.datetime_format
        self.log_file_path = None

    def set_log_file(self, log_file_path, level=logging.INFO):
        self.log_file_path = log_file_path
        # file_handler = logging.FileHandler(log_file_path)
        file_handler = FileHandler(log_file_path)
        file_handler.setLevel(level)
        file_handler.setFormatter(logging.Formatter(self.fmt, datefmt=self.datefmt))
        self.logger.addHandler(file_handler)

    def set_state(self, paths):
        self.paths = paths

    def get_state(self):
        return self.paths

    def _save_error_img(self):
        # copy2(os.path.join(self.input_path, self.filename), os.path.join(output_path, self.filename))
        copy2(self.paths.input_file, self.paths.error_output_file)

    def _save_error_msg(self, msg):
        msg_filename = os.path.splitext(self.paths.filename)[0] + "_error.txt"
        msg_file = os.path.join(self.paths.error_output_dir, msg_filename)

        with open(msg_file, "w") as error_file:
            error_file.write(msg)

    def _save_error(self, message):
        self._save_error_img()
        self._save_error_msg(message)

    def _log(self, level, namespace, msg, *args, save=False, email=False, email_mode="error", **kwargs):
        logger = self.logger
        logger.log(level, msg, *args, **kwargs)
        if save:
            try:
                # Try to save image
                os.makedirs(self.paths.error_output_dir, exist_ok=True)
                self._save_error(msg)
            except Exception as err:
                logger.log(logging.ERROR, f"Got error '{str(err)}' while trying to save error image.")
                return
            else:
                logger.log(logging.INFO, f"Copied image file to {self.paths.error_output_dir} for manual inspection.")

        if email and config.processing_error_email:
            from src.email_sender import send_mail
            send_mail(email_mode, msg=msg)

    def debug(self, namespace, *args, **kwargs):
        self._log(logging.DEBUG, namespace, *args, **kwargs)

    def info(self, namespace, *args, **kwargs):
        self._log(logging.INFO, namespace, *args, **kwargs)

    def warning(self, namespace, *args, **kwargs):
        self._log(logging.WARNING, namespace, *args, **kwargs)

    def error(self, namespace, *args, **kwargs):
        self._log(logging.ERROR, namespace, *args, **kwargs)


LOGGER = Logger()
LOG_SEP = 150 * "-"


def config_string():
    """
    Write the config variables to a string suitable for logging.

    :return: Config string
    :rtype: str
    """
    start_line = 5

    config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), "config", "config.py")
    with open(config_path, "r") as config_file:
        lines = config_file.readlines()

    lines = lines[start_line:]
    config_str = "".join(lines)
    config_str = 40 * "#" + " CONFIG START " + 40 * "#" + "\n" + config_str + "\n" + \
        40 * "#" + " CONFIG END " + 40 * "#"
    return config_str




