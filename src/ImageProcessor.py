import os
import time
import multiprocessing
import numpy as np
import config
from src.Logger import LOGGER
from src.Workers import SaveWorker, EXIFWorker, EXIFWorkerOld, ERROR_RETVAL
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

    def __init__(self, masker, max_num_async_workers=2, old_exif_version=False):
        self.masker = masker
        self.n_completed = 0
        self.max_worker_starts = 2
        self.workers = []
        self.old_exif_version = old_exif_version

        if self.old_exif_version:
            LOGGER.info(__name__, f"ImageProcessor running with the *old* version of the ExifWorker.")
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

    def normalize_coordinates(row_i, col_j, img):
        """
        Normalizes a coordinate inside an image
        from https://stackoverflow.com/questions/48524516/normalize-coordinates-of-an-image

        :param row_i: The row-pixel (height pixel) in the image.
        :param col_j: The column-pixel (width pixel) in the image.
        :param img: Input image. Must be a 4D color image tensor with shape (1, height, width, 3)
        :rtype: float, float
        """

        num_rows, num_cols = img.shape[1:3]
        x = col_j / (num_cols - 1.)
        y = row_i / (num_rows - 1.)
        return x, y

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
        # If the ImageProcessor is working with older images,
        # it may run an older version of the ExifWorker.
        worker = {
            "paths": paths,
            "SaveWorker": SaveWorker(self.pool, paths, image, mask_results),
            "EXIFWorker": EXIFWorker(self.pool, paths, mask_results) if not self.old_exif_version else EXIFWorkerOld(
                self.pool, paths, mask_results)
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

    def process_image_with_cutouts(self, image, paths):
        """
        Masks the image with a sliding window method.
        It first masks the whole image,
        then a sliding window of a defined scale will slide through the image
        by a defined number of steps, and the masking will be applied on each "window".
        lastly, workers will be spawned to save and process the metadata.

        :param image: Input image. Must be a 4D color image tensor with shape (1, height, width, 3)
        :type image: tf.python.framework.ops.EagerTensor
        :param paths: Paths object representing the image file.
        :type paths: src.io.TreeWalker.Paths

        
        """
        # Get the dimensions of the cutout for a sliding window.
        # The dimensions are defined in the config file.
        window_height_scale, window_width_scale = config.cutout_dim_downscale
        img_h, img_w = image.shape[1:3]
        window_height = int(img_h / window_height_scale)
        window_width = int(img_w / window_width_scale)
        LOGGER.debug(__name__, f"Window h: {window_height}, Window w: {window_width}")

        # SCreate an empty mask for the whole image.
        full_image_mask = np.zeros((img_h, img_w), dtype=bool)
        # The mask results for the whole image.
        all_mask_results = {
            "num_detections": 0,
            "detection_masks": np.asarray([[full_image_mask]]),
            "detection_classes": {},
            "detection_scores": {},
            "detection_boxes": np.asarray([[]])
        }
        i = 0
        first_mask = True
        # Count of the masks that are detected from the sliding window.
        additional_masks = 0
        full_img_time = time.time()
        # Mask the full image
        full_img_mask_result = self.masker.mask(image)

        # Update the full image results with the results from the masking.
        all_mask_results["num_detections"] = full_img_mask_result["num_detections"]
        all_mask_results["detection_masks"] = full_img_mask_result["detection_masks"]

        # Loop through all the masks from the full image masking and update the results wiht the correct format.
        for mask_num, mask in enumerate(full_img_mask_result["detection_masks"][0]):
            detection_box = full_img_mask_result["detection_boxes"][0][mask_num]
            if first_mask:
                first_mask = False
                all_mask_results["detection_boxes"] = np.asarray([detection_box])
            else:
                _add_new_detection_boxes(all_mask_results, [detection_box])
            _add_new_detection_classes(all_mask_results, full_img_mask_result, mask_num)
            _add_new_detection_scores(all_mask_results, full_img_mask_result, mask_num)

        sliding_window_time = time.time()
        # Slide a window/cutout of the full image through the full image. 
        # Mask every cutout and update the results
        for height in range(0, img_h - window_height + 1, config.cutout_step_factor[0]):
            for width in range(0, img_w - window_width + 1, config.cutout_step_factor[1]):

                cutout_image = image[
                               :,
                               height:height + window_height,
                               width:width + window_width,
                               :
                               ]

                # Mask the cutout
                masked_result = self.masker.mask(cutout_image)

                # Loop through each mask detected by the masking.
                # MEither update an existing mask or add a new mask to the results
                for mask_num, mask in enumerate(masked_result["detection_masks"][0]):
                    new_mask = True
                    # Map the bounding box coordinates in the cutout to the corresponding coordinates in the full image.
                    X_min, Y_min = _coordinate_mapping(masked_result["detection_boxes"][0][mask_num][0],
                                                       masked_result["detection_boxes"][0][mask_num][1], image,
                                                       cutout_image, width, height)
                    X_max, Y_max = _coordinate_mapping(masked_result["detection_boxes"][0][mask_num][2],
                                                       masked_result["detection_boxes"][0][mask_num][3], image,
                                                       cutout_image, width, height)
                    mask_bbox_in_full_img = np.asarray([Y_min, X_min, Y_max, X_max])

                    # If the mask is the first mask found in the full image, 
                    # initialise the results with the masking results of the cutout.
                    # This could happen if the masking of the full image yielded no masks.
                    if first_mask:
                        first_mask = False
                        insert_mask = np.asarray([full_image_mask.copy()])
                        insert_mask[0][
                        height:height + window_height,
                        width:width + window_width,
                        ] = mask

                        all_mask_results["detection_masks"] = np.array([insert_mask])
                        all_mask_results["detection_boxes"] = np.asarray([mask_bbox_in_full_img])
                        _add_new_detection_classes(all_mask_results, masked_result, 0)
                        _add_new_detection_scores(all_mask_results, masked_result, 0)
                        all_mask_results["num_detections"] += 1

                    for e_mask_num, existing_mask in enumerate(all_mask_results["detection_masks"][0]):
                        # Extract the relevant cutout of the existing full image mask for comparison.
                        existing_mask = existing_mask[height:height + window_height, width:width + window_width]

                        # If there are overlapping masked pixels between the exisiting mask and the cutout mask
                        # The mask is not new, and the matching existing mask should be updated.
                        if len(np.where(existing_mask[np.where(mask)] == True)[0]) > 0:
                            mask = np.where(mask, mask, existing_mask)
                            new_mask = False
                            update_mask_id = e_mask_num
                    # If the mask is new, add the new results as new entries for the full image.
                    if new_mask:
                        additional_masks += 1
                        _add_new_detection_mask(all_mask_results, mask,full_image_mask, height, window_height, width, window_width)
                        _add_new_detection_boxes(all_mask_results, [[Y_min, X_min, Y_max, X_max]])
                        _add_new_detection_scores(all_mask_results, masked_result, mask_num)
                        _add_new_detection_classes(all_mask_results, masked_result, mask_num)

                    # If the mask is not new, update the results of the existing mask.
                    else:
                        _update_detection_mask(all_mask_results, mask, update_mask_id, height, window_height, width, window_width)
                        _update_detection_scores(all_mask_results, masked_result, update_mask_id, mask_num)
                        _update_detection_classes(all_mask_results, masked_result, update_mask_id, mask_num)
                        _update_detection_boxes(all_mask_results, mask_bbox_in_full_img, update_mask_id)

                i += 1
        sliding_window_time_delta = "{:.3f}".format(time.time() - sliding_window_time)
        detection_classes = []
        detection_scores = []

        # Convert the image tensor to a numpy array 
        if not isinstance(image, np.ndarray):
            image = image.numpy()

            # Make final calculations and decisions about the results.
        for mask_num in range(all_mask_results["num_detections"]):
            # Extract the majority vote of all the classes
            majority_vote_class = _poll_array(all_mask_results["detection_classes"][mask_num])
            detection_classes.append(majority_vote_class)
            # Calculate the average score for the mask
            average_score = np.mean(all_mask_results["detection_scores"][mask_num])
            detection_scores.append(average_score)

        # Format all the results correctly
        all_mask_results["detection_classes"] = np.asarray([detection_classes])
        all_mask_results["detection_scores"] = np.asarray([[detection_scores]])
        all_mask_results["detection_boxes"] = np.asarray([all_mask_results["detection_boxes"]])
        LOGGER.debug(__name__, f"Final results: {all_mask_results}")

        # If we have reached the maximum number of workers. Wait for them to finish
        if len(self.workers) >= self.max_num_async_workers:
            self._wait_for_workers()
        # Create workers for the current image.
        self._spawn_workers(paths, image, all_mask_results)

        time_delta = "{:.3f}".format(time.time() - full_img_time)
        LOGGER.info(__name__, f"Full image time: {time_delta} s.")
        LOGGER.info(__name__, f"Time spent on 'sliding window {sliding_window_time_delta} s.")
        LOGGER.info(__name__, f"Masks added from the 'sliding window': {additional_masks}")

    def process_image_without_cutouts(self, image, paths):
        """
        Run the processing pipeline for `image` without any sliding window method.

        :param image: Input image. Must be a 4D color image tensor with shape (1, height, width, 3)
        :type image: tf.python.framework.ops.EagerTensor
        :param paths: Paths object representing the image file.
        :type paths: src.io.TreeWalker.Paths
        """
        start_time = time.time()
        # Compute the detected objects and their masks.
        mask_results = self.masker.mask(image)

        LOGGER.debug(__name__, f"Masked results: {mask_results}")
        time_delta = "{:.3f}".format(time.time() - start_time)
        LOGGER.debug(__name__, f"Masked image in {time_delta} s. File: {paths.input_file}")

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


def _add_new_detection_mask(all_mask_results, mask, full_image_mask, height, window_height, width, window_width):
    updated_full_image_mask = full_image_mask
    full_image_mask[height:height + window_height, width:width + window_width] = mask
    # Add the mask as a new entry in the full image results.
    all_mask_results["detection_masks"] = np.asarray([np.concatenate(
        (all_mask_results['detection_masks'][0], [updated_full_image_mask]), axis=0)])
    all_mask_results["num_detections"] += 1


def _add_new_detection_boxes(all_mask_results, detection_box):
    all_mask_results["detection_boxes"] = np.concatenate(
        (all_mask_results["detection_boxes"], detection_box), axis=0)


def _add_new_detection_classes(all_mask_results, masked_result, mask_num):
    all_mask_results["detection_classes"].update({
        len(all_mask_results['detection_classes']): [
            masked_result["detection_classes"][0][mask_num]]
    })


def _add_new_detection_scores(all_mask_results, masked_result, mask_num):
    # Add new scores and classes as items in their respective dictionaries.
    all_mask_results["detection_scores"].update({
        len(all_mask_results['detection_scores'].items()): [
            masked_result["detection_scores"][0][mask_num]]
    })


def _update_detection_mask(all_mask_results, mask, update_mask_id, height, window_height, width, window_width):
    # Only update the mask in the current window
    updated_full_image_mask = all_mask_results["detection_masks"][0][update_mask_id]
    updated_full_image_mask[height:height + window_height, width:width + window_width] = mask
    all_mask_results["detection_masks"][0][update_mask_id] = updated_full_image_mask


def _update_detection_boxes(all_mask_results, mask_bbox_in_full_img, update_mask_id):
    full_img_bbox = all_mask_results["detection_boxes"][update_mask_id]
    updated_mask_bbox_min = np.where(full_img_bbox[:2] < mask_bbox_in_full_img[:2],
                                     full_img_bbox[:2], mask_bbox_in_full_img[:2])
    updated_mask_bbox_max = np.where(full_img_bbox[2:] > mask_bbox_in_full_img[2:],
                                     full_img_bbox[2:], mask_bbox_in_full_img[2:])
    updated_mask_bbox = np.append(updated_mask_bbox_min, updated_mask_bbox_max)
    all_mask_results["detection_boxes"][update_mask_id] = updated_mask_bbox


def _update_detection_classes(all_mask_results, masked_result, update_mask_id, mask_num):
    # Add the mask class and score to the list of classes and scores for the mask.
    # The class defined for the mask will be the majority vote of all the classes
    # The final score for the mask will be the average score of all the scores.
    new_classes = np.concatenate(
        (all_mask_results['detection_classes'][update_mask_id],
         [masked_result['detection_classes'][0][mask_num]]),
        axis=None)
    all_mask_results["detection_classes"].update({update_mask_id: new_classes})


def _update_detection_scores(all_mask_results, masked_result, update_mask_id, mask_num):
    new_scores = np.concatenate(
        (all_mask_results['detection_scores'][update_mask_id],
         [masked_result['detection_scores'][0][mask_num]]),
        axis=None)
    all_mask_results["detection_scores"].update({update_mask_id: new_scores})


def _poll_array(poll_item):
    """
    Finds the majority vote in a numpy array.
    """
    values, counts = np.unique(poll_item, return_counts=True)
    index = np.argmax(counts)
    return values[index]


def _coordinate_mapping(y, x, original_img, cutout_img, bounding_w, bounding_h):
    """
    Maps the coordinate y and x in the cutout_img to their correpsondning coordinates
    in the original image.

    :param y: The normalized height coordinate for the pixel.
    :type y: float
    :param x: The normalized width coordinate for the pixel
    :type x: float
    :param original_img: The original image as a 4D-color image tensor with shape (1, height, width, 3).
    :type original_img: tf.python.framework.ops.EagerTensor
    :param cutout_img: The cutout image as a 4D-color image tensor with shape (1, height, width, 3)
    :type cutout_img: tf.python.framework.ops.EagerTensor
    :param bounding_w: The bounding width coordinate for the cutout
    :type bounding_w: int
    :param bounding_h:The bounding height coordinate for the cutout
    :type bounding_h: int
    :rtype: float, float
    """

    X = bounding_w + (x * cutout_img.shape[2])
    Y = bounding_h + (y * cutout_img.shape[1])
    return X / original_img.shape[2], Y / original_img.shape[1]


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
