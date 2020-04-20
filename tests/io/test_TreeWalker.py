import os
import pytest
from shutil import copy2

from src.io.TreeWalker import TreeWalker


EXPECTED_FILES = [
    os.path.join("%#{} _  _ _", "test_0.jpg"),
    os.path.join("åæø", "test_1.jpg"),
    "corrupted.jpg",
    "test_2.jpg",
]


@pytest.mark.parametrize("precompute_paths,skip_webp", [
    (True, True),
    (True, False),
    (False, True),
    (False, False)
])
def test_TreeWalker_find_files(get_tmp_data_dir, precompute_paths, skip_webp):
    """
    Check that the TreeWalker finds all the files it is supposed to find.
    """
    tmp_dir = get_tmp_data_dir(subdirs=["fake"])

    base_input_dir = os.path.join(tmp_dir, "fake")
    base_output_dir = os.path.join(tmp_dir, "out")

    expected_files = EXPECTED_FILES.copy()
    if skip_webp:
        # Copy ææå\test_1.webp to the corresponding output directory to simulate an already masked image
        output_dir = os.path.join(base_output_dir, "åæø")
        os.makedirs(output_dir)
        copy2(os.path.join(base_input_dir, "åæø", "test_1.webp"), os.path.join(output_dir, "test_1.webp"))
        # Remove "test_1.jpg" from the list of expected files
        expected_files.remove(os.path.join("åæø", "test_1.jpg"))

    # Prepend the tmp directory to the list of expected files.
    expected_files = [os.path.join(base_input_dir, f) for f in expected_files]

    # Instantiate the TreeWalker
    tree_walker = TreeWalker(input_folder=base_input_dir, mirror_folders=[base_output_dir], skip_webp=skip_webp,
                             precompute_paths=precompute_paths)

    # Check files
    found_files = [p.input_file for p in tree_walker.walk()]
    assert set(found_files) == set(expected_files), "Found files do not match"


def test_TreeWalker_input_output_correspondence():
    """
    Make sure that the the mirror paths from the TreeWalker are correct.
    """
    base_input_dir = "foo"
    base_output_dir = "bar"

    tree_walker = TreeWalker(input_folder=base_input_dir, mirror_folders=[base_output_dir])

    # Convenience alias
    j = lambda *args: os.path.join(*args)
    # Test pairs. (Sample input dir, expected output dir)
    test_subdirs = [
        (j("foo", "foo", "foo"), j("bar", "foo", "foo")),
        (j("foo", "bar", "bar"), j("bar", "bar", "bar")),
        (j("foo", "Foo"), j("bar", "Foo")),
        (j("foo", "foo 1234", "456"), j("bar", "foo 1234", "456"))
    ]

    for input_dir, expected_output_dir in test_subdirs:
        output_dir = tree_walker._get_mirror_dirs(input_dir)[0]
        assert output_dir == expected_output_dir, f"Expected output dir '{expected_output_dir}' for input dir " \
                                                  f"'{input_dir}' but got '{output_dir}' instead."
