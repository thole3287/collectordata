try:
    print("Attempting to import camera_collector...")
    import camera_collector
    print("Successfully imported camera_collector")
except ImportError as e:
    print(f"ImportError: {e}")
except SyntaxError as e:
    print(f"SyntaxError: {e}")
except Exception as e:
    print(f"Error: {e}")

try:
    print("Attempting to import services.camera_service...")
    import services.camera_service
    print("Successfully imported services.camera_service")
except Exception as e:
    print(f"Error importing services.camera_service: {e}")
