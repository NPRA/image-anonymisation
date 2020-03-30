import os
import multiprocessing
import numpy as np

import config
from src.io import save
from src.Logger import LOGGER
from src.io.file_access_guard import wait_until_path_is_found

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
    :param base_input_path: Base input directory.
    :type base_input_path: str
    :param base_output_path: Base output directory.
    :type base_output_path: str
    :param base_archive_path: Base archive directory. Set `base_archive_path = None` when archiving is disabled.
    :type base_archive_path: str | None
    """
    def __init__(self, masker, max_num_async_workers, base_input_path, base_output_path, base_archive_path=None):
        self.masker = masker

        self.base_input_path = base_input_path
        self.base_output_path = base_output_path
        self.base_archive_path = base_archive_path

        self.async_workers = []
        self.pool = multiprocessing.Pool(processes=max_num_async_workers)
        self.max_num_async_workers = max_num_async_workers
        self.got_worker_error = False

    def _create_worker(self, image, mask_results, input_path, mirror_paths, filename):
        """
        Create an async. worker, which handles result-saving for the given image.

        :param image: Input image
        :type image: np.ndarray
        :param mask_results: Results from `src.Masker.Masker.mask`. applied to `image`.
        :type mask_results: dict
        :param input_path: Path to directory containing the input image
        :type input_path: str
        :param mirror_paths: List containing the path to the output directory, and optionally the path to the archive
                             directory.
        :type mirror_paths: list of str
        :param filename: File name of input image
        :type filename: str
        """
        worker = {
            "input_path": input_path,
            "mirror_paths": mirror_paths,
            "filename": filename,
            "result": self.pool.apply_async(save_and_archive,
                                            args=(image, mask_results, input_path, mirror_paths, filename,
                                                  self.base_output_path, self.base_archive_path))
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
                self._handle_worker_error(err, input_path=worker["input_path"], mirror_paths=worker["mirror_paths"],
                                          filename=worker["filename"])
        self.async_workers = []

    def _handle_worker_error(self, err, input_path, mirror_paths, filename):
        """
        Handle an exception raised by an async. worker. This method logs the received error, and copies the image file
        to the error directory. The latter will only be done if the image file is reachable.

        :param err: Exception raised by worker
        :type err: BaseException
        :param input_path: Path to directory containing the input image
        :type input_path: str
        :param mirror_paths: List containing the path to the output directory, and optionally the path to the archive
                             directory.
        :type mirror_paths: list of str
        :param filename: File name of input image
        :type filename: str
        """
        self.got_worker_error = True
        # Get the current state of the logger
        current_logger_state = LOGGER.get_state()
        # Log the error
        LOGGER.set_state(input_path=input_path, output_path=mirror_paths[0], filename=filename)
        LOGGER.error(__name__, f"Got error while saving image {input_path}\\{filename}:\n{str(err)}", save=True)
        # Reset the state
        LOGGER.set_state(**current_logger_state)
        
    def process_image(self, image, input_path, mirror_paths, filename):
        """
        Run the processing pipeline for `image`.

        :param image: Input image. Must be a 4D color image tensor with shape (1, height, width, 3)
        :type image: tf.python.framework.ops.EagerTensor
        :param input_path: Path to directory containing the input image
        :type input_path: str
        :param mirror_paths: List containing the path to the output directory, and optionally the path to the archive
                             directory.
        :type mirror_paths: list of str
        :param filename: File name of input image
        :type filename: str
        """
        mask_results = self.masker.mask(image, mask_dilation_pixels=config.mask_dilation_pixels)

        if not isinstance(image, np.ndarray):
            image = image.numpy()

        # Wait for previous workers if we have reached the maximum number of workers
        if len(self.async_workers) >= self.max_num_async_workers:
            self._wait_for_workers()
        # Add a worker for the current image
        self._create_worker(image, mask_results, input_path, mirror_paths, filename)

    def close(self):
        """
        Close the image processing instance. Waits for all dispatched workers to finish, and then closes the
        multiprocessing pool.
        """
        self._wait_for_workers()
        self.pool.close()


def save_and_archive(img, mask_results, input_path, mirror_paths, filename, base_output_path, base_archive_path):
    """
    Save the result files and do archiving.

    :param img: Input image
    :type img: np.ndarray
    :param mask_results: Results from `src.Masker.Masker.mask`. applied to `image`.
    :type mask_results: dict
    :param input_path: Path to directory containing the input image
    :type input_path: str
    :param mirror_paths: List containing the path to the output directory, and optionally the path to the archive
                         directory.
    :type mirror_paths: list of str
    :param filename: File name of input image
    :type filename: str
    :param base_output_path: Base output directory.
    :type base_output_path: str
    :param base_archive_path: Base archive directory. Set `base_archive_path = None` when archiving is disabled.
    :type base_archive_path: str | None
    :return: 0
    :rtype: int
    """
    # Wait if we can't find the input image or the output path. Here we wait for the base output directory, since
    # `output_path` might be a folder which does not yet exist.
    image_path = os.path.join(input_path, filename)
    wait_until_path_is_found([image_path, base_output_path])
    # Save
    save.save_processed_img(img, mask_results, input_path=input_path, output_path=mirror_paths[0],
                            filename=filename, draw_mask=config.draw_mask, local_json=config.local_json,
                            remote_json=config.remote_json, local_mask=config.local_mask,
                            remote_mask=config.remote_mask, mask_color=config.mask_color, blur=config.blur,
                            gray_blur=config.gray_blur, normalized_gray_blur=config.normalized_gray_blur)

    if len(mirror_paths) > 1:
        # Wait if we can't find the input image, the output path or the archive path
        wait_until_path_is_found([image_path, base_output_path, base_archive_path])
        # Archive
        save.archive(input_path, mirror_paths, filename, archive_json=config.archive_json,
                     archive_mask=config.archive_mask, delete_input_img=config.delete_input, assert_output_mask=True)

    return 0
