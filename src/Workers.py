import os

import config
from src.Logger import LOGGER
from src.io import save
from src.io import exif_util
from src.io.file_access_guard import wait_until_path_is_found


class BaseWorker:
    """
    Base class for asynchronous workers. Should be subclassed, and not used as-is.

    :param pool: multiprocessing.Pool to apply async workers in. Can be None if `config.enable_async = False`.
    :type pool: multiprocessing.Pool | None
    :param paths: Paths object representing the image file.
    :type paths: src.io.TreeWalker.Paths
    """
    def __init__(self, pool, paths):
        self.pool = pool
        self.paths = paths

        self.worker_exceptions = (AssertionError,)
        self.error_message = "Got error while processing image '{image_path}':\n{err}"
        self.finished_message = "Worker finished. File: 'image_path'"
        self.async_worker = None

        self.args = tuple()

    @staticmethod
    def async_func(*args):
        """
        Function to apply asynchronously. Implement this in subclasses.

        :param args: Function arguments
        :type args: list
        """
        raise NotImplementedError

    def result_is_valid(self, result):
        """
        Check that `result` is a valid result from `self.async_func`. Implement this in subclasses. Should return a
        boolean.

        :param result: Result from `async_func`.
        :type result:
        """
        raise NotImplementedError

    def start(self):
        """
        Start the async worker. If `config.enable_async = False`, `self.async_func` will be called directly.
        """
        if config.enable_async:
            # Spawn an asynchronous worker
            self.async_worker = self.pool.apply_async(self.async_func, args=self.args)
        else:
            # Try to call the function directly. If it raises an exception, handle the exception.
            try:
                self.async_worker = self.async_func(*self.args)
                assert self.result_is_valid(self.async_worker), f"Invalid result: '{self.async_worker}'"
            except self.worker_exceptions as err:
                self.handle_error(err)

    def get(self):
        """
        Get the result from the worker.

        :return: Return value from `self.async_func`.
        :rtype:
        """
        if config.enable_async:
            # Try to get the result from the asynchronous worker. If it raises an exception, handle the exception.
            try:
                result = self.async_worker.get()
                assert self.result_is_valid(result), f"Invalid result: '{result}'"

            except self.worker_exceptions as err:
                self.handle_error(err)
                return None
        else:
            # The execution was not run asynchronously, which means that the result is stored in `self.async_worker`.
            result = self.async_worker

        LOGGER.debug(__name__, self.finished_message.format(image_file=self.paths.input_file))
        return result

    def handle_error(self, err):
        """
        Handle an exception raised by an async worker.

        :param err: Exception raised by the worker
        :type err: BaseException
        """
        # Get the current state of the logger
        current_logger_state = LOGGER.get_state()

        # Set the state of the logger to reflect the failed image.
        LOGGER.set_state(self.paths)
        # Log the error
        LOGGER.error(__name__, self.error_message.format(image_path=self.paths.input_file, err=str(err)),
                     save=True, email=True, email_mode="error")
        # Reset the state
        LOGGER.set_state(current_logger_state)


class SaveWorker(BaseWorker):
    """
    Worker which saves the masked image, and archives it if archiving is enabled.

    :param pool: multiprocessing.Pool to apply async workers in. Can be None if `config.enable_async = False`.
    :type pool: multiprocessing.Pool | None
    :param paths: Paths object representing the image file.
    :type paths: src.io.TreeWalker.Paths
    :param img: Image to mask
    :type img: np.ndarray
    :param mask_results: Results from `src.Masker.Masker.mask`
    :type mask_results: dict
    """
    def __init__(self, pool, paths, img, mask_results):
        super().__init__(pool, paths)

        self.error_message = "Got error while saving masked image '{image_path}': {err}"
        self.finished_message = "Saved masked image and mask. File: {image_file}"
        self.worker_exceptions = (
            AssertionError,
            FileNotFoundError,
            PermissionError,
            OSError,
        )

        # Arguments to async. function
        save_args = dict(draw_mask=config.draw_mask, local_mask=config.local_mask, remote_mask=config.remote_mask,
                         mask_color=config.mask_color, blur=config.blur, gray_blur=config.gray_blur,
                         normalized_gray_blur=config.normalized_gray_blur)
        archive_args = dict(archive_json=config.archive_json, archive_mask=config.archive_mask, assert_output_mask=True)
        self.args = (img, mask_results, self.paths, save_args, archive_args)

        self.start()

    def result_is_valid(self, result):
        return result == 0

    @staticmethod
    def async_func(img, mask_results, paths, save_args, archive_args):
        """
        Save the result files and do archiving.

        :param img: Input image
        :type img: np.ndarray
        :param mask_results: Results from `src.Masker.Masker.mask`. applied to `image`.
        :type mask_results: dict
        :param paths: Paths object representing the image file.
        :type paths: src.io.TreeWalker.Paths
        :param save_args: Additional keyword-arguments to `src.io.save.save_processed_img`
        :type save_args: dict
        :param archive_args: Additional keyword-arguments to `src.io.save.archive`
        :type archive_args: dict

        :return: 0
        :rtype: int
        """
        # Wait if we can't find the input image or the output path. Here we wait for the base output directory, since
        # `output_path` might be a folder which does not yet exist.
        wait_until_path_is_found([paths.input_file, paths.base_output_dir])
        # Save
        save.save_processed_img(img, mask_results, paths, **save_args)

        if paths.archive_dir is not None:
            # Wait if we can't find the input image, the output path or the archive path
            wait_until_path_is_found([paths.input_file, paths.output_dir, paths.base_archive_dir])
            # Archive
            save.archive(paths, **archive_args)

        return 0


class EXIFWorker(BaseWorker):
    """
   Worker which reads the EXIF data from the input image using `src.io.exif_util`. The EXIF dict will then be written
   to the specified location(s).

   :param pool: multiprocessing.Pool to apply async workers in. Can be None if `config.enable_async = False`.
   :type pool: multiprocessing.Pool | None
   :param paths: Paths object representing the image file.
   :type paths: src.io.TreeWalker.Paths
   :param mask_results: Results from `src.Masker.Masker.mask`
   :type mask_results: dict
   """
    def __init__(self, pool, paths, mask_results):
        super().__init__(pool, paths)

        self.error_message = "Got error while processing EXIF data for image '{image_path}': {err}"
        self.finished_message = "Saved EXIF to JSON. File: {image_file}"
        self.worker_exceptions = (
            AssertionError,
            FileNotFoundError,
            PermissionError,
            OSError,
        )
        self.args = (self.paths, mask_results, config.local_json, config.remote_json)
        self.start()

    def result_is_valid(self, result):
        return isinstance(result, dict)

    @staticmethod
    def async_func(paths, mask_results, local_json, remote_json):
        """
        Run the EXIF processing: Read the EXIF data, add the required fields, and save it. File exports are controlled
        in `config`.

        :param paths: Paths object representing the image file.
        :type paths: src.io.TreeWalker.Paths
        :param mask_results: Results from `src.Masker.Masker.mask`
        :type mask_results: dict
        :param local_json: Write JSON file to the input (local) directory?
        :type local_json: bool
        :param remote_json: Write JSON file to the output (remote) directory?
        :type remote_json: bool
        :return: EXIF dict written to the specified locations
        :rtype: dict
        """
        wait_until_path_is_found([paths.input_file])
        # Get the EXIF data
        exif = exif_util.exif_from_file(paths.input_file)
        # Insert detected objects
        exif["detekterte_objekter"] = exif_util.get_detected_objects_dict(mask_results)
        # Insert path to output image
        # exif["anonymisert_bildefil"] = paths.output_file.replace(os.sep, "/")

        if local_json:
            # Write EXIF to input directory
            exif_util.write_exif(exif, paths.input_json)
        if remote_json:
            # Write EXIF to output directory
            wait_until_path_is_found([paths.base_output_dir])
            os.makedirs(paths.output_dir, exist_ok=True)
            exif_util.write_exif(exif, paths.output_json)

        return exif
