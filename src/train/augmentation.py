import imgaug.augmenters as iaa


def get_agumentations():
    """
    Get image-agumenters to use in training.

    :return: Image augmenter
    :rtype: iaa.SomeOf
    """
    augmenter = iaa.SomeOf((0, None), [
        iaa.Identity(),
        iaa.Fliplr(0.5),
        iaa.GammaContrast((1.0, 1.8)),
        iaa.MotionBlur(k=(11, 21), angle=[-90.0, 90.0])
    ])
    return augmenter


if __name__ == '__main__':
    get_agumentations()
