import requests
import json
import os
from datetime import datetime

# Cấu hình endpoint (Chạy trên localhost đang active)
# Nếu bạn chưa bind port 5000, hãy kiểm tra lại file app.py hoặc docker-compose
URL = "http://localhost:5000/api/vehicle-detection/upload"

# Đường dẫn file ảnh mẫu (Dùng ảnh có sẵn trong static để test)
# Lưu ý: API hiện tại yêu cầu file phải NẰM TRÊN SERVER (Local Path)
SAMPLE_IMAGE = os.path.abspath("static/img/no-image.png")

if not os.path.exists(SAMPLE_IMAGE):
    print(f"⚠️ Không tìm thấy ảnh mẫu tại: {SAMPLE_IMAGE}")
    # Tạo ảnh giả dummy để test logic
    with open("test_dummy.jpg", "wb") as f:
        f.write(b"\x00" * 100) # Dummy bytes
    SAMPLE_IMAGE = os.path.abspath("test_dummy.jpg")
    print(f"✅ Đã tạo ảnh dummy: {SAMPLE_IMAGE}")

payload = {
    "event_id": f"evt_test_{int(datetime.now().timestamp())}",
    "camera_id": "CAM_TEST_01",
    "timestamp": datetime.now().isoformat(),
    "location": {
        "lat": 10.762622,
        "lng": 106.660172
    },
    "vehicle_type": "car",
    "license_plate": "51A-999.99",
    "color": "red",
    "confidence": 0.98,
    "full_frame_path": SAMPLE_IMAGE, # Quan trọng: Phải là đường dẫn local
    "cropped_vehicle_path": None,
    "cropped_plate_path": None
}

print(f"Dang gui request toi: {URL}")
print(f"Payload: {json.dumps(payload, indent=2)}")

try:
    response = requests.post(URL, json=payload)
    
    if response.status_code == 201:
        print("\nTHANH CONG! API da luu du lieu.")
        print("Response:", response.json())
        print("\nBay gio ban co the kiem tra MongoDB, collection 'vehicle_detections' da duoc tao.")
    else:
        print(f"\nTHAT BAI! Status Code: {response.status_code}")
        print("Error:", response.text)

except Exception as e:
    print(f"\nLOI KET NOI: {e}")
    print("Goi y: Hay dam bao Web Server (app.py) dang chay.")
