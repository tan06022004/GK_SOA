
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
import os

# Connection string from Atlas
load_dotenv()
MONGO_URL = os.getenv("MONGODB_URL")

client = None
db = None


async def connect_db():
    global client, db
    try:
        client = AsyncIOMotorClient(MONGO_URL)
        await client.admin.command('ping')
        db = client.ibanking_db

        await db.users.create_index("username", unique = True)
        await db.students.create_index("mssv", unique = True)
        await db.otps.create_index("code", unique = True);
        print("MongoDb Atlas connected successfully !")
    except Exception as e:
        print(f"Connect failed: {e}")
        raise

async def close_db():
    client.close()
    print("MongoDB Atlas disconnected !")

async def get_db():
    if db is None:
        await connect_db()
    return db        

if __name__ == "__main__":
    import asyncio
    asyncio.run(connect_db())
    