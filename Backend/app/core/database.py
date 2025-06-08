from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorCollection
import redis
from app.core.config import settings

# MongoDB Connection
mongodb_client: AsyncIOMotorClient = None

async def connect_to_mongodb():
    global mongodb_client
    try:
        print(f"Before connection - mongodb_client: {mongodb_client}")
        mongodb_client = AsyncIOMotorClient(settings.MONGODB_URL)
        print(f"After assignment - mongodb_client: {mongodb_client}")
        print(f"MongoDB URL: {settings.MONGODB_URL}")
        
        # Test the connection
        await mongodb_client.admin.command('ping')
        print("Connected to MongoDB and ping successful.")
    except Exception as e:
        print(f"Could not connect to MongoDB: {e}")
        raise e

async def close_mongodb_connection():
    global mongodb_client
    if mongodb_client:
        mongodb_client.close()
        print("MongoDB connection closed.")

def get_mongodb_client():
    """Get the MongoDB client instance."""
    return mongodb_client

def get_database():
    client = get_mongodb_client()
    if client is None:
        raise RuntimeError("MongoDB client is not initialized. Please ensure connect_to_mongodb() was called.")
    return client[settings.MONGODB_DB_NAME]

async def get_metrics_collection() -> AsyncIOMotorCollection:
    """Get the ad_metrics collection from MongoDB."""
    db = get_database()
    return db.ad_metrics

async def get_users_collection() -> AsyncIOMotorCollection:
    """Get the users collection from MongoDB."""
    db = get_database()
    return db.users

# Redis Connection
redis_client = redis.Redis(
    host=settings.REDIS_HOST,
    port=settings.REDIS_PORT,
    db=settings.REDIS_DB,
    decode_responses=True
)

def get_redis():
    return redis_client 