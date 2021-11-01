import cv2
import os
import numpy as np

# Change contrast
def contrast_brightness(img, alpha, beta):
    # alpha 1  beta 0      --> no change  
    # 0 < alpha < 1        --> lower contrast  
    # alpha > 1            --> higher contrast  
    # -127 < beta < +127   --> good range for brightness values

    # Example: new_image = cv.convertScaleAbs(image, alpha=alpha, beta=beta)

    for a in alpha:
        for b in beta:

            contrast_brightness = cv2.convertScaleAbs(img, alpha=a, beta=b)
            cv2.imwrite(
                os.path.join(out_path, "preprocessing_alpha_beta",f"contrast_brightness_a_{a}_b_{b}.jpg"),
                contrast_brightness
                )
def sharpen_img(img, ddepth, kernel, iter_num=1):
    image_sharp = img
    for i in range(1,iter_num+1):
        image_sharp = cv2.filter2D(image_sharp, ddepth, kernel)
        #cv2.imshow("sharp", image_sharp)
        cv2.imwrite(
            os.path.join(out_path, "preprocessing_sharp", f"sharp_{i}.jpg"),
            image_sharp)
def make_cutouts(img, window_width_scale, window_height_scale, step_factor=400):
    print(img.shape)
    img_h, img_w = img.shape[:2]
    window_height = int(img_h/window_height_scale)
    window_width = int(img_w/window_width_scale)

    for x in range(0,img_h - window_height + 1,step_factor):
        for y in range(0,img_w - window_width +1, step_factor):
            cropped_img = img[
                x:x+window_height,
                y:y+window_width
                ]
            print(f"x: {x}, y: {y}")
            
            cv2.imwrite(os.path.join(out_path,"preprocessing_crop_2", f"cropped_x_{x}_y_{y}.jpg"), cropped_img)   

if __name__ == '__main__':
    out_path = os.environ["OUT_PATH_PREPROCESS"]
    image = cv2.imread(os.environ["IN_IMAGE_PREPROCESS"])
    
    # Load image
    #image = cv2.resize(image, (500,600), interpolation=cv2.INTER_AREA)

    # 1. Adjust brightness and contrast
    alpha =[0.7, 1.0, 1.2, 1.5, 1.8, 2.0, 2.5, 3.0 ]
    beta = [-100, -50, 0, 50, 100]
    #contrast_brightness(image, alpha, beta)
    
    # 2. Sharpen image
    k = np.array([
        [0, -1, 0],
        [-1, 5, -1],
        [0, -1, 0]
    ])
    ddepth = -1
    # for sharp_num in range(1,10):
    #     sharpen_img(image, ddepth, k, iter_num=sharp_num)

    make_cutouts(image, 4, 4)

    # exit images
    # cv2.waitKey()
    # cv2.destroyAllWindows()
    