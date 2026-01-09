import os
import requests
import json
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv('PEXELS_API_KEY')
headers = {"Authorization": api_key}
video_id = 35124638
url = f"https://api.pexels.com/videos/videos/{video_id}"
response = requests.get(url, headers=headers)

with open('debug_output.json', 'w', encoding='utf-8') as f:
    f.write(response.text)
