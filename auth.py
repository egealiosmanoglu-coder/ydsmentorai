import os
import jwt
from datetime import datetime, timedelta, timezone
from passlib.context import CryptContext
from fastapi import Header, HTTPException

# Render'da bir environment variable olarak ayarlanmalı (rastgele uzun bir metin).
# Ayarlanmazsa geliştirme için bir varsayılan kullanılır ama bunu production'da
# MUTLAKA kendi gizli anahtarınla değiştir.
SECRET_KEY = os.environ.get("JWT_SECRET", "gelistirme-icin-degistir-bunu-render-da")
ALGORITHM = "HS256"
TOKEN_EXPIRE_DAYS = 30

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return pwd_context.verify(password, password_hash)


def create_token(user_id: int) -> str:
    payload = {
        "sub": str(user_id),
        "exp": datetime.now(timezone.utc) + timedelta(days=TOKEN_EXPIRE_DAYS),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> int:
    """Token'ı çözer, geçerliyse user_id (int) döndürür, değilse hata fırlatır."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return int(payload["sub"])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Oturum süresi doldu, lütfen tekrar giriş yap.")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Geçersiz oturum.")


def get_current_user_id(authorization: str = Header(default=None)) -> int:
    """
    'Authorization: Bearer <token>' başlığından kullanıcı id'sini çıkarır.
    Token yoksa veya geçersizse 401 hatası fırlatır.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Giriş yapmalısın.")
    token = authorization.removeprefix("Bearer ").strip()
    return decode_token(token)
