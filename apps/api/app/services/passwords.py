from pwdlib import PasswordHash

_password_hasher = PasswordHash.recommended()


def hash_password(plain: str) -> str:
    return _password_hasher.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return _password_hasher.verify(plain, hashed)
