from importlib import import_module


MODULES = [
    ("h5py", "2.10.0"),
    ("mkl", "2.3.0"),
    ("numpy", "1.18.1"),
    ("pip", "20.0.2"),
    ("scipy", "1.3.1"),
    ("tensorflow", "2.1.0"),
    ("xmltodict", "0.12.0"),
    ("cv2", "4.2.0"),
    ("PIL", "7.0.0"),
    ("webp", "0.1.0a15")
]


if __name__ == '__main__':
    for module_name, required_version in MODULES:
        try:
            module = import_module(module_name)
        except ImportError as e:
            print("[Error]", e)
            continue
        if hasattr(module, "__version__"):
            current_version = module.__version__
            if current_version == required_version:
                print("[OK]", module_name, module.__version__)
            else:
                print("[Error]", module_name, f"Required: {required_version}. Found {current_version}")
        else:
            print(f"[Warning] No version found for module '{module_name}'")
