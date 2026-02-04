import os
import sys
from kafka import KafkaConsumer, TopicPartition
from kafka.admin import KafkaAdminClient
from dotenv import load_dotenv

# Fix encoding for Windows
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

load_dotenv()

def check_active_consumers():
    bootstrap_servers = os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'localhost:9092')
    group_id = 'collector_workers'
    topic = 'video-tasks'
    
    print(f"Kiem tra so worker dang chay...")
    print(f"Kafka server: {bootstrap_servers}")
    print(f"Consumer Group: {group_id}\n")
    
    try:
        # Create consumer to check group
        consumer = KafkaConsumer(
            bootstrap_servers=bootstrap_servers,
            group_id=group_id,
            enable_auto_commit=False
        )
        
        # Get partitions
        partitions = consumer.partitions_for_topic(topic)
        if not partitions:
            print(f"Topic '{topic}' khong ton tai!")
            consumer.close()
            return
        
        print(f"Topic '{topic}' co {len(partitions)} partitions: {sorted(partitions)}")
        
        # Get committed offsets
        topic_partitions = [TopicPartition(topic, p) for p in partitions]
        committed_offsets = {}
        for tp in topic_partitions:
            offset = consumer.committed(tp)
            committed_offsets[tp] = offset
        
        print(f"\nTrang thai offsets:")
        has_activity = False
        for tp in topic_partitions:
            offset = committed_offsets.get(tp)
            if offset is None:
                offset = 0
            print(f"  Partition {tp.partition}: offset = {offset}")
            if offset > 0:
                has_activity = True
        
        if has_activity:
            print(f"\n[OK] Co consumer dang hoat dong (da commit offsets)")
        else:
            print(f"\n[NO] Khong co consumer nao dang hoat dong (chua commit offsets)")
        
        # Try to get consumer group members using admin API
        print(f"\nDang kiem tra so luong consumer members...")
        try:
            admin_client = KafkaAdminClient(
                bootstrap_servers=bootstrap_servers,
                client_id='check_workers'
            )
            
            # Use describe_consumer_groups
            from kafka.admin import describe_consumer_groups
            from kafka.errors import GroupCoordinatorNotAvailableError
            
            try:
                groups = admin_client.describe_consumer_groups([group_id], group_coordinator_timeout_ms=5000)
                if group_id in groups:
                    group_info = groups[group_id]
                    print(f"Group State: {group_info.state}")
                    
                    # Try to get members
                    if hasattr(group_info, 'members'):
                        member_count = len(group_info.members) if group_info.members else 0
                        print(f"\n{'='*50}")
                        print(f"SO WORKER DANG CHAY: {member_count}")
                        print(f"{'='*50}")
                        
                        if member_count > 0:
                            print(f"\nChi tiet cac worker:")
                            for member_id, member in group_info.members.items():
                                print(f"  - {member_id}")
                                if hasattr(member, 'member_metadata') and hasattr(member.member_metadata, 'assignment'):
                                    assignment = member.member_metadata.assignment
                                    if hasattr(assignment, 'partitions'):
                                        parts = assignment.partitions()
                                        print(f"    Partitions: {sorted(parts)}")
                    else:
                        print("Khong the lay thong tin members tu API nay.")
                        print("Co the can su dung kafka-consumer-groups.sh command line tool.")
            except Exception as e:
                print(f"Khong the lay thong tin consumer group: {e}")
                print("\nGoi y: Kiem tra bang cach:")
                print("1. Xem log file worker.log")
                print("2. Kiem tra process dang chay")
                print("3. Su dung kafka-consumer-groups.sh neu co Docker/Kafka tools")
            
            admin_client.close()
        except Exception as e:
            print(f"Loi khi kiem tra admin API: {e}")
        
        consumer.close()
        
    except Exception as e:
        print(f"Loi: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    check_active_consumers()
