import os
import time
import multiprocessing
import numpy as np
import cv2

import config
from src.Logger import LOGGER
from src.Workers import SaveWorker, EXIFWorker, ERROR_RETVAL
from src.io.file_checker import check_all_files_written
from src.io.file_access_guard import wait_until_path_is_found


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

    def __init__(self, masker, max_num_async_workers=2):
        self.masker = masker
        self.n_completed = 0
        self.max_worker_starts = 2
        self.workers = []

        if config.enable_async:
            self.max_num_async_workers = max_num_async_workers
            self.pool = multiprocessing.Pool(processes=max_num_async_workers)
        else:
            self.pool = None
            self.max_num_async_workers = 1

        if config.write_exif_to_db:
            from src.db.DatabaseClient import DatabaseClient
            self.database_client = DatabaseClient(max_n_accumulated_rows=config.db_max_n_accumulated_rows,
                                                  max_n_errors=config.db_max_n_errors,
                                                  max_cache_size=config.db_max_cache_size)
        else:
            self.database_client = None

    def _spawn_workers(self, paths, image, mask_results):
        """
        Create workers for saving/archiving and EXIF export. The workers will work asynchronously if
        `config.enable_async = True`.

        :param paths: Paths object representing the image file.
        :type paths: src.io.TreeWalker.Paths
        :param image: Input image
        :type image: np.ndarray
        :param mask_results: Results from `src.Masker.Masker.mask`
        :type mask_results: dict
        """
        # Write the cache file indicating that the saving process has begun.
        paths.create_cache_file()
        # Create workers
        worker = {
            "paths": paths,
            "SaveWorker": SaveWorker(self.pool, paths, image, mask_results),
            "EXIFWorker": EXIFWorker(self.pool, paths, mask_results)
        }
        self.workers.append(worker)

    def _wait_for_workers(self):
        """
        Wait for all dispatched workers to finish. If any of the workers raise an exception, it will be handled, and the
        worker will be restarted (unless it has been started `self.max_worker_starts` times already). When a worker is
        finished, the output files and archive files will be checked, the cache file will be removed, and if
        `config.delete_input`, the input image will be removed.
        """
        failed_workers = []
        while self.workers:
            worker = self.workers.pop(0)

            paths = worker["paths"]
            exif_result = worker["EXIFWorker"].get()
            save_result = worker["SaveWorker"].get()

            workers_restarted = False
            if exif_result == ERROR_RETVAL:
                workers_restarted = self._maybe_restart_worker(paths, worker["EXIFWorker"])
            if save_result == ERROR_RETVAL:
                workers_restarted = self._maybe_restart_worker(paths, worker["SaveWorker"])

            if workers_restarted:
                failed_workers.append(worker)
            # Check that all expected output files exist, and log an error if any files are missing.
            elif check_all_files_written(paths):
                self._finish_image(paths, exif_result)

        self.workers += failed_workers

    def _maybe_restart_worker(self, paths, worker):
        """
        Restart the worker if it has been started less than `self.max_worker_starts` times previously. Otherwise, log an
        error, and save the error image.

        :param paths: Paths object representing the image file.
        :type paths: src.io.TreeWalker.Paths
        :param worker: Worker to maybe restart
        :type worker: src.Workers.BaseWorker
        :return: True if worker was restarted, False otherwise
        :rtype: bool
        """
        if worker.n_starts > self.max_worker_starts:
            LOGGER.error(__name__, f"{worker.__class__.__name__} failed for image: {paths.input_file}.", save=True,
                         email=True, email_mode="error")
            return False
        else:
            worker.start()
            LOGGER.debug(__name__, f"Restarted {worker.__class__.__name__} for image: {paths.input_file}.")
            return True

    def _finish_image(self, paths, exif_result):
        """
        Finish processing for an image. This function will:

        - (optionally) Write the EXIF data to the database. (If `config.write_exif_to_db == True`.)
        - Remove the cache file for the image
        - (optionally) Remove the input image. (If `config.delete_input == True`.)

        :param paths: Paths object representing the image file.
        :type paths: src.io.TreeWalker.Paths
        :param exif_result: JSON metadata file contents. Will be used to write to the database if database writing is
                            enabled.
        :type exif_result: dict
        """
        # If we have an active database_client, add the EXIF data to the database client.
        if self.database_client is not None and exif_result is not None:
            self.database_client.add_row(exif_result)

        # Remove the cache file
        paths.remove_cache_file()

        # Delete the input file?
        if config.delete_input:
            wait_until_path_is_found(paths.input_file)
            os.remove(paths.input_file)
            LOGGER.debug(__name__, f"Input file removed: {paths.input_file}")

            # Remove the input folder if it is empty and it's not the base input folder.
            remove_empty_folders(start_dir=paths.input_dir, top_dir=paths.base_input_dir)

        self.n_completed += 1
    def make_cutouts(self, image, paths):
        """
        Creates cutouts of the image, and caches them to a folder if specified in the config file.
        
        """
        out_dir = paths.cache_cutout_dir
        cropped_images = []
        window_height_scale, window_width_scale = config.cutout_dim_downscale
        img_h, img_w = image.shape[1:3]
        #print(img_h, img_w)
        
        # Get the dimensions of the sliding window
        window_height = int(img_h/window_height_scale)
        window_width = int(img_w/window_width_scale)
        
        # Slide the window over the original image and crop out the window.
        
        for height in range(0, img_h - window_height + 1, config.cutout_step_factor):
            for width in range(0, img_w - window_width +1, config.cutout_step_factor):
                
                cutout_image = image[
                    :,
                    height:height+window_height,
                    width:width+window_width,
                    : 
                ]
                #print(f"[height x width][{height}:{height+window_height} x W{width}:{width+window_width}], cutout shape: {cutout_image.shape}")
                
                cropped_img_numpy = cutout_image.numpy()
                cropped_img_numpy = cropped_img_numpy[0].astype(np.uint8)
                #print(cropped_img_numpy)
                #print(cropped_img_numpy.shape)
                # save cropped image
                # if config.cache_cutouts:
                    # cv2.imwrite(os.path.join(out_dir, f"{paths.filename}_h{height}_w{width}.jpg"), cropped_img_numpy)
                cropped_images.append(cutout_image)
                LOGGER.info(__name__, f"Cutout: H{height}:{height+window_height} x W{width}:{width+window_width}")
                
        
        return cropped_images
    def process_image(self, image, paths, cropped=False):
        """
        Run the processing pipeline for `image`.

        :param image: Input image. Must be a 4D color image tensor with shape (1, height, width, 3)
        :type image: tf.python.framework.ops.EagerTensor
        :param paths: Paths object representing the image file.
        :type paths: src.io.TreeWalker.Paths
        """
        start_time = time.time()
        # Compute the detected objects and their masks.
        mask_results = self.masker.mask(image)
        LOGGER.info(__name__, f"Masked results: {mask_results}")
        time_delta = "{:.3f}".format(time.time() - start_time)
        LOGGER.info(__name__, f"Masked image in {time_delta} s. File: {paths.input_file}")

        # Convert the image to a numpy array
        if not isinstance(image, np.ndarray):
            image = image.numpy()

        # If we have reached the maximum number of workers. Wait for them to finish
        if len(self.workers) >= self.max_num_async_workers:
            self._wait_for_workers()
        # Create workers for the current image.
        self._spawn_workers(paths, image, mask_results)

    def close(self):
        """
        Close the image processing instance. Waits for all dispatched workers to finish, and then closes the
        multiprocessing pool.
        """
        self._wait_for_workers()
        if self.pool is not None:
            self.pool.close()
        if self.database_client is not None:
            self.database_client.close()


def remove_empty_folders(start_dir, top_dir):
    """
    Bottom-up removal of empty folders. If `start_dir` is empty, it will be removed. If `start_dir`'s parent directory
    is empty after removing `start_dir`, it too will be removed. This process i continued until a parent is non-empty,
    or the current directory is equal to `top_dir`. (The `top_dir` directory will not be removed).

    NOTE: Use full paths when using this function, to avoid problems when comparing the current directory to `top_dir`.

    :param start_dir: Path to bottom directory to remove if empty.
    :type start_dir: str
    :param top_dir: Top directory. Only folders under this will be deleted.
    :type top_dir:
    """
    assert start_dir.startswith(top_dir), f"remove_empty_folders: Invalid top directory '{top_dir}' for start " \
                                          f"directory '{start_dir}'"
    current_dir = start_dir
    while not os.listdir(current_dir) and current_dir != top_dir:
        os.rmdir(current_dir)
        LOGGER.debug(__name__, f"Input folder removed: {current_dir}")
        current_dir = os.path.dirname(current_dir)
