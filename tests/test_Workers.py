import os
import pytest
from unittest import mock
import numpy as np
import pickle
from PIL import Image
import multiprocessing

from src.Workers import SaveWorker, EXIFWorker
from src.io.TreeWalker import Paths

from tests.helpers import check_file_exists


@pytest.fixture
def get_image_info(get_tmp_data_dir):
    def _get_info(enable_archive):
        tmp_dir = get_tmp_data_dir(subdirs=["real"])

        tmp_in = os.path.join(tmp_dir, "real")
        mirror_dirs = [os.path.join(tmp_dir, "out")]
        if enable_archive:
            mirror_dirs.append(os.path.join(tmp_dir, "arch"))
        
        for md in mirror_dirs:
            os.makedirs(md)

        paths = Paths(
            base_input_dir=tmp_in,
            base_mirror_dirs=mirror_dirs,
            input_dir=tmp_in,
            mirror_dirs=mirror_dirs,
            filename="Fy50_Rv003_hp01_f1_m01237.jpg"
        )
        img = np.array(Image.open(paths.input_file))[None, ...]
        with open(os.path.join(paths.input_dir, "Fy50_Rv003_hp01_f1_m01237_mask_results.pkl"), "rb") as f:
            mask_results = pickle.load(f)

        return img, mask_results, paths
    return _get_info


@pytest.mark.parametrize("remote_mask,local_mask,enable_archive,enable_async", [
    (False, False, False, True),
    (False, False, False, False),
    (True, True, True, True),
    (True, True, True, False),
])
def test_SaveWorker(get_config, get_image_info, remote_mask, local_mask, enable_archive, enable_async):
    config = get_config(remote_mask=remote_mask, local_mask=local_mask, archive_mask=enable_archive,
                        archive_json=enable_archive, enable_async=enable_async)

    img, mask_results, paths = get_image_info(enable_archive=enable_archive)

    # Make the output-json to emulate the EXIFWorker
    with open(paths.output_json, "w") as f:
        f.write("Output JSON")
    # Create a multiprocessing pool
    if enable_async:
        pool = multiprocessing.Pool(1)
    else:
        pool = None
    # Run the worker
    with mock.patch("src.Workers.config", new=config):
        worker = SaveWorker(pool, paths, img, mask_results)
        result = worker.get()
    assert result == 0

    # Check expected output files
    check_file_exists(paths.output_file)
    check_file_exists(paths.input_webp, invert=not local_mask)
    check_file_exists(paths.output_webp, invert=not remote_mask)

    if enable_archive:
        check_file_exists(paths.archive_file)
        check_file_exists(paths.archive_json)
        check_file_exists(paths.archive_webp)


@pytest.mark.parametrize("remote_json,local_json,enable_async", [
    (False, False, False),
    (False, False, True),
    (True, True, True),
    (True, True, False),
])
def test_EXIFWorker(get_config, get_image_info, remote_json, local_json, enable_async):
    config = get_config(remote_json=remote_json, local_json=local_json, enable_async=enable_async)

    img, mask_results, paths = get_image_info(enable_archive=False)

    # Create a multiprocessing pool
    if enable_async:
        pool = multiprocessing.Pool(1)
    else:
        pool = None
    # Run the worker
    with mock.patch("src.Workers.config", new=config):
        worker = EXIFWorker(pool, paths, mask_results)
        exif = worker.get()

    # Check that the exif dict contains the required keys
    assert set(exif.keys()) == EXPECTED_EXIF_KEYS
    # Check expected output files
    check_file_exists(paths.input_json, invert=not local_json)
    check_file_exists(paths.output_json, invert=not remote_json)


EXPECTED_EXIF_KEYS = {
    "exif_tid",
    "exif_dato",
    "exif_speed",
    "exif_heading",
    "exif_gpsposisjon",
    "exif_strekningsnavn",
    "exif_fylke",
    "exif_vegkat",
    "exif_vegstat",
    "exif_vegnr",
    "exif_hp",
    "exif_meter",
    "exif_feltkode",
    "exif_mappenavn",
    "exif_filnavn",
    "exif_strekningreferanse",
    "exif_imageproperties",
    "exif_reflinkid",
    "exif_reflinkposisjon",
    "exif_reflinkinfo",
    "exif_xptitle",
    "bildeuuid",
    "detekterte_objekter",
}
