import requests
import os
import time

# --- CẤU HÌNH ---
# 1. Dán API Key bạn vừa xin được vào đây
API_KEY = "XgQsJsFgBorp7TstDSW208jrPfvEgvVp7xP5RwpLdyWqBEyrxrTNTsG6"

# 2. Từ khóa tìm kiếm (Tiếng Anh sẽ nhiều kết quả hơn)
# Gợi ý: "traffic", "street cctv", "highway", "vehicles", "ho chi minh city"
QUERY = "traffic"

# 3. Số lượng video muốn tải
NUM_VIDEOS = 10

# 4. Thư mục lưu
OUTPUT_FOLDER = "pexels_traffic_dataset"

# 5. Cố gắng tìm video có chiều ngang gần với số này nhất (HD 720p)
TARGET_WIDTH = 1280


def download_pexels_videos():
    if API_KEY == "DÁN_API_KEY_CỦA_BẠN_VÀO_ĐÂY":
        print("❌ LỖI: Bạn chưa điền API Key!")
        return

    if not os.path.exists(OUTPUT_FOLDER):
        os.makedirs(OUTPUT_FOLDER)

    print(f"--- 🚀 Đang tìm '{QUERY}' trên Pexels... ---")

    headers = {
        "Authorization": API_KEY
    }

    # Gọi API tìm kiếm video
    # Pexels cho tìm tối đa 80 video mỗi trang
    url = f"https://api.pexels.com/videos/search?query={QUERY}&per_page={NUM_VIDEOS}&orientation=landscape"

    try:
        response = requests.get(url, headers=headers)
        if response.status_code != 200:
            print(f"❌ Lỗi kết nối API: {response.status_code}")
            return

        data = response.json()
        videos = data.get("videos", [])

        print(f"✅ Tìm thấy {len(videos)} video. Bắt đầu lọc và tải...")

        count = 0
        for video in videos:
            video_id = video["id"]
            video_files = video["video_files"]

            # --- THUẬT TOÁN CHỌN ĐỘ PHÂN GIẢI ---
            # Pexels trả về nhiều bản (SD, HD, 4K). Ta chọn bản gần 1280px nhất.
            best_link = None
            min_diff = 99999

            for v_file in video_files:
                width = v_file["width"]
                # Tính độ lệch so với 1280
                diff = abs(width - TARGET_WIDTH)

                if diff < min_diff:
                    min_diff = diff
                    best_link = v_file["link"]

            if best_link:
                print(f"  ⬇️ Đang tải Video ID {video_id} (Gần chuẩn HD)...")

                # Tải file về
                vid_content = requests.get(best_link).content

                filename = os.path.join(OUTPUT_FOLDER, f"pexels_{QUERY}_{video_id}.mp4")
                with open(filename, "wb") as f:
                    f.write(vid_content)

                count += 1
                print(f"     -> Xong: {filename}")
                time.sleep(1)  # Nghỉ xíu để không bị chặn
            else:
                print(f"  ⚠️ Bỏ qua ID {video_id} (Không tìm thấy link tải)")

        print("-" * 30)
        print(f"🎉 Hoàn tất! Đã tải {count} video vào thư mục '{OUTPUT_FOLDER}'.")

    except Exception as e:
        print(f"❌ Có lỗi xảy ra: {e}")


if __name__ == "__main__":
    download_pexels_videos()