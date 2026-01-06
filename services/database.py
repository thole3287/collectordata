from pymongo import MongoClient
from pymongo.errors import ConnectionFailure
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


# Singleton client instance
_client = None

def get_db_connection():
    """Get MongoDB database connection (Singleton)."""
    global _client
    try:
        db_host = os.getenv('DB_HOST', 'localhost')
        db_port = int(os.getenv('DB_PORT', 27017))
        db_name = os.getenv('DB_NAME', 'data_collection')
        db_user = os.getenv('DB_USER', '')
        db_password = os.getenv('DB_PASSWORD', '')
        
        # If client already exists, check if it's alive (optional) or just return it
        if _client is not None:
            return _client[db_name]

        if db_user and db_password:
            connection_string = f"mongodb://{db_user}:{db_password}@{db_host}:{db_port}/"
        else:
            connection_string = f"mongodb://{db_host}:{db_port}/"
        
        # Create new client with connection pooling options if needed
        # PyMongo defaults are usually good (maxPoolSize=100)
        _client = MongoClient(connection_string, serverSelectionTimeoutMS=5000)
        
        # Test connection
        _client.admin.command('ping')
        db = _client[db_name]
        return db
    except (ConnectionFailure, Exception) as e:
        print(f"Error connecting to MongoDB: {e}")
        # Reset client on error so next retry creates a new one
        _client = None
        return None
