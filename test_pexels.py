import os
import requests
from dotenv import load_dotenv

def test_pexels():
    load_dotenv()
    api_key = os.getenv('PEXELS_API_KEY')
    
    print(f"Checking PEXELS_API_KEY...")
    if not api_key:
        print("❌ Error: PEXELS_API_KEY not found in environment variables.")
        return
    
    print(f"API Key present (length: {len(api_key)})")
    
    url = "https://api.pexels.com/videos/search?query=traffic&per_page=1"
    headers = {"Authorization": api_key}
    
    print(f"Testing connectivity to {url}...")
    try:
        response = requests.get(url, headers=headers, timeout=10)
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            videos = data.get('videos', [])
            print(f"✅ Success! Found {len(videos)} videos.")
            if videos:
                print(f"First video: {videos[0].get('url')}")
        elif response.status_code == 401:
            print("❌ Error: Unauthorized. Invalid API Key.")
        elif response.status_code == 429:
            print("❌ Error: Rate limit exceeded.")
        else:
            print(f"❌ Error: Unexpected status code {response.status_code}")
            print(response.text)
            
    except Exception as e:
        print(f"❌ Exception during request: {e}")

if __name__ == "__main__":
    test_pexels()
