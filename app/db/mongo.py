from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorCollection
from app.core.config import MONGO_URI, DATABASE_NAME
import certifi

client = AsyncIOMotorClient("mongodb+srv://rapifarma:30780142@cluster0.9nirn5t.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0",tlsCAFile=certifi.where())
db = client["RAPIFARMA"]

def get_collection(nombre: str) -> AsyncIOMotorCollection:
    return db[nombre]
