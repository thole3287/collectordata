import os
import cv2
from tqdm import tqdm
import albumentations as A

IMAGE_DIR = "images_raw"
OUT_DIR = "images_aug"

# Tạo thư mục output nếu chưa tồn tại
os.makedirs(OUT_DIR, exist_ok=True)

# Định nghĩa các transform augmentation cụ thể
transforms = [
    A.Compose([A.Rotate(limit=(-15, -15), p=1.0)]),  # Xoay 15 độ trái
    A.Compose([A.Rotate(limit=(15, 15), p=1.0)]),    # Xoay 15 độ phải
    A.Compose([A.HorizontalFlip(p=1.0), A.Rotate(limit=(-15, -15), p=1.0)]),  # Flip và xoay 15 độ trái
    A.Compose([A.HorizontalFlip(p=1.0), A.Rotate(limit=(15, 15), p=1.0)]),    # Flip và xoay 15 độ phải
]

# Tên mô tả cho từng transform
transform_names = [
    "rotate_left_15",
    "rotate_right_15",
    "flip_rotate_left_15",
    "flip_rotate_right_15"
]

# Xử lý từng ảnh trong thư mục
for img_name in tqdm(os.listdir(IMAGE_DIR)):
    img_path = os.path.join(IMAGE_DIR, img_name)
    
    # Bỏ qua nếu không phải file ảnh
    if not img_name.lower().endswith(('.jpg', '.jpeg', '.png', '.bmp')):
        continue
    
    # Đọc ảnh
    image = cv2.imread(img_path)
    
    # Kiểm tra nếu ảnh đọc được thành công
    if image is None:
        print(f"Không thể đọc ảnh: {img_path}")
        continue
    
    # Chuyển đổi từ BGR sang RGB (OpenCV đọc BGR, albumentations cần RGB)
    image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

    # Tạo 4 phiên bản augment cho mỗi ảnh
    for i, transform in enumerate(transforms):
        aug = transform(image=image)["image"]
        
        # Tạo tên file output
        base_name = os.path.splitext(img_name)[0]
        ext = os.path.splitext(img_name)[1]
        out_name = f"{base_name}_{transform_names[i]}{ext}"

        # Chuyển đổi lại từ RGB sang BGR và lưu ảnh
        cv2.imwrite(
            os.path.join(OUT_DIR, out_name),
            cv2.cvtColor(aug, cv2.COLOR_RGB2BGR)
        )

print(f"\nHoàn thành! Đã tạo các ảnh augment trong thư mục: {OUT_DIR}")
