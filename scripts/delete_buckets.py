
import os
import sys
# Add parent directory to path to import services
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.minio_service import get_minio_client
from minio.deleteobjects import DeleteObject

def delete_bucket_recursive(bucket_name):
    client = get_minio_client()
    
    if not client.bucket_exists(bucket_name):
        print(f"Bucket '{bucket_name}' does not exist.")
        return

    print(f"Emptying bucket '{bucket_name}'...")
    try:
        # List all objects
        objects = client.list_objects(bucket_name, recursive=True)
        # DeleteObject wrapper is needed for remove_objects
        delete_list = [DeleteObject(obj.object_name) for obj in objects]
        
        if delete_list:
            errors = client.remove_objects(bucket_name, delete_list)
            for error in errors:
                print(f"Error deleting object {error}")
        
        # Check if bucket is empty (sometimes versioned buckets need more work, but assuming standard)
        # Now remove the bucket
        client.remove_bucket(bucket_name)
        print(f"Bucket '{bucket_name}' deleted successfully.")
        
    except Exception as e:
        print(f"Error deleting bucket '{bucket_name}': {e}")

if __name__ == "__main__":
    buckets_to_delete = [
        "camera-images",
        "frames",
        "images",
        "test-bucket",
        "vehicle-detection" 
    ]
    # Note: User typed 'vehicle-detecction' but existing bucket is 'vehicle-detection'.
    
    print("Starting deletion process...")
    for bucket in buckets_to_delete:
        delete_bucket_recursive(bucket)
    print("Done.")
