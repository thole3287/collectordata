from pymongo import MongoClient
from pymongo.errors import ConnectionFailure
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def get_db_connection():
    """Get MongoDB database connection."""
    try:
        db_host = os.getenv('DB_HOST', 'localhost')
        db_port = int(os.getenv('DB_PORT', 27017))
        db_name = os.getenv('DB_NAME', 'data_collection')
        db_user = os.getenv('DB_USER', '')
        db_password = os.getenv('DB_PASSWORD', '')
        
        if db_user and db_password:
            connection_string = f"mongodb://{db_user}:{db_password}@{db_host}:{db_port}/"
        else:
            connection_string = f"mongodb://{db_host}:{db_port}/"
        
        client = MongoClient(connection_string)
        # Test connection
        client.admin.command('ping')
        db = client[db_name]
        return db
    except (ConnectionFailure, Exception) as e:
        print(f"Error connecting to MongoDB: {e}")
        return None
