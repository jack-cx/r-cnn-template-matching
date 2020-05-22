import cv2
import numpy as np
import os
import time
import shutil


class AugmentedDataset():
    def __init__(self, root):
        self.root = root

        # self.imgs_backgrounds = list(sorted(os.listdir(os.path.join(root, 'backgrounds'))))
        self.imgs_backgrounds = list(
            sorted([f for f in os.listdir(os.path.join(root, 'backgrounds')) if not f.startswith('.')]))
        self.imgs_templates = list(
            sorted([f for f in os.listdir(os.path.join(root, 'templates')) if not f.startswith('.')]))

        self.template_masks = self.create_template_masks(self.imgs_templates)

        # number of max copies of the same template in one augmented image
        self.max_templates = 3
        # maximum relation between background to template
        # the larger this value, the smaller is the maximum template size relative to its background
        self.max_temp_back_rel = 6
        # min scale of template when scaling the image down

        # the larger this value, the larger is the minimum template size relative to its background
        self.min_augm_scale = 0.5
        # max rotation angle in the augmentation
        self.max_augm_rot = 20.0
        self.max_augm_rot_tem = 40.0

    def create_template_masks(self, imgs_templates):
        template_masks = []
        for template_name in imgs_templates:
            template = cv2.imread(os.path.join(self.root, 'templates', template_name), cv2.IMREAD_UNCHANGED)
            alpha_channel = template[:, :, 3]
            _, template_mask = cv2.threshold(alpha_channel, 254, 1, cv2.THRESH_BINARY)
            template_mask = template_mask.reshape((alpha_channel.shape[0], alpha_channel.shape[1]))
            template_masks.append(template_mask)
        return template_masks

    def get_random_background(self):
        idx = np.random.randint(0, len(self.imgs_backgrounds))
        return self.imgs_backgrounds[idx]

    def augment_templates(self, template, template_mask, amount):
        augmented_templates = []
        augmented_template_masks = []
        for i in range(amount):
            scale = np.random.uniform(self.min_augm_scale, 1.0)
            template = cv2.resize(template, dsize=(0, 0), fx=scale, fy=scale)
            template_mask = cv2.resize(template_mask, dsize=(0, 0), fx=scale, fy=scale)
            angle = np.random.uniform(-self.max_augm_rot_tem, self.max_augm_rot_tem)
            template = self.rotate_image_keep_size(template, angle)
            template_mask = self.rotate_image_keep_size(template_mask, angle)

            augmented_templates.append(template)
            augmented_template_masks.append(template_mask)

        return augmented_templates, augmented_template_masks

    def stitch_templates_to_background(self, background, templates, template_masks, temp_count):
        back_height = np.shape(background)[0]
        back_width = np.shape(background)[1]

        mask_array = [np.zeros_like(background[:, :, 0]) for _ in range(len(templates))]

        for k in range(len(templates)):
            # if len(templates) > 0:

            rand_idx_array = np.random.permutation(len(templates[k]))
            # print(np.shape(templates))
            col = 1
            for idx in rand_idx_array:
                template = templates[k][idx]
                template_mask = template_masks[k][idx]
                temp_height = np.shape(template)[0]
                temp_width = np.shape(template)[1]
                y_coord = np.random.randint(0, back_height - temp_height)
                x_coord = np.random.randint(0, back_width - temp_width)
                y1, y2 = y_coord, y_coord + temp_height
                x1, x2 = x_coord, x_coord + temp_width

                for y in range(temp_height):
                    for x in range(temp_width):
                        if template_mask[y, x] > 0:
                            mask_array[k][y1 + y, x1 + x] = template_mask[y, x] * col
                        # mask_array[y1:y2, x1:x2] = template_mask * count_temp_cumsum[i]
                col += 1

                background_mask = 1.0 - template_mask

                for c in range(0, 3):
                    background[y1:y2, x1:x2, c] = (
                            template_mask * template[:, :, c] + background_mask * background[y1:y2, x1:x2, c])

        return background, mask_array

    def rotate_image_keep_size(self, img, degreesCCW, scaleFactor=1):
        (oldY, oldX) = img.shape[:2]  # note: numpy uses (y,x) convention but most OpenCV functions use (x,y)
        M = cv2.getRotationMatrix2D(center=(oldX / 2, oldY / 2), angle=degreesCCW,
                                    scale=scaleFactor)  # rotate about center of image.

        # choose a new image size.
        newX, newY = oldX * scaleFactor, oldY * scaleFactor
        # include this if you want to prevent corners being cut off
        r = np.deg2rad(degreesCCW)
        newX, newY = (abs(np.sin(r) * newY) + abs(np.cos(r) * newX), abs(np.sin(r) * newX) + abs(np.cos(r) * newY))

        # the warpAffine function call, below, basically works like this:
        # 1. apply the M transformation on each pixel of the original image
        # 2. save everything that falls within the upper-left "dsize" portion of the resulting image.

        # So I will find the translation that moves the result to the center of that region.
        (tx, ty) = ((newX - oldX) / 2, (newY - oldY) / 2)
        M[0, 2] += tx  # third column of matrix holds translation, which takes effect after rotation.
        M[1, 2] += ty

        rotatedImg = cv2.warpAffine(img, M, dsize=(int(newX), int(newY)))
        return rotatedImg

    def rotate_image(self, image, angle):
        image_center = tuple(np.array(image.shape[1::-1]) / 2)
        rot_mat = cv2.getRotationMatrix2D(image_center, angle, 1.0)
        result = cv2.warpAffine(image, rot_mat, image.shape[1::-1], flags=cv2.INTER_LINEAR)
        return result

    def get_train_data(self, amount):
        aug_imgs = []
        aug_masks = []

        # data augmentation for background, template, and template mask
        for i in range(amount):
            print("Image: {}".format(i))
            background_name = self.get_random_background()
            background = cv2.imread(os.path.join(self.root, 'backgrounds', background_name), cv2.IMREAD_UNCHANGED)
            background_size = background.shape[0] * background.shape[1]

            stitch_templates = []
            stitch_template_masks = []
            temp_count = []
            for j in range(len(self.imgs_templates)):
                template = cv2.imread(os.path.join(self.root, 'templates', self.imgs_templates[j]),
                                      cv2.IMREAD_UNCHANGED)
                template_size = template.shape[0] * template.shape[1]

                temp_back_rel = template_size / background_size
                temp_normalization = 1 / (temp_back_rel * self.max_temp_back_rel)
                template = cv2.resize(template, dsize=(0, 0), fx=temp_normalization, fy=temp_normalization)
                template_mask = cv2.resize(self.template_masks[j], dsize=(0, 0), fx=temp_normalization,
                                           fy=temp_normalization)


                rand = np.random.randint(1, self.max_templates + 1)


                if rand > 0:
                    augmented_templates, augmented_template_masks = self.augment_templates(template, template_mask,
                                                                                           rand)
                    stitch_templates.append(augmented_templates)
                    stitch_template_masks.append(augmented_template_masks)
                temp_count.append(rand)
                # print(rand)

            background_angle = np.random.uniform(-self.max_augm_rot, self.max_augm_rot)
            # background = self.rotate_image(aug_mask[k], background_angle)
            aug_img, aug_mask = self.stitch_templates_to_background(background, stitch_templates, stitch_template_masks,
                                                                    temp_count)

            for k in range(len(aug_mask)):
                aug_mask[k] = self.rotate_image(aug_mask[k], background_angle)
            aug_img = self.rotate_image(aug_img, background_angle)

            cv2.imwrite("dataset/images/{}.png".format(i), aug_img)
            # aug_imgs.append(aug_img)
            # aug_masks.append(aug_mask)
            os.mkdir("dataset/masks/{}".format(i))
            # cv2.imshow('image', aug_img)
            # cv2.waitKey()
            for k, aug_m in enumerate(aug_mask):
                cv2.imwrite("dataset/masks/{}/{}.png".format(i, k), aug_m)
                # mask = cv2.threshold(aug_m, 0, 255, cv2.THRESH_BINARY)
                # cv2.imshow('mask', mask[1])
                # cv2.waitKey()
        # return aug_imgs, aug_masks


start = time.time()

np.random.seed(12345)
shutil.rmtree("dataset")
os.mkdir("dataset")
os.mkdir("dataset/images")
os.mkdir("dataset/masks")
dataset = AugmentedDataset(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'test_images'))
dataset.get_train_data(100)
end = time.time()
print(end - start)
# cv2.imshow('image', imgs[0])

