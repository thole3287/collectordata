import os
import zipfile
import shutil
import urllib.request
import sys

FFMPEG_URL = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
DOWNLOAD_DIR = "ffmpeg_temp"
BIN_DIR = "bin"

def install_ffmpeg():
    print(f"Checking for existing installation in {BIN_DIR}...")
    if not os.path.exists(BIN_DIR):
        os.makedirs(BIN_DIR)

    ffmpeg_exe = os.path.join(BIN_DIR, "ffmpeg.exe")
    ffprobe_exe = os.path.join(BIN_DIR, "ffprobe.exe")

    if os.path.exists(ffmpeg_exe) and os.path.exists(ffprobe_exe):
        print("✅ FFmpeg is already installed in 'bin/' folder.")
        # Verify version?
        return

    print(f"Downloading FFmpeg from {FFMPEG_URL}...")
    zip_path = "ffmpeg.zip"
    
    try:
        # Download with progress hook
        def progress_hook(count, block_size, total_size):
            percent = int(count * block_size * 100 / total_size)
            if percent % 10 == 0:
                print(f"Downloading: {percent}%", end="\r")
                
        urllib.request.urlretrieve(FFMPEG_URL, zip_path, progress_hook)
        print("\nDownload complete. Extracting...")

        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            # Look for bin/ffmpeg.exe in the zip
            for file in zip_ref.namelist():
                if file.endswith("bin/ffmpeg.exe"):
                    print(f"Extracting {file}...")
                    source = zip_ref.open(file)
                    target = open(ffmpeg_exe, "wb")
                    with source, target:
                        shutil.copyfileobj(source, target)
                elif file.endswith("bin/ffprobe.exe"):
                    print(f"Extracting {file}...")
                    source = zip_ref.open(file)
                    target = open(ffprobe_exe, "wb")
                    with source, target:
                        shutil.copyfileobj(source, target)
        
        print("Cleaning up...")
        if os.path.exists(zip_path):
            os.remove(zip_path)
            
        print("✅ FFmpeg installed successfully to 'bin/' folder.")
        
    except Exception as e:
        print(f"❌ Error installing FFmpeg: {e}")
        if os.path.exists(zip_path):
            os.remove(zip_path)

if __name__ == "__main__":
    install_ffmpeg()
