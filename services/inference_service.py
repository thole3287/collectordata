import os
import cv2
import time
import traceback
import uuid
from datetime import datetime
from ultralytics import YOLO
import services.database as db_service

class InferenceService:
    def __init__(self, db=None):
        self.db = db if db is not None else db_service.get_db_connection()
        print("Loading YOLO model for Inference Service...")
        # Load the custom trained model
        self.model = YOLO("runs/detect/vehicle_yolo26_gpu7/weights/best.pt")
        self.classes = [0, 1, 2, 3, 4] # Vehicle classes: bicycle, car, motorcycle, bus, truck
        
        # Color Map (BGR format) for drawing
        self.color_map = {
            'bus': (0, 255, 255),          # Yellow
            'car': (255, 255, 0),          # Cyan
            'truck': (235, 10, 10),        # Deep Blue
            'motorcycle': (255, 255, 255), # White
            'bicycle': (200, 200, 200)     # Light Gray
        }

    def _update_job_status(self, job_id, status, error_msg=None, output_url=None,
                           progress=0, counts=None, preview_url=None,
                           processing_fps=None, gallery_snapshots=None,
                           frame_count=None, video_fps=None, total_frames=None):
        if self.db is None:
            return
        
        update_data = {
            "status": status,
            "progress": progress,
            "updated_at": datetime.now()
        }
        if error_msg:
            update_data["error"] = error_msg
        if output_url:
            update_data["output_url"] = output_url
        if counts is not None:
            update_data["counts"] = counts
        if preview_url is not None:
            update_data["preview_url"] = preview_url
        if processing_fps is not None:
            update_data["processing_fps"] = processing_fps
        if gallery_snapshots is not None:
            update_data["gallery_snapshots"] = gallery_snapshots
        if frame_count is not None:
            update_data["frame_count"] = frame_count
        if video_fps is not None:
            update_data["video_fps"] = video_fps
        if total_frames is not None:
            update_data["total_frames"] = total_frames
            
        self.db['inference_jobs'].update_one(
            {"job_id": job_id},
            {"$set": update_data}
        )

    def _save_traffic_stats(self, job_id, counts, total_frames, video_fps):
        """Lưu kết quả thống kê lưu lượng xe vào collection traffic_stats."""
        if self.db is None:
            return
        try:
            job = self.db['inference_jobs'].find_one({"job_id": job_id})
            if not job:
                return

            total_vehicles = sum(counts.values()) if counts else 0
            video_duration = round(total_frames / video_fps, 2) if video_fps > 0 else 0

            stats_doc = {
                "job_id":            job_id,
                "camera_id":         job.get("camera_id", "CAM_UNKNOWN"),
                "camera_name":       job.get("camera_name", "Không rõ"),
                "location":          job.get("location", "Không rõ"),
                "record_date":       job.get("record_date", datetime.now()),
                "original_filename": job.get("original_filename", ""),
                "video_duration_seconds": video_duration,
                "total_frames":      total_frames,
                "video_fps":         video_fps,
                "counts": {
                    "car":        counts.get("car", 0),
                    "motorcycle": counts.get("motorcycle", 0),
                    "bus":        counts.get("bus", 0),
                    "truck":      counts.get("truck", 0),
                    "bicycle":    counts.get("bicycle", 0),
                },
                "total_vehicles": total_vehicles,
                "output_url":     job.get("output_url"),
                "processed_at":   datetime.now(),
            }
            self.db['traffic_stats'].insert_one(stats_doc)
            print(f"[InferenceService] Traffic stats saved for job {job_id}: {total_vehicles} vehicles total.")
        except Exception as e:
            print(f"[InferenceService] Failed to save traffic stats: {e}")

    def _save_incremental_traffic_stats(self, job, job_id, incremental_counts, current_record_date):
        """Lưu kết quả nhồi theo lô 30 frames để vẽ Real-time chart & áp dụng giãn thời gian 60x"""
        if self.db is None or sum(incremental_counts.values()) == 0:
            return
        
        try:
            total_vehicles = sum(incremental_counts.values())
            stats_doc = {
                "job_id":            job_id,
                "camera_id":         job.get("camera_id", "CAM_UNKNOWN"),
                "camera_name":       job.get("camera_name", "Không rõ"),
                "location":          job.get("location", "Không rõ"),
                "record_date":       current_record_date,
                "original_filename": job.get("original_filename", ""),
                "total_vehicles":    total_vehicles,
                "counts": {
                    "car":        incremental_counts.get("car", 0),
                    "motorcycle": incremental_counts.get("motorcycle", 0),
                    "bus":        incremental_counts.get("bus", 0),
                    "truck":      incremental_counts.get("truck", 0),
                    "bicycle":    incremental_counts.get("bicycle", 0),
                },
                "incremental_batch": True,
                "processed_at":      datetime.now()
            }
            self.db['traffic_stats'].insert_one(stats_doc)
        except Exception as e:
            print(f"[InferenceService] Failed to save incremental stats: {e}")

    def process_video(self, job_id, input_path, output_dir):
        """
        Processes a single video, draws bounding boxes, and saves the output video.
        Updates MongoDB 'inference_jobs' collection with status & live preview.
        """
        self._update_job_status(job_id, status="processing", progress=0)
        
        if not os.path.exists(input_path):
            self._update_job_status(job_id, status="failed", error_msg="Input video file not found")
            return
            
        os.makedirs(output_dir, exist_ok=True)
        filename = os.path.basename(input_path)
        name, ext = os.path.splitext(filename)
        output_filename = f"{name}_inferred{ext}"
        output_path = os.path.join(output_dir, output_filename)
        
        # Build output URL
        try:
            static_idx = output_dir.index('static')
            output_url = "/" + output_dir[static_idx:].replace('\\', '/') + "/" + output_filename
        except ValueError:
            output_url = f"/static/inference_results/output/{output_filename}"

        # ── Preview / Snapshot dir ────────────────────────────────────────────
        preview_dir  = os.path.join(os.getcwd(), 'static', 'inference_results', 'previews', job_id)
        os.makedirs(preview_dir, exist_ok=True)
        preview_path = os.path.join(preview_dir, "preview.jpg")
        preview_url  = f"/static/inference_results/previews/{job_id}/preview.jpg"
        gallery_snapshots = []
        last_milestone    = -1
        # ─────────────────────────────────────────────────────────────────────

        try:
            cap = cv2.VideoCapture(input_path)
            if not cap.isOpened():
                raise Exception("Cannot open video stream")

            width        = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height       = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            fps          = cap.get(cv2.CAP_PROP_FPS)
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            
            if total_frames <= 0:
                total_frames = 1  # Prevent div by zero

            # Write video_fps and total_frames to DB right away
            self._update_job_status(job_id, status="processing", progress=0,
                                    video_fps=round(fps, 2), total_frames=total_frames)

            # Retrieve job params for counting
            job = None
            enable_counting = False
            line_y = int(height / 2)
            
            if self.db is not None:
                job = self.db['inference_jobs'].find_one({"job_id": job_id})
                if job:
                    enable_counting = job.get("enable_counting", False)
                    if job.get("line_y") is not None:
                        line_y = job.get("line_y")

            # Counting state
            tracked_objects = {}   # id -> last_y
            counted_ids     = set()
            counts          = {cls: 0 for cls in self.color_map.keys()}

            # Setup VideoWriter
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            out    = cv2.VideoWriter(output_path, fourcc, fps, (width, height))

            frame_count        = 0
            processing_fps     = 0.0
            batch_start_time   = time.time()
            
            last_saved_counts = {cls: 0 for cls in self.color_map.keys()}
            start_record_date = None
            if job and job.get("record_date"):
                dt_val = job["record_date"]
                if isinstance(dt_val, str):
                    from dateutil.parser import parse
                    try:
                        start_record_date = parse(dt_val)
                    except:
                        pass
                else:
                    start_record_date = dt_val
            if not start_record_date:
                start_record_date = datetime.now()

            while True:
                ret, frame = cap.read()
                if not ret:
                    break
                
                # ── Inference ────────────────────────────────────────────────
                if enable_counting:
                    results = self.model.track(frame, conf=0.25, iou=0.45,
                                               classes=self.classes, persist=True, verbose=False)
                else:    
                    results = self.model.predict(frame, conf=0.25, iou=0.45,
                                                 classes=self.classes, verbose=False)
                res = results[0]
                
                # ── Draw boxes ───────────────────────────────────────────────
                if res.boxes is not None and len(res.boxes) > 0:
                    ids = res.boxes.id.cpu().numpy().astype(int) if res.boxes.id is not None else None
                    
                    for i, box in enumerate(res.boxes):
                        x1, y1, x2, y2 = map(int, box.xyxy[0])
                        conf    = float(box.conf[0])
                        cls_id  = int(box.cls[0])
                        cls_name = self.model.names.get(cls_id, str(cls_id)).lower()
                        
                        color   = self.color_map.get(cls_name, (0, 255, 0))
                        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
                        
                        obj_id = ids[i] if ids is not None else None
                        label  = f"{cls_name} {conf:.2f}"
                        if obj_id is not None:
                            label = f"#{obj_id} {label}"
                            
                        t_size = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)[0]
                        cv2.rectangle(frame, (x1, y1 - t_size[1] - 3), (x1 + t_size[0], y1), color, -1)
                        cv2.putText(frame, label, (x1, y1 - 2),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1, cv2.LINE_AA)
                        
                        # Counting Logic
                        if enable_counting and obj_id is not None:
                            cy = int((y1 + y2) / 2)
                            if obj_id in tracked_objects:
                                last_y = tracked_objects[obj_id]
                                if (last_y <= line_y < cy) or (last_y >= line_y > cy):
                                    if obj_id not in counted_ids:
                                        counts[cls_name] = counts.get(cls_name, 0) + 1
                                        counted_ids.add(obj_id)
                            tracked_objects[obj_id] = cy

                # ── Draw counting overlay ────────────────────────────────────
                if enable_counting:
                    cv2.line(frame, (0, line_y), (width, line_y), (0, 0, 255), 2)
                    cv2.putText(frame, "COUNT LINE", (10, line_y - 10),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
                    y_offset = 30
                    cv2.rectangle(frame, (10, 10), (250, 40 + len(counts) * 25), (0, 0, 0), -1)
                    cv2.putText(frame, "Vehicle Counters:", (20, y_offset),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
                    for c_name, c_val in counts.items():
                        if c_val > 0:
                            y_offset += 25
                            c_color = self.color_map.get(c_name, (200, 200, 200))
                            cv2.putText(frame, f"{c_name.capitalize()}: {c_val}", (20, y_offset),
                                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, c_color, 2)

                out.write(frame)
                frame_count += 1

                # ── Lưu preview MỖI FRAME để MJPEG Stream đọc ────────
                _, jpeg = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
                jpeg_bytes = jpeg.tobytes()
                
                temp_path = preview_path + ".tmp"
                with open(temp_path, 'wb') as f:
                    f.write(jpeg_bytes)
                # Dùng os.replace để ghi đè nguyên tử (atomic), giúp file không bị lỗi khi Flask đọc
                os.replace(temp_path, preview_path)

                # ── Cập nhật DB + FPS mỗi 30 frame (tránh overload MongoDB) ─
                if frame_count % 30 == 0:
                    elapsed = time.time() - batch_start_time
                    processing_fps   = round(30 / elapsed, 1) if elapsed > 0 else 0.0
                    batch_start_time = time.time()

                    progress = int((frame_count / total_frames) * 100)

                    # Save snapshot at 10% milestones
                    milestone = progress // 10
                    if milestone > last_milestone and milestone > 0:
                        snap_filename = f"snap_{milestone:02d}.jpg"
                        snap_path     = os.path.join(preview_dir, snap_filename)
                        with open(snap_path, 'wb') as f:
                            f.write(jpeg_bytes)
                        snap_url = f"/static/inference_results/previews/{job_id}/{snap_filename}"
                        gallery_snapshots.append(snap_url)
                        last_milestone = milestone

                    self._update_job_status(
                        job_id, status="processing", progress=progress,
                        preview_url=preview_url,
                        processing_fps=processing_fps,
                        gallery_snapshots=gallery_snapshots,
                        frame_count=frame_count,
                    )

                    # Lưu DB ngắt quãng để Chart có số liệu Real-time (với Thời gian giãn 60x)
                    if enable_counting:
                        incremental = {k: counts.get(k, 0) - last_saved_counts.get(k, 0) for k in self.color_map}
                        if sum(incremental.values()) > 0:
                            from datetime import timedelta
                            current_recorded_seconds = (frame_count / fps) * 60
                            current_record_date = start_record_date + timedelta(seconds=int(current_recorded_seconds))
                            
                            self._save_incremental_traffic_stats(job, job_id, incremental, current_record_date)
                            
                            for k in last_saved_counts:
                                last_saved_counts[k] = counts.get(k, 0)
                # ─────────────────────────────────────────────────────────────


            cap.release()
            out.release()
            
            # Convert to H264 if ffmpeg available
            try:
                h264_output_path = output_path.replace(".mp4", "_h264.mp4")
                if os.system("ffmpeg -version >nul 2>&1") == 0 or os.system("ffmpeg -version >/dev/null 2>&1") == 0:
                    os.system(f'ffmpeg -y -i "{output_path}" -vcodec libx264 -acodec aac "{h264_output_path}"')
                    if os.path.exists(h264_output_path):
                        os.remove(output_path)
                        output_path = h264_output_path
                        output_url  = output_url.replace(".mp4", "_h264.mp4")
            except Exception as e:
                print(f"H264 conversion skipped: {e}")

            # Mark completed
            final_counts = counts if enable_counting else {}
            self._update_job_status(
                job_id, status="completed", progress=100,
                output_url=output_url, counts=final_counts,
                processing_fps=processing_fps,
                gallery_snapshots=gallery_snapshots,
                frame_count=frame_count,
            )

            # Save traffic statistics to DB (Final Summary)
            if enable_counting:
                # Lưu mẻ cuối cùng nếu còn sót
                incremental = {k: counts.get(k, 0) - last_saved_counts.get(k, 0) for k in self.color_map}
                if sum(incremental.values()) > 0:
                    from datetime import timedelta
                    current_recorded_seconds = (frame_count / fps) * 60
                    current_record_date = start_record_date + timedelta(seconds=int(current_recorded_seconds))
                    self._save_incremental_traffic_stats(job, job_id, incremental, current_record_date)
            
            # Luôn lưu 1 bản ghi Final (không phải incremental) để hiện vào History
            self._save_traffic_stats(job_id, final_counts, total_frames, fps)

            print(f"Inference complete: {output_path}")

        except Exception as e:
            error_trace = traceback.format_exc()
            print(f"Error processing video {input_path}: {error_trace}")
            self._update_job_status(job_id, status="failed", error_msg=str(e))
