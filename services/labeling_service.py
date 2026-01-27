
import os
import cv2
import numpy as np
import torch
from ultralytics import YOLO, RTDETR
from ultralytics.utils.metrics import box_iou
from datetime import datetime
import tempfile
import shutil

# Import references from existing services if needed
# But for standalone running, we might need to be careful with imports
try:
    from services.minio_service import (
        get_minio_client, MINIO_BUCKET_FRAMES, 
        upload_and_get_key, generate_storage_path
    )
except ImportError:
    # If run as standalone script from root without module context
    from minio_service import get_minio_client, MINIO_BUCKET_FRAMES

class LabelingService:
    def __init__(self, db=None):
        self.db = db
        self.minio_client = get_minio_client()
        self.bucket_frames = MINIO_BUCKET_FRAMES
        
        # Load Models (Lazy loading or immediate?)
        print("Loading models for labeling service...")
        # Dùng đúng model YOLO26 như pipeline gốc
        self.model_yolo = YOLO("yolo26n.pt")
        self.model_rtdetr = RTDETR("rtdetr-l.pt")
        self.classes = [1, 2, 3, 5, 7] # Vehicle classes of interest
        
        # Mappings for stats
        self.class_names = self.model_yolo.names

    def _determine_winner(self, res_yolo, res_rtdetr):
        """
        Chọn model thắng dựa trên mean confidence (giống logic test script).
        Trả về dict: { 'model_name': 'yolo26'|'rtdetr', 'result': <ultralytics Results> }
        """
        conf_yolo = res_yolo.boxes.conf if res_yolo.boxes is not None and len(res_yolo.boxes) else torch.tensor([])
        conf_rtdetr = res_rtdetr.boxes.conf if res_rtdetr.boxes is not None and len(res_rtdetr.boxes) else torch.tensor([])
        
        mean_y = conf_yolo.mean().item() if len(conf_yolo) else 0.0
        mean_r = conf_rtdetr.mean().item() if len(conf_rtdetr) else 0.0
        
        if mean_y > mean_r:
            return {"model_name": "yolo26", "result": res_yolo}
        else:
            return {"model_name": "rtdetr", "result": res_rtdetr}

    def _extract_boxes_conf_cls(self, res):
        """
        Helper: lấy boxes (xyxy), conf, cls dưới dạng tensor CPU, tránh lỗi device khi concat.
        """
        if res.boxes is None or len(res.boxes) == 0:
            return (
                torch.empty((0, 4), device="cpu"),
                torch.empty((0,), device="cpu"),
                torch.empty((0,), device="cpu"),
            )
        b = res.boxes
        return b.xyxy.cpu(), b.conf.cpu(), b.cls.cpu()

    def _merge_detections(self, res_yolo, res_rtdetr, img_w, img_h, iou_thresh=0.45):
        """
        Ensemble YOLO26 + RT-DETR giống script YOLO_RT_DETR_Merge.py:
        - Gộp boxes hai model
        - NMS đơn giản theo confidence và IoU
        Trả về merged_boxes (xyxy), merged_conf, merged_cls, cùng nhãn string cho từng cls.
        """
        boxes_yolo, conf_yolo, cls_yolo = self._extract_boxes_conf_cls(res_yolo)
        boxes_rtdetr, conf_rtdetr, cls_rtdetr = self._extract_boxes_conf_cls(res_rtdetr)

        if len(boxes_yolo) == 0 and len(boxes_rtdetr) == 0:
            merged_boxes = torch.empty((0, 4), device="cpu")
            merged_conf = torch.empty((0,), device="cpu")
            merged_cls = torch.empty((0,), device="cpu")
        else:
            all_boxes = torch.cat([boxes_yolo, boxes_rtdetr], dim=0)
            all_conf = torch.cat([conf_yolo, conf_rtdetr], dim=0)
            all_cls = torch.cat([cls_yolo, cls_rtdetr], dim=0)

            # NMS thủ công: sort theo conf, loại box trùng nếu IoU > iou_thresh
            _, indices = torch.sort(all_conf, descending=True)
            keep = []
            while indices.numel() > 0:
                i = indices[0].item()
                keep.append(i)
                if indices.numel() == 1:
                    break
                ovr = box_iou(all_boxes[i].unsqueeze(0), all_boxes[indices[1:]])[0]
                indices = indices[1:][ovr <= iou_thresh]

            keep = torch.tensor(keep, device="cpu", dtype=torch.long)
            merged_boxes = all_boxes[keep]
            merged_conf = all_conf[keep]
            merged_cls = all_cls[keep]

        # Chuẩn bị dạng normalized xywh + tên lớp để sử dụng chung cho label + DB
        detections = []
        label_summary = {}
        for i in range(len(merged_boxes)):
            x1, y1, x2, y2 = merged_boxes[i]
            conf = float(merged_conf[i].item())
            cls_id = int(merged_cls[i].item())
            cls_name = self.class_names.get(cls_id, str(cls_id))

            cx = float(((x1 + x2) / 2) / img_w)
            cy = float(((y1 + y2) / 2) / img_h)
            bw = float((x2 - x1) / img_w)
            bh = float((y2 - y1) / img_h)

            label_summary[cls_name] = label_summary.get(cls_name, 0) + 1
            detections.append(
                {
                    "cls": cls_id,
                    "label": cls_name,
                    "conf": conf,
                    "bbox": [cx, cy, bw, bh],
                    "xyxy": [float(x1), float(y1), float(x2), float(y2)],
                }
            )

        return {
            "boxes": merged_boxes,
            "confs": merged_conf,
            "clses": merged_cls,
            "label_summary": label_summary,
            "detections": detections,
        }

    def _draw_merged_boxes(self, img, merged_result, color=(0, 255, 0)):
        """
        Vẽ bounding boxes merged trực tiếp bằng OpenCV để tạo ảnh visualize.
        """
        vis_img = img.copy()
        for det in merged_result["detections"]:
            x1, y1, x2, y2 = det["xyxy"]
            cls_name = det["label"]
            conf = det["conf"]
            pt1 = (int(x1), int(y1))
            pt2 = (int(x2), int(y2))
            cv2.rectangle(vis_img, pt1, pt2, color, 2)
            label = f"{cls_name} {conf:.2f}"
            cv2.putText(
                vis_img,
                label,
                (pt1[0], max(0, pt1[1] - 5)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                color,
                1,
                cv2.LINE_AA,
            )
        return vis_img

    def process_single_image(self, object_name, bucket_name=None):
        """
        Download -> Predict -> Save Winner -> Update DB
        """
        if not bucket_name:
            bucket_name = self.bucket_frames

        # 1. Download
        try:
            response = self.minio_client.get_object(bucket_name, object_name)
            file_bytes = np.asarray(bytearray(response.read()), dtype=np.uint8)
            response.close()
            img = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)
            if img is None:
                return {"success": False, "error": "Decode failed"}
        except Exception as e:
            return {"success": False, "error": f"Download failed: {e}"}

        # 2. Inference
        try:
            res_yolo = self.model_yolo.predict(img, conf=0.25, iou=0.45, imgsz=640, classes=self.classes, verbose=False)[0]
            res_rtdetr = self.model_rtdetr.predict(img, conf=0.25, iou=0.45, imgsz=640, classes=self.classes, verbose=False)[0]
        except Exception as e:
            return {"success": False, "error": f"Inference failed: {e}"}

        # 3. Determine Winner (dùng cho stats), nhưng LABEL sẽ dùng ensemble merged
        winner_data = self._determine_winner(res_yolo, res_rtdetr)
        winner_name = winner_data['model_name']

        # 4. Merge detections từ cả hai model (ensemble)
        h, w = img.shape[:2]
        merged_result = self._merge_detections(res_yolo, res_rtdetr, w, h)
        
        # 5. Generate Artifacts (Visualized Image & Label Txt) từ merged_result
        
        # Prepare paths
        # object_name ex: camera/2026/.../fr001.png
        # We want: 
        #   visualized: dataset/visualized/camera/.../fr001.jpg
        #   labels: dataset/labels/camera/.../fr001.txt
        
        base_name = os.path.splitext(object_name)[0]
        ext = os.path.splitext(object_name)[1]
        
        # Adjust path if it starts with 'dataset/' or similar? 
        # Assuming object_name is relative to bucket root (e.g. 'camera/...')
        
        vis_key = f"visualized/{base_name}.jpg" # Monitor: visualized/camera/...
        lbl_key = f"labels/{base_name}.txt"
        
        # Upload Visualized (vẽ từ merged boxes)
        vis_img = self._draw_merged_boxes(img, merged_result)
        _, vis_encoded = cv2.imencode(".jpg", vis_img)
        vis_bytes = vis_encoded.tobytes()
        
        try:
            from io import BytesIO
            self.minio_client.put_object(
                bucket_name, vis_key, BytesIO(vis_bytes), len(vis_bytes), content_type="image/jpeg"
            )
        except Exception as e:
            print(f"Failed upload vis: {e}")

        # Upload Label Txt (YOLO format từ merged detections)
        lines = []
        for det in merged_result["detections"]:
            cls = det["cls"]
            x, y, bw, bh = det["bbox"]
            conf = det["conf"]
            lines.append(f"{cls} {x:.6f} {y:.6f} {bw:.6f} {bh:.6f} {conf:.6f}")
        txt_content = "\n".join(lines)
        try:
            self.minio_client.put_object(
                bucket_name, lbl_key, BytesIO(txt_content.encode('utf-8')), len(txt_content), content_type="text/plain"
            )
        except Exception as e:
            print(f"Failed upload txt: {e}")
            
        # 6. Result Summary for DB (từ merged detections)
        label_summary = merged_result["label_summary"]
        detections_list = [
            {
                "cls": det["cls"],
                "label": det["label"],
                "conf": det["conf"],
                "bbox": det["bbox"],
            }
            for det in merged_result["detections"]
        ]
        # 6. Update DB (ghi label_status, winner_model, detections,... để dataset gallery đọc được)
        if self.db is not None:
            self._update_db(object_name, winner_name, label_summary, detections_list, vis_key, lbl_key)

        # Trả summary cho caller (batch script) dùng nếu cần
        return {
            "success": True,
            "winner": winner_name,
            "counts": label_summary,
            "detections": detections_list,
            "storage_refs": {
                "visualized_key": vis_key,
                "label_key": lbl_key
            },
            "original_key": object_name
        }

    def _update_db(self, object_name, winner, summary, detections, vis_key, lbl_key):
        """
        Update video_frames document based on 'storage_refs.key' or similar
        """
        try:
            print(f"[LabelingService] _update_db for key='{object_name}', winner={winner}, dets={len(detections)}")
            # We stored 'storage_refs.key' as the object_name in DB
            # Need to find the document that matches this frame.
            # Usually stored in 'video_frames' with 'storage_refs.key' == object_name
            
            # Note: object_name is relative key (camera/.../fr.png)
            
            collection = self.db['video_frames']
            
            update_data = {
                "label_status": "labeled",
                "winner_model": winner,
                "label_summary": summary,
                "detections": detections, # Array of detailed boxes
                "storage_refs.visualized_key": vis_key,
                "storage_refs.label_key": lbl_key,
                "updated_at": datetime.now()
            }
            
            result = collection.update_one(
                {"storage_refs.key": object_name},
                {"$set": update_data}
            )
            
            if result.matched_count == 0:
                # Try camera_images collection
                cam_collection = self.db['camera_images']
                # camera_images might use 'storage_refs.key' or just constructed path?
                # Based on get_frames_service, it has storage_refs.
                res_cam = cam_collection.update_one(
                    {"storage_refs.key": object_name},
                    {"$set": update_data}
                )
                if res_cam.matched_count == 0:
                    # Không tìm thấy frame gốc -> tạo document tối thiểu để Dataset Gallery vẫn có stats
                    try:
                        # Suy ra platform / scene_type từ object_name: platform/scene/.../file.png
                        parts = object_name.split('/')
                        platform = parts[0] if len(parts) > 0 else 'unknown'
                        scene_type = parts[1] if len(parts) > 1 else 'day'

                        minimal_doc = {
                            "platform": platform,
                            "scene_type": scene_type,
                            "weather": scene_type,
                            "label_status": "labeled",
                            "winner_model": winner,
                            "label_summary": summary,
                            "detections": detections,
                            "storage_refs": {
                                "bucket": self.bucket_frames,
                                "key": object_name,
                                "visualized_key": vis_key,
                                "label_key": lbl_key,
                            },
                            "created_at": datetime.now(),
                            "updated_at": datetime.now(),
                        }
                        collection.insert_one(minimal_doc)
                        print(f"ℹ️  Inserted minimal labeled doc for key '{object_name}'")
                    except Exception as inner_e:
                        print(f"⚠️  DB Insert Fallback Failed for key '{object_name}': {inner_e}")
            else:
                # Found in video_frames, good.
                pass
                
        except Exception as e:
            print(f"DB Update failed: {e}")

    def _generate_yolo_txt(self, results):
        out = []
        if results.boxes:
            for box in results.boxes:
                cls = int(box.cls[0].item())
                x, y, w, h = box.xywhn[0].tolist()
                conf = box.conf[0].item()
                out.append(f"{cls} {x:.6f} {y:.6f} {w:.6f} {h:.6f} {conf:.6f}")
        return "\n".join(out)
