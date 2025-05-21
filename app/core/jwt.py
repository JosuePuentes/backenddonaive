from datetime import datetime, timedelta
from jose import jwt

SECRET_KEY = "30780142"
ALGORITHM = "HS256"
EXPIRATION_MINUTES = 60

def crear_token_jwt(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=EXPIRATION_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt
