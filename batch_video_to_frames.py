import cv2
import os
import glob

# --- CẤU HÌNH ---
# 1. Thư mục chứa các video đầu vào
INPUT_FOLDER = "pexels_traffic_dataset"

# 2. Thư mục tổng chứa ảnh đầu ra
OUTPUT_ROOT = "dataset_extracted"

# 3. Cứ bao nhiêu frame lấy 1 ảnh (30 frame ~ 1 giây)
FRAME_STEP = 30

# 4. Kích thước ảnh chuẩn (HD 720p)
TARGET_WIDTH = 1280
TARGET_HEIGHT = 720

# Các đuôi file video hỗ trợ
VALID_EXTENSIONS = ('.mp4', '.avi', '.mov', '.mkv', '.wmv')


def process_batch():
    # Kiểm tra thư mục đầu vào
    if not os.path.exists(INPUT_FOLDER):
        print(f"❌ Lỗi: Không tìm thấy thư mục '{INPUT_FOLDER}'. Hãy tạo nó và bỏ video vào.")
        return

    # Lấy danh sách tất cả file trong thư mục
    files = os.listdir(INPUT_FOLDER)
    video_files = [f for f in files if f.lower().endswith(VALID_EXTENSIONS)]

    if not video_files:
        print(f"⚠️ Không tìm thấy video nào trong '{INPUT_FOLDER}'.")
        return

    print(f"--- 🚀 TÌM THẤY {len(video_files)} VIDEO. BẮT ĐẦU XỬ LÝ... ---")

    for idx, video_file in enumerate(video_files):
        # Đường dẫn đầy đủ của video
        video_path = os.path.join(INPUT_FOLDER, video_file)

        # Tách tên video (bỏ đuôi .mp4) để làm tên folder
        video_name = os.path.splitext(video_file)[0]

        # Tạo folder con tương ứng
        current_output_dir = os.path.join(OUTPUT_ROOT, video_name)
        if not os.path.exists(current_output_dir):
            os.makedirs(current_output_dir)

        print(f"\n[{idx + 1}/{len(video_files)}] 🎬 Đang xử lý: {video_file}")
        print(f"   📂 Lưu vào: {current_output_dir}")

        # --- BẮT ĐẦU CẮT ẢNH CHO VIDEO NÀY ---
        extract_frames_single_video(video_path, current_output_dir, video_name)


def extract_frames_single_video(video_path, save_dir, prefix_name):
    cap = cv2.VideoCapture(video_path)

    if not cap.isOpened():
        print(f"   ❌ Lỗi: Không mở được video này.")
        return

    count = 0
    saved_count = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        # Chỉ xử lý frame theo bước nhảy (Step)
        if count % FRAME_STEP == 0:
            try:
                # Resize về chuẩn 720p
                resized_frame = cv2.resize(frame, (TARGET_WIDTH, TARGET_HEIGHT), interpolation=cv2.INTER_AREA)

                # Đặt tên file: TenVideo_Frame001.jpg
                filename = f"{prefix_name}_fr{saved_count:05d}.jpg"
                save_path = os.path.join(save_dir, filename)

                cv2.imwrite(save_path, resized_frame)
                saved_count += 1

                # In dấu chấm (.) để biểu thị đang chạy (cho đỡ sốt ruột)
                if saved_count % 20 == 0:
                    print(".", end="", flush=True)
            except Exception as e:
                print(f"Err: {e}")

        count += 1

    cap.release()
    print(f"\n   ✅ Xong video này. Đã lưu {saved_count} ảnh.")


if __name__ == "__main__":
    process_batch()