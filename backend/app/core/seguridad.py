"""Contraseñas (Argon2id) y tokens de sesión."""
import hashlib
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

_hasher = PasswordHasher()  # argon2-cffi usa Argon2id por defecto

COOKIE_SESION = "siget_sesion"
COOKIE_CSRF = "siget_csrf"
CABECERA_CSRF = "X-CSRF-Token"


def hashear_password(password: str) -> str:
    return _hasher.hash(password)


def verificar_password(hash_guardado: str, password: str) -> bool:
    try:
        return _hasher.verify(hash_guardado, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def necesita_rehash(hash_guardado: str) -> bool:
    return _hasher.check_needs_rehash(hash_guardado)


def generar_token() -> str:
    return secrets.token_urlsafe(32)  # 256 bits


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def tokens_iguales(a: str, b: str) -> bool:
    return secrets.compare_digest(a, b)
