import multiprocessing
import numpy as np

import config
from src.Workers import SaveWorker, EXIFWorker


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

        self.workers = []

        if config.enable_async:
            self.max_num_async_workers = max_num_async_workers
            self.pool = multiprocessing.Pool(processes=max_num_async_workers)
        else:
            self.pool = None
            self.max_num_async_workers = 1

        if config.write_exif_to_db:
            from src.db.DatabaseClient import DatabaseClient
            self.database_client = DatabaseClient(config.db_max_n_accumulated_rows)
        else:
            self.database_client = None

    def _spawn_workers(self, paths, image, mask_results):
        """
        Create workers for saving/archiving and EXIF export. The workers will work asynchronously if
        `config.enable_async = True`.

        :param paths: Paths object representing the image file.
        :type paths: src.io.TreeWalker.Paths
        :param image:
        :type image:
        :param mask_results:
        :type mask_results:
        """
        self.workers.append(SaveWorker(self.pool, paths, image, mask_results))
        self.workers.append(EXIFWorker(self.pool, paths, mask_results))

    def _wait_for_workers(self):
        while self.workers:
            worker = self.workers.pop(0)
            result = worker.get()

            if isinstance(worker, EXIFWorker) and self.database_client is not None:
                # If `worker` is an `EXIFWorker`, then `result` is the EXIF dict for the
                # worker's image. If we also have an active database_client, add the EXIF data
                # to the database client.
                self.database_client.add_row(result)

    def process_image(self, image, paths):
        """
        Run the processing pipeline for `image`.

        :param image: Input image. Must be a 4D color image tensor with shape (1, height, width, 3)
        :type image: tf.python.framework.ops.EagerTensor
        :param paths: Paths object representing the image file.
        :type paths: src.io.TreeWalker.Paths
        """
        # Compute the detected objects and their masks.
        mask_results = self.masker.mask(image)

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
