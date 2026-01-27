import os
import shutil
import torch
import cv2
import numpy as np
from ultralytics import YOLO, RTDETR
from ultralytics.utils.metrics import box_iou

# Đường dẫn (đã dùng path bạn cung cấp trước)
images_folder = r"E:\phaogo\Master\DataMiningAI\images\test"
base_results_folder = r"E:\phaogo\Master\DataMiningAI\images\Vehicle_Detection_Image_Dataset\train\result_labels5"
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

print("Debug: Processing images...")

for res_yolo, res_rtdetr in zip(results_yolo26, results_rtdetr):
    img_path = res_yolo.path
    img_name = os.path.basename(img_path)
    base_name = img_name.rsplit('.', 1)[0]

    # Lấy boxes, conf, cls từ cả hai model
    boxes_yolo = res_yolo.boxes.xyxy if res_yolo.boxes is not None else torch.empty((0, 4), device='cpu')
    conf_yolo = res_yolo.boxes.conf if res_yolo.boxes is not None else torch.empty((0,), device='cpu')
    cls_yolo = res_yolo.boxes.cls if res_yolo.boxes is not None else torch.empty((0,), device='cpu')

    boxes_rtdetr = res_rtdetr.boxes.xyxy if res_rtdetr.boxes is not None else torch.empty((0, 4), device='cpu')
    conf_rtdetr = res_rtdetr.boxes.conf if res_rtdetr.boxes is not None else torch.empty((0,), device='cpu')
    cls_rtdetr = res_rtdetr.boxes.cls if res_rtdetr.boxes is not None else torch.empty((0,), device='cpu')

    # Merge boxes thủ công (không cần non_max_suppression import)
    if len(boxes_yolo) == 0 and len(boxes_rtdetr) == 0:
        merged_boxes = torch.empty((0, 4), device='cpu')
        merged_conf = torch.empty((0,), device='cpu')
        merged_cls = torch.empty((0,), device='cpu')
    else:
        # Kết hợp detections
        all_boxes = torch.cat([boxes_yolo, boxes_rtdetr], dim=0)
        all_conf = torch.cat([conf_yolo, conf_rtdetr], dim=0)
        all_cls = torch.cat([cls_yolo, cls_rtdetr], dim=0)

        # Simple NMS: sort by conf descending, loại trùng IoU > 0.45
        _, indices = torch.sort(all_conf, descending=True)
        keep = []
        while indices.numel() > 0:
            i = indices[0].item()
            keep.append(i)
            if indices.numel() == 1:
                break
            ovr = box_iou(all_boxes[i].unsqueeze(0), all_boxes[indices[1:]])[0]
            indices = indices[1:][ovr <= 0.45]  # loại nếu IoU > 0.45

        keep = torch.tensor(keep, device='cpu')
        merged_boxes = all_boxes[keep]
        merged_conf = all_conf[keep]
        merged_cls = all_cls[keep]

    # Tiếp tục tạo label.txt merged như cũ
    label_path = os.path.join(final_pseudo_folder, base_name + '.txt')
    with open(label_path, 'w') as f:
        for i in range(len(merged_boxes)):
            x1, y1, x2, y2 = merged_boxes[i]
            conf = merged_conf[i]
            cls = int(merged_cls[i])
            img = cv2.imread(img_path)
            h, w = img.shape[:2]
            cx = ((x1 + x2) / 2) / w
            cy = ((y1 + y2) / 2) / h
            bw = (x2 - x1) / w
            bh = (y2 - y1) / h
            f.write(f"{cls} {cx:.6f} {cy:.6f} {bw:.6f} {bh:.6f} {conf:.6f}\n")

    # Lưu hình gốc
    shutil.copy(img_path, os.path.join(final_pseudo_folder, img_name))

    # Visualize merged (tạo Results giả lập để plot)
    from ultralytics.engine.results import Results

    fake_results = Results(
        orig_img=cv2.imread(img_path),
        path=img_path,
        names=model_yolo26.names,  # dùng names từ YOLO26 (chung)
        boxes=torch.cat([merged_boxes, merged_conf.unsqueeze(1), merged_cls.unsqueeze(1)], dim=1) if len(
            merged_boxes) > 0 else None
    )
    annotated_img = fake_results.plot()
    vis_path = os.path.join(visualized_folder, f"merged_{img_name}")
    cv2.imwrite(vis_path, annotated_img)

    print(f"Ảnh {img_name}: Merged {len(merged_boxes)} boxes (YOLO: {len(boxes_yolo)}, RT-DETR: {len(boxes_rtdetr)})")

    # Phần disagree (tùy chọn: nếu chênh lệch lớn thì lưu để check)
    is_agree = False
    if abs(len(boxes_yolo) - len(boxes_rtdetr)) <= 5:  # nới lỏng hơn
        if len(boxes_yolo) == 0 and len(boxes_rtdetr) == 0:
            is_agree = True
        elif len(boxes_yolo) > 0 and len(boxes_rtdetr) > 0:
            iou_matrix = box_iou(boxes_yolo, boxes_rtdetr)
            max_iou, _ = iou_matrix.max(dim=1)
            mean_iou = max_iou.mean().item()
            if mean_iou > 0.35:
                is_agree = True

    if not is_agree:
        shutil.copy(img_path, os.path.join(original_disagree, img_name))
        # Copy label gốc từ hai model để so sánh
        yolo_label = os.path.join(yolo26_labels_dir, base_name + '.txt')
        if os.path.exists(yolo_label):
            shutil.copy(yolo_label, os.path.join(yolo26_disagree, base_name + '.txt'))
        rtdetr_label = os.path.join(rtdetr_labels_dir, base_name + '.txt')
        if os.path.exists(rtdetr_label):
            shutil.copy(rtdetr_label, os.path.join(rtdetr_disagree, base_name + '.txt'))

print("\nHoàn tất!")
print(f"Dataset merged pseudo-label (ensemble): {final_pseudo_folder}")
print("  - *.txt: label sau NMS từ cả hai model")
print("  - visualized/: merged_*.png với boxes sau ensemble")
print(f"Disagree (nếu chênh lệch lớn): {disagree_folder}")