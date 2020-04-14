import os
import multiprocessing
import numpy as np

import config
from src.io import save
from src.Logger import LOGGER
from src.io.file_access_guard import wait_until_path_is_found
from src.io.exif_util import exif_from_file

#: Exceptions to catch when saving and archiving.
WORKER_EXCEPTIONS = (
    AssertionError,
    FileNotFoundError,
    PermissionError,
    OSError,
)


class ImageProcessor:
    """
    Implements the image processing pipeline. When an image is received, it will be masked, and the resulting output
    files will be written asynchronously.

    :param masker: Masker instance. Used to compute the image masks.
    :type masker: src.Masker.Masker
    :param max_num_async_workers: Maximum number of async workers. When the number of dispatched workers exceeds
                                  `max_num_async_workers`, `ImageProcessor.process_image` will stop and wait for all
                                  dispatched workers to finish.
    :type max_num_async_workers: int
    """
    def __init__(self, masker, max_num_async_workers):
        self.masker = masker

        self.async_workers = []
        self.pool = multiprocessing.Pool(processes=max_num_async_workers)
        self.max_num_async_workers = max_num_async_workers
        self.got_worker_error = False

        if config.write_exif_to_db:
            from src.db.DatabaseClient import DatabaseClient
            self.database_client = DatabaseClient(config.db_max_n_accumulated_rows)
        else:
            self.database_client = None

    def _create_worker(self, image, mask_results, exif, paths):
        """
        Create an async. worker, which handles result-saving for the given image.

        :param image: Input image
        :type image: np.ndarray
        :param mask_results: Results from `src.Masker.Masker.mask`. applied to `image`.
        :type mask_results: dict
        :param exif: EXIF data for `img`.
        :type exif: dict
        """
        # Wait for previous workers if we have reached the maximum number of workers
        if len(self.async_workers) >= self.max_num_async_workers:
            self._wait_for_workers()

        # Create a new worker
        worker = {
            "paths": paths,
            "result": self.pool.apply_async(save_and_archive, args=(image, mask_results, exif, paths))
        }
        self.async_workers.append(worker)

    def _wait_for_workers(self):
        """
        Wait for all dispatched workers to finish. If any of the workers fail, this will be handled by
        `ImageProcessor._handle_worker_error`.
        """
        for worker in self.async_workers:
            try:
                assert worker["result"].get() == 0
            except WORKER_EXCEPTIONS as err:
                self._handle_worker_error(err, worker["paths"])
        self.async_workers = []

    def _handle_worker_error(self, err, paths):
        """
        Handle an exception raised by an async. worker. This method logs the received error, and copies the image file
        to the error directory. The latter will only be done if the image file is reachable.

        :param err: Exception raised by worker
        :type err: BaseException
        """
        self.got_worker_error = True
        # Get the current state of the logger
        current_logger_state = LOGGER.get_state()
        # Log the error
        LOGGER.set_state(paths)
        LOGGER.error(__name__, f"Got error while saving image {paths.input_file}:\n{str(err)}",
                     save=True, email=True, email_mode="error")
        # Reset the state
        LOGGER.set_state(current_logger_state)
        
    def process_image(self, image, paths):
        """
        Run the processing pipeline for `image`.

        :param image: Input image. Must be a 4D color image tensor with shape (1, height, width, 3)
        :type image: tf.python.framework.ops.EagerTensor
        """
        # Compute the detected objects and their masks.
        mask_results = self.masker.mask(image, mask_dilation_pixels=config.mask_dilation_pixels)

        # Get EXIF data
        exif = exif_from_file(paths.input_file)
        # Add the path to the output image to the json dict.
        exif["anonymisert_bildefil"] = paths.output_file.replace(os.sep, "/")

        # Convert the image to a numpy array
        if not isinstance(image, np.ndarray):
            image = image.numpy()

        # Add a worker for the current image
        self._create_worker(image, mask_results, exif, paths)

        # Add the EXIF data to the database if database writing is enabled.
        if self.database_client is not None:
            self.database_client.add_row(exif)

    def close(self):
        """
        Close the image processing instance. Waits for all dispatched workers to finish, and then closes the
        multiprocessing pool.
        """
        self._wait_for_workers()
        self.pool.close()
        if self.database_client is not None:
            self.database_client.close()


def save_and_archive(img, mask_results, exif, paths):
    """
    Save the result files and do archiving.

    :param img: Input image
    :type img: np.ndarray
    :param mask_results: Results from `src.Masker.Masker.mask`. applied to `image`.
    :type mask_results: dict
    :param exif: EXIF data for `img`.
    :type exif: dict
    :return: 0
    :rtype: int
    """
    # Wait if we can't find the input image or the output path. Here we wait for the base output directory, since
    # `output_path` might be a folder which does not yet exist.
    wait_until_path_is_found([paths.input_file, paths.base_output_dir])
    # Save
    save.save_processed_img(img, mask_results, exif, paths, draw_mask=config.draw_mask, local_json=config.local_json,
                            remote_json=config.remote_json, local_mask=config.local_mask,
                            remote_mask=config.remote_mask, mask_color=config.mask_color, blur=config.blur,
                            gray_blur=config.gray_blur, normalized_gray_blur=config.normalized_gray_blur)

    if paths.archive_dir is not None:
        # Wait if we can't find the input image, the output path or the archive path
        wait_until_path_is_found([paths.input_file, paths.base_output_dir, paths.base_archive_dir])
        # Archive
        save.archive(paths, archive_json=config.archive_json, archive_mask=config.archive_mask,
                     delete_input_img=config.delete_input, assert_output_mask=True)

    return 0
