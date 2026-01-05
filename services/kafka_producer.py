
import os
import json
import time
import logging
from kafka import KafkaProducer
from kafka.errors import NoBrokersAvailable

logger = logging.getLogger(__name__)

class KafkaQueue:
    def __init__(self, bootstrap_servers=None):
        if not bootstrap_servers:
            bootstrap_servers = os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'localhost:9092')
        
        self.bootstrap_servers = bootstrap_servers
        self.producer = None
        self.topic = 'video-tasks'
        
    def connect(self):
        """Establish connection to Kafka"""
        try:
            self.producer = KafkaProducer(
                bootstrap_servers=self.bootstrap_servers,
                value_serializer=lambda v: json.dumps(v).encode('utf-8'),
                retries=5
            )
            logger.info(f"Connected to Kafka at {self.bootstrap_servers}")
            return True
        except NoBrokersAvailable:
            logger.error("No Kafka brokers available")
            return False
        except Exception as e:
            logger.error(f"Failed to connect to Kafka: {e}")
            return False

    def send_task(self, source, keyword, priority=1):
        """Send a task to the queue"""
        if not self.producer:
            if not self.connect():
                return False

        message = {
            "source": source,
            "keyword": keyword,
            "timestamp": time.time(),
            "priority": priority
        }
        
        try:
            future = self.producer.send(self.topic, message)
            # Block for result to ensure delivery
            record_metadata = future.get(timeout=10)
            logger.info(f"Sent task to Kafka: {source} - {keyword} (partition: {record_metadata.partition})")
            return True
        except Exception as e:
            logger.error(f"Failed to send task to Kafka: {e}")
            return False

    def close(self):
        if self.producer:
            self.producer.close()

# Global instance
kafka_queue = KafkaQueue()
