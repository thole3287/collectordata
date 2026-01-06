import os
import logging
import time
from dotenv import load_dotenv
import services.pexels_service as pexels_service

# Load env
load_dotenv()

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def debug_pexels():
    keyword = "traffic"
    api_key = os.getenv('PEXELS_API_KEY')
    
    print(f"DEBUG: API Key present: {bool(api_key)}")
    if not api_key:
        print("ERROR: PEXELS_API_KEY not found in .env")
        return

    print(f"DEBUG: Starting download for keyword '{keyword}'...")
    try:
        # Request 1 video
        result = pexels_service.download_pexels_videos(keyword, num_videos=1, api_key=api_key)
        print(f"DEBUG: Result: {result}")
        if result.get('success'):
            print("SUCCESS: Pexels flow completed manually.")
        else:
            print("FAILURE: Pexels flow returned failure.")
            
    except Exception as e:
        print(f"DEBUG: Exception occurred: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    debug_pexels()
