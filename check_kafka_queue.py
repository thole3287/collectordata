import os
import json
from kafka import KafkaConsumer, TopicPartition
from dotenv import load_dotenv

load_dotenv()

def check_queue_lag():
    bootstrap_servers = os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'localhost:9092')
    topic = 'video-tasks'
    group_id = 'collector_workers'
    
    print(f"Connecting to Kafka at {bootstrap_servers}...")
    
    try:
        # Create a consumer to inspect the topic
        consumer = KafkaConsumer(
            bootstrap_servers=bootstrap_servers,
            group_id=group_id,
            enable_auto_commit=False 
        )
        
        # Get partitions for the topic
        partitions = consumer.partitions_for_topic(topic)
        if not partitions:
            print(f"[WARN] Topic '{topic}' not found or has no partitions.")
            return

        topic_partitions = [TopicPartition(topic, p) for p in partitions]
        
        # Get End Offsets (Head of the queue)
        end_offsets = consumer.end_offsets(topic_partitions)
        
        total_lag = 0
        total_messages = 0
        
        print(f"\n[INFO] Queue Status for topic '{topic}' (Group: {group_id}):")
        print(f"{'Partition':<10} {'Current Offset':<15} {'End Offset':<15} {'Lag (Pending)':<15}")
        print("-" * 60)
        
        for tp in topic_partitions:
            # Get Committed Offset (Where the consumer group is currently at)
            committed = consumer.committed(tp)
            
            # If nothing committed, assume 0 (start)
            current_offset = committed if committed is not None else 0
            end_offset = end_offsets[tp]
            
            lag = end_offset - current_offset
            
            # If current > end (shouldn't happen unless reset), treat as 0 lag
            if lag < 0: lag = 0
            
            total_lag += lag
            total_messages += end_offset
            
            print(f"{tp.partition:<10} {current_offset:<15} {end_offset:<15} {lag:<15}")
            
        print("-" * 60)
        print(f"Total Pending Tasks (Approx): {total_lag}")
        print(f"Total Messages Processed/Pending: {total_messages}")
        
        consumer.close()
        
    except Exception as e:
        print(f"[ERROR] Error checking Kafka: {e}")

if __name__ == "__main__":
    check_queue_lag()
