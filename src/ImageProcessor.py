import os
import multiprocessing
import numpy as np

import config
from src.io import save
from src.Logger import LOGGER
from src.io.file_access_guard import wait_until_path_is_found


WORKER_EXCEPTIONS = (
    AssertionError,
    FileNotFoundError,
    PermissionError,
)


class ImageProcessor:
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
        for worker in self.async_workers:
            try:
                assert worker["result"].get() == 0
            except WORKER_EXCEPTIONS as err:
                self._handle_worker_error(err, input_path=worker["input_path"], mirror_paths=worker["mirror_paths"],
                                          filename=worker["filename"])
        self.async_workers = []

    def _handle_worker_error(self, err, input_path, mirror_paths, filename):
        self.got_worker_error = True
        LOGGER.set_state(input_path=input_path, output_path=mirror_paths[0], filename=filename)
        LOGGER.error(__name__, f"Got error while saving image {input_path}\\{filename}:\n{str(err)}", save=True)

    def process_image(self, image, input_path, mirror_paths, filename):
        mask_results = self.masker.mask(image, mask_dilation_pixels=config.mask_dilation_pixels)

        if not isinstance(image, np.ndarray):
            image = image.numpy()

        # Wait for previous workers if we have reached the maximum number of workers
        if len(self.async_workers) >= self.max_num_async_workers:
            self._wait_for_workers()
        # Add a worker for the current image
        self._create_worker(image, mask_results, input_path, mirror_paths, filename)

    def close(self):
        self._wait_for_workers()
        self.pool.close()


def save_and_archive(img, mask_results, input_path, mirror_paths, filename, base_output_path, base_archive_path):
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
