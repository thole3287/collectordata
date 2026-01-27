import os
import shutil
import torch
import cv2  # Để lưu ảnh từ numpy array
from ultralytics import YOLO, RTDETR
from ultralytics.utils.metrics import box_iou

# Đường dẫn (thay bằng thật)
images_folder = r"E:\phaogo\Master\DataMiningAI\images\4K camera example for Traffic Monitoring Road"  # ví dụ
base_results_folder = r"E:\phaogo\Master\DataMiningAI\images\Vehicle_Detection_Image_Dataset\train\result_labels3"
os.makedirs(base_results_folder, exist_ok=True)

yolo26_results = os.path.join(base_results_folder, "yolo26")
rtdetr_results = os.path.join(base_results_folder, "rtdetr")
disagree_folder = os.path.join(base_results_folder, "disagree")
final_pseudo_folder = os.path.join(base_results_folder, "final_pseudo")

os.makedirs(yolo26_results, exist_ok=True)
os.makedirs(rtdetr_results, exist_ok=True)
os.makedirs(disagree_folder, exist_ok=True)
os.makedirs(final_pseudo_folder, exist_ok=True)

original_disagree = os.path.join(disagree_folder, "original")
yolo26_disagree = os.path.join(disagree_folder, "yolo26")
rtdetr_disagree = os.path.join(disagree_folder, "rtdetr")
os.makedirs(original_disagree, exist_ok=True)
os.makedirs(yolo26_disagree, exist_ok=True)
os.makedirs(rtdetr_disagree, exist_ok=True)

visualized_folder = os.path.join(final_pseudo_folder, "visualized")
os.makedirs(visualized_folder, exist_ok=True)

vehicle_classes = [1, 2, 3, 5, 7]

model_yolo26 = YOLO("yolo26n.pt")
model_rtdetr = RTDETR("rtdetr-l.pt")

print("Predicting with YOLO26...")
results_yolo26 = model_yolo26.predict(
    source=images_folder,
    conf=0.25,
    iou=0.45,
    imgsz=640,
    classes=vehicle_classes,
    save=True, save_txt=True, save_conf=True,
    project=yolo26_results, name="predict", exist_ok=True
)

print("Predicting with RT-DETR...")
results_rtdetr = model_rtdetr.predict(
    source=images_folder,
    conf=0.25,
    iou=0.45,
    imgsz=640,
    classes=vehicle_classes,
    save=True, save_txt=True, save_conf=True,
    project=rtdetr_results, name="predict", exist_ok=True
)

yolo26_labels_dir = os.path.join(yolo26_results, "predict", "labels")
rtdetr_labels_dir = os.path.join(rtdetr_results, "predict", "labels")

# Không cần visual_dir nữa vì ta dùng plot()

print("Debug: Processing images...")

for res_yolo, res_rtdetr in zip(results_yolo26, results_rtdetr):
    img_path = res_yolo.path
    img_name = os.path.basename(img_path)
    base_name = img_name.rsplit('.', 1)[0]

    boxes_yolo = res_yolo.boxes.xyxy if res_yolo.boxes is not None and len(res_yolo.boxes) > 0 else torch.empty((0, 4), device='cpu')
    conf_yolo  = res_yolo.boxes.conf if res_yolo.boxes is not None and len(res_yolo.boxes) > 0 else torch.empty((0,), device='cpu')

    boxes_rtdetr = res_rtdetr.boxes.xyxy if res_rtdetr.boxes is not None and len(res_rtdetr.boxes) > 0 else torch.empty((0, 4), device='cpu')
    conf_rtdetr  = res_rtdetr.boxes.conf if res_rtdetr.boxes is not None and len(res_rtdetr.boxes) > 0 else torch.empty((0,), device='cpu')

    mean_conf_yolo = conf_yolo.mean().item() if len(conf_yolo) > 0 else 0.0
    mean_conf_rtdetr = conf_rtdetr.mean().item() if len(conf_rtdetr) > 0 else 0.0

    if mean_conf_yolo > mean_conf_rtdetr:
        winner = "yolo26"
        winner_res = res_yolo
        winner_conf = mean_conf_yolo
        winner_labels_dir = yolo26_labels_dir
    else:
        winner = "rtdetr"
        winner_res = res_rtdetr
        winner_conf = mean_conf_rtdetr
        winner_labels_dir = rtdetr_labels_dir

    print(f"Ảnh {img_name}: Winner = {winner} (mean conf: {winner_conf:.3f})")

    # Lưu hình gốc + label winner
    shutil.copy(img_path, os.path.join(final_pseudo_folder, img_name))
    winner_label_path = os.path.join(winner_labels_dir, base_name + '.txt')
    if os.path.exists(winner_label_path):
        shutil.copy(winner_label_path, os.path.join(final_pseudo_folder, base_name + '.txt'))
    else:
        print(f"Warning: Label not found for {img_name}")

    # Tạo và lưu visualize từ winner bằng plot()
    annotated_img = winner_res.plot()  # Trả về numpy BGR với boxes vẽ
    vis_path = os.path.join(visualized_folder, f"{winner}_{img_name}")
    cv2.imwrite(vis_path, annotated_img)
    if os.path.exists(vis_path):
        print(f"Saved visualize: {vis_path}")
    else:
        print(f"Error saving visualize for {img_name}")

    # Phần disagree (giữ nguyên)
    is_agree = False
    if abs(len(boxes_yolo) - len(boxes_rtdetr)) <= 3:
        if len(boxes_yolo) == 0 and len(boxes_rtdetr) == 0:
            is_agree = True
        elif len(boxes_yolo) > 0 and len(boxes_rtdetr) > 0:
            iou_matrix = box_iou(boxes_yolo, boxes_rtdetr)
            max_iou, _ = iou_matrix.max(dim=1)
            mean_iou = max_iou.mean().item()
            if mean_iou > 0.4:
                is_agree = True

    if not is_agree:
        shutil.copy(img_path, os.path.join(original_disagree, img_name))
        # YOLO26 disagree
        yolo_label = os.path.join(yolo26_labels_dir, base_name + '.txt')
        if os.path.exists(yolo_label):
            shutil.copy(yolo_label, os.path.join(yolo26_disagree, base_name + '.txt'))
        # RT-DETR disagree
        rtdetr_label = os.path.join(rtdetr_labels_dir, base_name + '.txt')
        if os.path.exists(rtdetr_label):
            shutil.copy(rtdetr_label, os.path.join(rtdetr_disagree, base_name + '.txt'))
        # (Nếu muốn thêm visualize disagree, có thể plot tương tự, nhưng tạm bỏ để tiết kiệm)

print("\nHoàn tất!")
print(f"Dataset train: {final_pseudo_folder}")
print("  - visualized/ giờ sẽ có file như yolo26_...png hoặc rtdetr_...png với boxes vẽ sẵn")