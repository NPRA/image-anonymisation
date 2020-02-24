import pytest
import numpy as np

from src.Masker import Masker


def test_Masker_bad_input():
    masker = Masker()

    bad_imgs = {
        "Negative values":      np.full((1, 100, 200, 3), -1),
        "NaNs":                 np.full((1, 100, 200, 3), np.nan),
        "Infs":                 np.full((1, 100, 200, 3), np.inf),
        "Zero dimension":       np.empty((1, 0, 100, 3)),
        "Wrong channel number": np.ones((1, 100, 100, 1), dtype=np.uint8),
        "Wrong batch number":   np.ones((5, 100, 100, 3), dtype=np.uint8),
        "Wrong ndim":           np.ones((2, 2), dtype=np.uint8),
    }

    for desc, img in bad_imgs.items():
        with pytest.raises(AssertionError):
            masker.mask(img)
