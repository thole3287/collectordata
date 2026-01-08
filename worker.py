
import os
import json
import time
import logging
from kafka import KafkaConsumer
from dotenv import load_dotenv

# Services
import services.video_service as video_service
import services.pexels_service as pexels_service
import services.yt_service as yt

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('worker.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

# Load env
load_dotenv()

def get_kafka_consumer():
    bootstrap_servers = os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'localhost:9092')
    topic = 'video-tasks'
    
    while True:
        try:
            consumer = KafkaConsumer(
                topic,
                bootstrap_servers=bootstrap_servers,
                auto_offset_reset='earliest',
                enable_auto_commit=True,
                group_id='collector_workers',
                value_deserializer=lambda x: json.loads(x.decode('utf-8'))
            )
            logger.info(f"Connected to Kafka Consumer at {bootstrap_servers}")
            return consumer
        except Exception as e:
            logger.error(f"Waiting for Kafka... ({e})")
            time.sleep(5)

def process_youtube_task(keyword):
    logger.info(f"Processing YouTube task: {keyword}")
    try:
        # 1. Download video
        videos = yt.download_by_keyword(keyword, num_videos=1)
        if videos:
            # 2. Extract frames (assuming downloads folder)
            downloads_folder = os.path.join(os.getcwd(), 'downloads')
            if os.path.exists(downloads_folder):
                video_service.extract_frames_from_folder(downloads_folder)
                logger.info("YouTube frames extracted successfully")
        else:
            logger.warning(f"No YouTube videos found for {keyword}")
    except Exception as e:
        logger.error(f"Error processing YouTube task: {e}")

def process_pexels_task(keyword):
    logger.info(f"Processing Pexels task: {keyword}")
    try:
        api_key = os.getenv('PEXELS_API_KEY')
        if not api_key:
            logger.error("PEXELS_API_KEY not found")
            return

        pexels_service.download_pexels_videos(keyword, num_videos=1, api_key=api_key)
        logger.info("Pexels task completed successfully")
    except Exception as e:
        logger.error(f"Error processing Pexels task: {e}")

def main():
    logger.info("Worker started...")
    consumer = get_kafka_consumer()
    
    logger.info("Waiting for messages...")
    for message in consumer:
        try:
            task = message.value
            source = task.get('source')
            keyword = task.get('keyword')
            
            logger.info(f"Received task: {source} -> {keyword}")
            
            if source == 'youtube':
                process_youtube_task(keyword)
            elif source == 'pexels':
                process_pexels_task(keyword)
            else:
                logger.warning(f"Unknown source: {source}")
                
        except Exception as e:
            logger.error(f"Error processing message: {e}")

if __name__ == "__main__":
    main()
