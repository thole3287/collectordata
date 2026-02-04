
import os
import sys
# Add parent directory to path to import services
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.minio_service import get_minio_client

def list_buckets():
    try:
        client = get_minio_client()
        buckets = client.list_buckets()
        print("Existing buckets:")
        for bucket in buckets:
            print(f"- {bucket.name}")
    except Exception as e:
        print(f"Error listing buckets: {e}")

if __name__ == "__main__":
    list_buckets()
