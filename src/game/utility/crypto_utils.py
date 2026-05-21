from __future__ import annotations

import base64
import hashlib
from dataclasses import dataclass

from Crypto.Cipher import AES
from Crypto.Random import get_random_bytes
from Crypto.Util.Padding import pad, unpad


@dataclass(slots=True)
class EncryptedPayload:
    cipher_text: str
    checksum: str


class CryptoUtils:
    """AES 加密与完整性校验工具。"""

    BLOCK_SIZE = 16

    @staticmethod
    def derive_key(secret: str) -> bytes:
        return hashlib.sha256(secret.encode("utf-8")).digest()

    @staticmethod
    def encrypt_text(plain_text: str, *, secret: str) -> EncryptedPayload:
        key = CryptoUtils.derive_key(secret)
        iv = get_random_bytes(CryptoUtils.BLOCK_SIZE)
        cipher = AES.new(key, AES.MODE_CBC, iv=iv)
        encrypted = cipher.encrypt(pad(plain_text.encode("utf-8"), CryptoUtils.BLOCK_SIZE))
        payload = base64.b64encode(iv + encrypted).decode("utf-8")
        checksum = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        return EncryptedPayload(cipher_text=payload, checksum=checksum)

    @staticmethod
    def decrypt_text(payload: EncryptedPayload, *, secret: str) -> str:
        actual_checksum = hashlib.sha256(payload.cipher_text.encode("utf-8")).hexdigest()
        if actual_checksum != payload.checksum:
            raise ValueError("存档校验失败，数据可能已被篡改。")
        raw = base64.b64decode(payload.cipher_text.encode("utf-8"))
        iv, encrypted = raw[: CryptoUtils.BLOCK_SIZE], raw[CryptoUtils.BLOCK_SIZE :]
        cipher = AES.new(CryptoUtils.derive_key(secret), AES.MODE_CBC, iv=iv)
        plain_text = unpad(cipher.decrypt(encrypted), CryptoUtils.BLOCK_SIZE)
        return plain_text.decode("utf-8")

