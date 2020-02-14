from importlib import import_module


MODULES = [
    ("h5py", "2.10.0"),
    ("jupyter", "1.0.0"),
    ("matplotlib", "3.1.3"),
    ("mkl", "2.3.0"),
    ("numpy", "1.18.1"),
    ("pandas", "1.0.1"),
    ("pip", "20.0.2"),
    ("sklearn", "0.22.1"),
    ("scipy", "1.3.1"),
    ("tensorflow", "1.15.0"),
    ("tqdm", "4.42.1"),
    ("PIL", "7.0.0"),
    ("object_detection", "0.1")
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
