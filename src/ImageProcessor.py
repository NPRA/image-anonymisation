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
    
    def normalize_coordinates(row_i, col_j, img):
        """
        from https://stackoverflow.com/questions/48524516/normalize-coordinates-of-an-image
        row: x
        col: y
        """
        
        num_rows, num_cols = img.shape[1:3]
        x = col_j/(num_cols - 1.)
        y = row_i/(num_rows - 1.)
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
        #print(f"window_idt: {window_width}")
        total_masks = 0
        # Slide the window over the original image and crop out the window.
        full_image_mask = np.zeros((img_h, img_w), dtype=bool)
        i = 0
        all_mask_results = {
            "num_detections": 0,
            "detection_masks": np.asarray([[full_image_mask]]),
            "detection_classes": {},
            "detection_scores": {}
        }
        first_mask = True
        # Mask the full image
        full_img_mask_result = self.masker.mask(image)
        LOGGER.debug(__name__, f"full_mask_result: {full_img_mask_result}")
        #all_mask_results["detection_boxes"] = full_img_mask_result["detection_boxes"]
        all_mask_results["num_detections"] = full_img_mask_result["num_detections"]
        all_mask_results["detection_masks"] = full_img_mask_result["detection_masks"]
        #print(f"full img: {full_img_mask_result}")
        #print(f"c: {all_mask_results['detection_classes']}")
        first_mask = True
        for mask_num, mask in enumerate(full_img_mask_result["detection_masks"][0]):
            detection_box = full_img_mask_result["detection_boxes"][0][mask_num]

            if first_mask: 
                first_mask = False
                all_mask_results["detection_boxes"] = np.asarray([detection_box])
            else:
                all_mask_results["detection_boxes"] = np.concatenate((all_mask_results["detection_boxes"],[detection_box]), axis=0)

            #print(detection_box)
            #print(type(all_mask_results["detection_classes"]))
            all_mask_results["detection_classes"].update( {
                mask_num: [full_img_mask_result["detection_classes"][0][mask_num]]
                })
            all_mask_results["detection_scores"].update( {
                mask_num:full_img_mask_result["detection_scores"][0][mask_num]
            })
        # Apply the information into the all masks.
        additional_masks = 0
        #print(f"At init: {all_mask_results}")
        full_img_time = time.time()
        for height in range(0, img_h - window_height + 1, config.cutout_step_factor):
            for width in range(0, img_w - window_width +1, config.cutout_step_factor):
                cutout_time = time.time()
                
                cutout_image = image[
                    :,
                    height:height+window_height,
                    width:width+window_width,
                    : 
                ]
                #print(f"[height x width][{height}:{height+window_height} x W{width}:{width+window_width}], cutout shape: {cutout_image.shape}")
                
                #if i > 50:
                #print(f"$$$$$$$$$$$$$ [i: {i}] $$$$$$$$$$$$$$$$")
                #start_time = time.time()
                # Mask the cutout
                masked_result = self.masker.mask(cutout_image)
                #time_delta = "{:.3f}".format(time.time() - start_time)
                #LOGGER.info(__name__, f"Masked image in {time_delta} s. File: {paths.input_file}")
                after_mask_time = time.time()
                # detection_masks = masked_result["detection_masks"]

                # detection_classes = masked_result["detection_classes"][0]
                # for i in range(len(detection_classes)):
                #     detected_label = detection_classes[i]
                #     mask = detection_masks[:, i, ...] > 0
                #     cutout_image[mask] = config.LABEL_COLORS.get(detected_label, config.DEFAULT_COLOR)
                #print(f"masked res: {masked_result}")
                #print(f"{width+window_width}")
                #print(f"{np.asarray(full_image_mask[height:height+window_height][width:width+window_width]).shape}")
                # mask_area = full_image_mask[height:height+window_height, width:width+window_width]
                #print(f"i:{i}, Shapes {width}, {height}(w, h): img_mask: {full_image_mask.shape},img: {cutout_image.shape}, masked_result detection masks: {np.asarray(masked_result['detection_masks'][0]).shape}, mask_area shape: {np.asarray(mask_area).shape}")
                # perhaps insert for each mask in mask results...
                for mask_num, mask in enumerate(masked_result["detection_masks"][0]):
                    new_mask = True
                    #print(f"---- mask number {mask_num} h: {height}, w {width} ----")
                    #print(mask.dtype)
                    #print(mask)
                    # Update the mask with new masked pixels
                    #for j in range(len(masked_result["detection_classes"][0])):
                        #m = masked_result["detection_masks"][:, j, ...] > 0
                        #print(f"m: {m}")
                    #mask[-1] = True
                    mask_occurances = np.where(mask)
                    #y_min, x_min, y_max, x_max = mask_occurances[0][0], mask_occurances[1][0], mask_occurances[0][-1], mask_occurances[1][-1]
                    # What are the pixels in the main image (normalized)
                    X_min, Y_min = _coordinate_mapping(masked_result["detection_boxes"][0][mask_num][0], masked_result["detection_boxes"][0][mask_num][1], image, cutout_image, width, height)
                    X_max, Y_max = _coordinate_mapping(masked_result["detection_boxes"][0][mask_num][2], masked_result["detection_boxes"][0][mask_num][3], image, cutout_image, width, height)
                    mask_bbox_in_full_img = np.asarray([Y_min, X_min, Y_max, X_max])
                    
                    # comparY max Y min, min Y max 
                    

                        #print(f"firs!!")
                    for e_mask_num, existing_mask in enumerate(all_mask_results["detection_masks"][0]):
                        #new_masked_area = np.where(mask, mask, existing_mask)
                        # Compar only the relevant cutout of the mask
                        existing_mask = existing_mask[height:height+window_height, width:width+window_width]
                        # Is this a new mask, or a continuation?
                        # If the masked pixels in mask already exist, only update it,
                        # no new mask is added to the all_mask_result
                        #print(f"mask: {np.where(mask)}")
                        #print(f"{existing_mask}, {existing_mask.shape}")
                        #print(f"existing: {existing_mask[np.where(mask)] == True}")
                        #print(f"LEN: {len(np.where(existing_mask[ np.where(mask)] == True)[0])}, ({len(np.where(mask))}), ({np.where(existing_mask)}))")
                        
                        if len(np.where(existing_mask[ np.where(mask)] == True)[0]) > 0:
                            #print(f"UPDATE MASK {e_mask_num}")
                            #print(f"UPDATE MASK {e_mask_num}")
                            #print(f"UPDATE MASK {e_mask_num}")
                            
                            # Update the existing mask with diff. Perhaps remove where..
                            mask = np.where(mask, mask, existing_mask)
                            #all_mask_results[mask_id] = mask
                            new_mask = False
                            update_mask_id = e_mask_num
                    if new_mask: 
                        additional_masks += 1
                        #print(f"NEW MASK!!")
                        # if len(all_mask_results["detection_masks"][0]) == 0:
                        #     #: 0 the list of all
                        #     #: 1 ??? should be 0 always
                        #     #: update_mask_id 
                        #     all_mask_results["detection_masks"] = [[mask]]
                        #     all_mask_results["detection_boxes"] = [[[y_min, x_min, y_max, x_max]]]
                        # else:
                        updated_full_image_mask = full_image_mask
                        full_image_mask[height:height+window_height, width:width+window_width] = mask
                        #print(all_mask_results)
                        #print(f"beofre: {all_mask_results['detection_masks'][0]}")
                        #print(updated_full_image_mask)
                        # print(f"concat: {np.concatenate((all_mask_results['detection_masks'][0], [updated_full_image_mask]), axis=0).shape}")
                        all_mask_results["detection_masks"] = np.asarray([np.concatenate((all_mask_results['detection_masks'][0], [updated_full_image_mask]), axis=0)])
                        #print(f"aftyer {all_mask_results['detection_masks']}")
                        all_mask_results["num_detections"] += 1
                        total_masks += 1
                        #LOGGER.debug(__name__, f"All mask result adding a new mask: {all_mask_results}")
                        #LOGGER.debug(__name__, f"Trying to concat: {[[Y_min, X_min, Y_max, X_max]]} along axis 0")
                        #print(f"all: {all_mask_results}")
                        #print(f"{all_mask_results['detection_boxes']} ({all_mask_results['detection_boxes'].shape}) >< {[[Y_min, X_min, Y_max, X_max]]} ({np.asarray([[Y_min, X_min, Y_max, X_max]]).shape}) = ")
                        #print(f"{np.concatenate((all_mask_results['detection_boxes'],[[Y_min, X_min, Y_max, X_max]]), axis=0)}")
                        #all_mask_results["detection_masks"][0].append(mask, axis=0)
                        all_mask_results["detection_boxes"] = np.concatenate((all_mask_results["detection_boxes"],[[Y_min, X_min, Y_max, X_max]]), axis=0)
                        
                        #np.append(all_mask_results["detection_boxes"],[[[Y_min, X_min, Y_max, X_max]]], axis=0)
                        #print(f"d {[masked_result['detection_scores'][0][mask_num]]}")
                        all_mask_results["detection_scores"].update({
                            len(all_mask_results['detection_scores'].items()): [masked_result["detection_scores"][0][mask_num]]
                        })
                        
                        all_mask_results["detection_classes"].update( {
                            len(all_mask_results['detection_classes']): [masked_result["detection_classes"][0][mask_num]]
                        })
                        #np.concatenate((all_mask_results["detection_classes"], [[masked_result["detection_classes"][0][mask_num]]]), axis=0)
                        #np.append(all_mask_results["detection_scores"],[masked_result["detection_scores"][0][mask_num]], axis=0)
                        #np.append(all_mask_results["detection_classes"], [masked_result["detection_classes"][0][mask_num]], axis=0)
                        #print(all_mask_results)
                    else:
                        #print(f"UPDATE!!")
                        # Only update the mask in the current window
                        updated_full_image_mask = all_mask_results["detection_masks"][0][update_mask_id]
                        updated_full_image_mask[height:height+window_height, width:width+window_width] = mask
                        all_mask_results["detection_masks"][0][update_mask_id] = updated_full_image_mask
                        
                        #Update classes
                        # print(f"all_mask_detection: {all_mask_results['detection_classes']}")
                        # print(f"on mask id: {all_mask_results['detection_classes'][update_mask_id]} ")
                        # print(f"masked_results: {masked_result['detection_classes']} "\
                        #         #f"{[masked_result['detection_classes'][update_mask_id]]}, " \
                        #         f"{masked_result['detection_classes'][0][mask_num]}, " \
                        #         f"{np.concatenate((all_mask_results['detection_classes'][0][update_mask_id],[masked_result['detection_classes'][0][mask_num]]), axis=None)}")
                        new_classes= np.concatenate(
                            (all_mask_results['detection_classes'][update_mask_id],
                                [masked_result['detection_classes'][0][mask_num]]),
                            axis=None) # should be a list of possible classes
                        #print(f"new_scores: {new_classes}, new_score")
                        all_mask_results["detection_classes"].update({update_mask_id: new_classes})
                        #print(f"all detetion classes obj: {all_mask_results['detection_classes']}")
                        
                        new_scores= np.concatenate(
                            (all_mask_results['detection_scores'][update_mask_id],
                                [masked_result['detection_scores'][0][mask_num]]),
                            axis=None) # should be a list of scores
                        all_mask_results["detection_scores"].update({update_mask_id: new_scores})
                        # Add the mask class to the list of detection classes for later polling.
                        #all_mask_results["detection_classes"]=[[masked_result["detection_classes"][0][mask_num]]]
                        # Compare the bounding boxes of the masks
                        #print(f"bbox: {all_mask_results['detection_boxes']}, index: {update_mask_id}, shape: {all_mask_results['detection_boxes'].shape}")
                        full_img_bbox = all_mask_results["detection_boxes"][update_mask_id]
                        #print(f"full_img bbox: {full_img_bbox}, detection: {all_mask_results['detection_boxes']}")
                        #y_min = Y_min if Y_min < full_img_bbox[0] else full_img_bbox[0]
                        #x_min = X_min if X_min < full_img_bbox[1] else full_img_bbox[1]
                        #print(f"mask_bbox: {mask_bbox_in_full_img}")
                        #print(f"BBox: {full_img_bbox[:2]} < {mask_bbox_in_full_img}")
                        #print(f"scores: d: {masked_result['detection_scores'][0][mask_num]}, a: {all_mask_results['detection_scores'][update_mask_id]}")
                        updated_mask_bbox_min = np.where(full_img_bbox[:2] < mask_bbox_in_full_img[:2], full_img_bbox[:2], mask_bbox_in_full_img[:2])
                        updated_mask_bbox_max = np.where(full_img_bbox[2:] < mask_bbox_in_full_img[2:], full_img_bbox[2:], mask_bbox_in_full_img[2:])
                        updated_mask_bbox = np.append(updated_mask_bbox_min, updated_mask_bbox_max)
                        all_mask_results["detection_boxes"][update_mask_id] = updated_mask_bbox
                        #np.append(all_mask_results["detection_scores"][update_mask_id],masked_result["detection_scores"][0][mask_num])
                        #print(f"afte rupdate: {all_mask_results['detection_scores'][update_mask_id]}")
                        #else:
                        #time_delta = "{:.3f}".format(time.time() - start_time)
                           
                        
                        #with np.printoptions(threshold=np.inf):
                        #print(f"new mask area: {mask}")
                        # Insert the updated mask in the full image mask
                        # full_image_mask[height:height+window_height, width:width+window_width] = mask
                        #if i in range(74, 75):
                            #with np.printoptions(threshold=np.inf):
                                #print(f"full image mask: {np.where(full_image_mask)}")
                        # Update mask metadata
                        # for k,v in all_mask_results.items():
                        #     if hasattr(v, 'shape'):
                        #         print(f"{k}: {v.shape}")
                        # print(f"All masks: {all_mask_results}")
                        # print(f"masked res: {masked_result}")
                    #print(full_image_mask)
                    cropped_img_numpy = cutout_image.numpy()
                    cropped_img_numpy = cropped_img_numpy[0].astype(np.uint8)
                    #print(cropped_img_numpy)
                    #print(cropped_img_numpy.shape)
                    # save cropped image
                    # if config.cache_cutouts:
                        # cv2.imwrite(os.path.join(out_dir, f"{paths.filename}_h{height}_w{width}.jpg"), cropped_img_numpy)
                    cropped_images.append(cutout_image)
                time_delta = "{:.3f}".format(time.time() - cutout_time)
                LOGGER.debug(__name__, f"time checkpoint: Time for cutout: {time_delta} s.")
                #time_delta = "{:.3f}".format(time.time() - after_mask_time)
                #LOGGER.info(__name__, f"time checkpoint: after mask updated: {time_delta} s.")
                    
                    #LOGGER.info(__name__, f"Cutout: H{height}:{height+window_height} x W{width}:{width+window_width}")
                    
                i += 1
                    # Convert the image to a numpy array
        detection_classes = []
        detection_scores = []
        if not isinstance(image, np.ndarray):
              image = image.numpy()               

              
        # Make final calculations and decisions about the results.
        for mask_num in range(all_mask_results["num_detections"]):
            
            bbox = all_mask_results["detection_boxes"][mask_num]
            
            
            h = int(bbox[0]*image.shape[1])
            w = int(bbox[1]*image.shape[2])
            h2, w2 = int(bbox[2]*image.shape[1]), int(bbox[3]*image.shape[2])
            show_img = image[0]
            #show_img = image[0, h-10:h+10, w-10:2+10]
            #print(f"bbox {bbox}, showimg: {show_img.shape}")
            majority_vote_class = _poll_array(all_mask_results["detection_classes"][mask_num])
            detection_classes.append(majority_vote_class)
            average_score = np.mean(all_mask_results["detection_scores"][mask_num])
            detection_scores.append(average_score)
            avg_score_round = round(average_score, 3)
            cv2.rectangle(show_img, (w, h), (w2,h2), (255,0,0), thickness=1)
            cv2.putText(show_img, 
                f"n:{mask_num},c:{majority_vote_class},s:{avg_score_round}", 
                (w, h), 
                cv2.FONT_HERSHEY_COMPLEX, 
                0.3, 
                (255,0,0), 
                thickness=1)
            #print(image.dtype)
            #print(image.shape)
            #resized = cv2.resize(show_img, (1000, 2000),interpolation = cv2.INTER_AREA)s
            #cv2.imwrite(f"C:\\Users\\norpal\\Documents\\numbered_{h}_{w}.jpg", show_img)
            #cv2.imshow(f"{mask_num}: {average_score} - {h} - {w}", show_img)
            #cv2.waitKey(0)
        cv2.destroyAllWindows()
        all_mask_results["detection_classes"] = np.asarray([detection_classes])
        all_mask_results["detection_scores"] = np.asarray([[detection_scores]])
        all_mask_results["detection_boxes"] = np.asarray([all_mask_results["detection_boxes"]])
        #print(f"All results: {all_mask_results}")
        LOGGER.debug(__name__, f"'all_mask_results' before saving: {all_mask_results}")

        # # If we have reached the maximum number of workers. Wait for them to finish
        if len(self.workers) >= self.max_num_async_workers:
            self._wait_for_workers()
        # # Create workers for the current image.
        self._spawn_workers(paths, image, all_mask_results)
        #end_time =  time.time()
        time_delta = "{:.3f}".format(time.time() - full_img_time)
        LOGGER.info(__name__,f"Full image time: {time_delta} s.")
        #print(f"Full cutout time: {time_delta} s.")
        LOGGER.info(__name__,f"Masks added from the 'sliding window': {additional_masks}")
        return cropped_images
    def map_masks_on_cutouts_to_original_img(masks, original_img):
        pass
    
    def process_cutout_images(self, original_image, cutouts, paths):
        start_time = time.time()
        
        # Create a mask array of the original image
        original_image_mask = np.zeros(original_image.shape[1:3])
        
        # Define dims of the sliding window        
        window_scale = config.cutout_dim_downscale
        window_height = int(original_image_mask.shape[0]/window_scale)
        window_width = int(original_image_mask.shape[1]/window_scale)

        # Compute masks for the objects detected in each image.
        for i, cutout in enumerate(cutouts):
            masked_results = self.masker.mask(cutout)
            time_delta = "{:.3f}".format(time.time() - start_time)
            mapped_pixel_term = (config.cutout_step_factor*i)
            window_height_scale, window_width_scale = config.cutout_dim_downscale
        
            # Get the dimensions of the sliding window
            window_height = int(original_image_mask.shape[0]/window_height_scale)
            window_width = int(original_image_mask.shape[1]/window_width_scale)
            
            relevant_mask_slice = original_image_mask[mapped_pixel_term:mapped_pixel_term+window_height, mapped_pixel_term:mapped_pixel_term+window_width]
            
            
            # Apply each the mask to 
            for mask in masked_results["detection_masks"][0]:
                
                #original_image_mask[:,] = 1 if mask_pixel else 
                original_image_mask[mapped_pixel_term:mapped_pixel_term+window_height, 
                                    mapped_pixel_term:mapped_pixel_term+window_width] = np.where(
                                        mask == True and relevant_mask_slice == 0, mask, relevant_mask_slice)
            
        pass
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
        
        #for i, mask in enumerate(mask_results["detection_masks"][0]):
            #print(f"mask [{i}] shape: {mask.shape}, {mask}")
        # LOGGER.info(__name__, f"Masked results1: {mask_results['detection_masks'][0].shape}")
        # LOGGER.info(__name__, f"Masked results1: {mask_results['detection_masks']}")
        # LOGGER.info(__name__, f"Masked results2: {mask_results['detection_masks'][0]}")
        
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
def _poll_array(poll_item):
    """
    Finds the majority vote in a numpy array.
    """
    values, counts = np.unique(poll_item, return_counts=True)
    index = np.argmax(counts)
    return values[index]
def _coordinate_mapping(y, x, original_img, cutout_img, bounding_w, bounding_h):
    """
    x, y = %/cutout
    """
    #print(f"x: {x}, y: {y}")
    X = bounding_w + (x*cutout_img.shape[2])
    Y = bounding_h + (y * cutout_img.shape[1])
    #print(f"X: {X}({X/original_img.shape[2]}) Y: {Y}({Y/original_img.shape[1]})")
    return X/original_img.shape[2], Y/original_img.shape[1]
    
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
