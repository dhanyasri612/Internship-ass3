# auth.py
import os
import time
import jwt
from passlib.hash import bcrypt

JWT_SECRET = os.getenv("JWT_SECRET", "devsecret")
JWT_ALGO = os.getenv("JWT_ALGORITHM", "HS256")
JWT_EXP = int(os.getenv("JWT_EXP_SECONDS", 86400))

def hash_password(password: str) -> str:
    return bcrypt.hash(password)

def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.verify(password, hashed)

def create_token(user_id: int) -> str:
    payload = {"sub": user_id, "exp": int(time.time()) + JWT_EXP}
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGO)

def decode_token(token: str):
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGO])
        return payload.get("sub")
    except Exception:
        return None
