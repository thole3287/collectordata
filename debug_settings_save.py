import requests
import json

url = 'http://localhost:5000/api/settings/'
headers = {'Content-Type': 'application/json'}

# Mimic the payload sent by frontend
payload = {
    "enabled_camera": False,
    "enabled_video": False,
    "profiles": {
        "day": {
            "mean_intensity": "",
            "clahe_clip_limit": 1.0,
            "gamma": 1.0,
            "denoise_strength": 0,
            "hue_shift": 0,
            "saturation_scale": 1.0,
            "contrast_scale": 1.0,
            "resize_640": False
        },
        "night": {
            "mean_intensity": "",
            "clahe_clip_limit": 1.0,
            "gamma": 1.2,
            "denoise_strength": 3.0,
            "hue_shift": 0,
            "saturation_scale": 1.0,
            "contrast_scale": 1.1,
            "resize_640": False
        },
        "rain": {
            "mean_intensity": "",
            "clahe_clip_limit": 2.0,
            "gamma": 1.0,
            "denoise_strength": 0,
            "hue_shift": 0,
            "saturation_scale": 1.1,
            "contrast_scale": 1.2,
            "resize_640": False
        }
    }
}

try:
    print(f"Sending POST to {url}...")
    response = requests.post(url, json=payload)
    print(f"Status Code: {response.status_code}")
    print("Response Content:")
    print(response.text)
except Exception as e:
    print(f"Error: {e}")
