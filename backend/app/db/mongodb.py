from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from app.config import settings

client: AsyncIOMotorClient = None
db: AsyncIOMotorDatabase = None


async def init_mongodb():
    global client, db
    client = AsyncIOMotorClient(settings.mongodb_uri)
    db = client[settings.mongodb_db]


async def close_mongodb():
    global client
    if client:
        client.close()


def get_mongodb() -> AsyncIOMotorDatabase:
    return db
