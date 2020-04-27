import os
import re
import pytest
import platform
import warnings
from pkg_resources import get_distribution
from importlib import import_module


from config import PROJECT_ROOT


IGNORE_NAMES = ["pip"]
CONVERT_NAMES = {
    "tensorflow-gpu": "tensorflow",
    "cx-oracle": "cx_Oracle",
    "opencv-python": "cv2",
    "pillow": "PIL",
}
EXTRA_ALLOWED_VERSIONS = {
    "mkl": ["2.3.0"],
    "cv2": ["4.2.0"]
}


@pytest.fixture
def required_modules():
    file_path = os.path.join(PROJECT_ROOT, "environment.yml")
    modules = []
    module_pattern = re.compile(r"([\w-]*)={1,2}([\w\.-]*)")
    with open(file_path, "r") as f:
        for line in f:
            matches = module_pattern.findall(line)
            if matches:
                modules.append(matches[0])
    return modules


def get_installed_version(name):
    if name == "python":
        return platform.python_version()
    try:
        return get_distribution(name).version
    except:
        pass
    try:
        return import_module(name).__version__
    except:
        pass

    warnings.warn(f"Could not find version for package '{name}'.")
    return None


def compare_versions(name, required, installed):
    extra_allowed = EXTRA_ALLOWED_VERSIONS.get(name, [])
    allowed_versions = [required] + extra_allowed
    assert installed in allowed_versions, f"Invalid version for module '{name}': {installed} not in {allowed_versions}."


def test_environment(required_modules):
    for name, required_version in required_modules:
        if name not in IGNORE_NAMES:
            name = CONVERT_NAMES.get(name, name)
            installed_version = get_installed_version(name)
            compare_versions(name, required_version, installed_version)
