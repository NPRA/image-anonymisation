import os

from src.io.TreeWalker import TreeWalker


EXPECTED_FILES = [
    os.path.join("tests", "data", "fake", "%#{} _  _ _", "test_0.jpg"),
    os.path.join("tests", "data", "fake", "åæø", "test_1.jpg"),
    os.path.join("tests", "data", "fake", "corrupted.jpg"),
    os.path.join("tests", "data", "fake", "test_2.jpg"),
]


def _check_files(tree_walker, expected_files):
    found_files = [os.path.join(input_dir, filename) for input_dir, _, filename in tree_walker.walk()]
    assert set(found_files) == set(expected_files), "Found files do not match"


def test_TreeWalker_find_files():
    """
    Check that the TreeWalker finds a;; the files it is supposed to find.
    """
    base_input_dir = os.path.join("tests", "data", "fake")
    base_output_dir = os.path.join("tests", "data", "out")

    # Check that all files are discovered when .webp skipping is disabled
    _check_files(TreeWalker(input_folder=base_input_dir, mirror_folders=[base_output_dir], skip_webp=False,
                            precompute_paths=False), EXPECTED_FILES)
    _check_files(TreeWalker(input_folder=base_input_dir, mirror_folders=[base_output_dir], skip_webp=False,
                            precompute_paths=True), EXPECTED_FILES)

    # Check that all files are discovered when .webp skipping is disabled
    expected_files = EXPECTED_FILES.copy()
    expected_files.remove(os.path.join("tests", "data", "fake", "åæø", "test_1.jpg"))

    _check_files(TreeWalker(input_folder=base_input_dir, mirror_folders=[base_output_dir], skip_webp=True,
                            precompute_paths=False), expected_files)
    _check_files(TreeWalker(input_folder=base_input_dir, mirror_folders=[base_output_dir], skip_webp=True,
                            precompute_paths=True), expected_files)


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
        output_dir = tree_walker._get_mirror_paths(input_dir)[0]
        assert output_dir == expected_output_dir, f"Expected output dir '{expected_output_dir}' for input dir " \
                                                  f"'{input_dir}' but got '{output_dir}' instead."
