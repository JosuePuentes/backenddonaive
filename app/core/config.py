import os
from dotenv import load_dotenv

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")
print(f"URI: {MONGO_URI}")
DATABASE_NAME = os.getenv("DATABASE_NAME")
print(f"DB: {DATABASE_NAME}")