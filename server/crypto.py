"""
AES-256-GCM 解密模块

用于解密客户端上报的离线卸载码等加密数据。
与客户端 src/crypto.rs 使用相同的加密方案：
- AES-256-GCM
- 12字节 nonce 前缀
- base64 编码输出
"""

import base64
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


class ServerCrypto:
    """服务端 AES-256-GCM 解密类"""

    def __init__(self, shared_key_b64: str):
        """
        初始化解密器

        Args:
            shared_key_b64: base64 编码的 32 字节共享密钥
        """
        key = base64.b64decode(shared_key_b64)
        if len(key) != 32:
            raise ValueError("shared key must be 32 bytes")
        self.key = key
        self.aesgcm = AESGCM(key)

    def decrypt(self, encrypted: bytes) -> bytes:
        """
        解密数据

        Args:
            encrypted: 加密数据（12字节 nonce + ciphertext + 16字节 tag）

        Returns:
            解密后的原始数据
        """
        if len(encrypted) < 28:  # 12 nonce + 16 tag minimum
            raise ValueError("encrypted data too short")
        nonce = encrypted[:12]
        ciphertext = encrypted[12:]
        return self.aesgcm.decrypt(nonce, ciphertext, None)

    def decrypt_from_base64(self, encrypted_b64: str) -> bytes:
        """
        从 base64 编码的加密数据中解密

        Args:
            encrypted_b64: base64 编码的加密数据

        Returns:
            解密后的原始数据
        """
        encrypted = base64.b64decode(encrypted_b64)
        return self.decrypt(encrypted)

    def decrypt_offline_code(self, encrypted_b64: str) -> str:
        """
        解密离线卸载码

        Args:
            encrypted_b64: base64 编码的加密离线码

        Returns:
            解密后的 8 位离线卸载码
        """
        decrypted = self.decrypt_from_base64(encrypted_b64)
        return decrypted.decode('utf-8')

    def encrypt(self, plaintext: bytes) -> bytes:
        """
        加密数据（用于服务端生成离线码等场景）

        Args:
            plaintext: 原始数据

        Returns:
            加密数据（12字节 nonce + ciphertext + tag）
        """
        import secrets
        nonce = secrets.token_bytes(12)
        ciphertext = self.aesgcm.encrypt(nonce, plaintext, None)
        return nonce + ciphertext

    def encrypt_to_base64(self, plaintext: bytes) -> str:
        """
        加密数据并返回 base64 编码

        Args:
            plaintext: 原始数据

        Returns:
            base64 编码的加密数据
        """
        encrypted = self.encrypt(plaintext)
        return base64.b64encode(encrypted).decode('utf-8')

    def encrypt_offline_code(self, code: str) -> str:
        """
        加密离线卸载码

        Args:
            code: 8 位离线码

        Returns:
            base64 编码的加密数据
        """
        return self.encrypt_to_base64(code.encode('utf-8'))


def get_shared_key() -> str:
    """
    从环境变量或配置获取共享密钥

    Returns:
        base64 编码的共享密钥
    """
    import os
    from config import SHARED_KEY

    # 优先使用环境变量
    key_b64 = os.getenv("WINDSENTINEL_SHARED_KEY_B64")
    if key_b64:
        return key_b64

    # 使用配置中的密钥
    return SHARED_KEY


def decrypt_offline_uninstall_code(encrypted_b64: str, shared_key_b64: str = None) -> str:
    """
    解密离线卸载码的便捷函数

    Args:
        encrypted_b64: base64 编码的加密离线码
        shared_key_b64: 共享密钥（可选，默认从配置获取）

    Returns:
        解密后的 8 位离线卸载码
    """
    key = shared_key_b64 or get_shared_key()
    crypto = ServerCrypto(key)
    return crypto.decrypt_offline_code(encrypted_b64)


def encrypt_offline_uninstall_code(code: str, shared_key_b64: str = None) -> str:
    """
    加密离线卸载码的便捷函数

    Args:
        code: 8 位离线码
        shared_key_b64: 共享密钥（可选，默认从配置获取）

    Returns:
        base64 编码的加密数据
    """
    key = shared_key_b64 or get_shared_key()
    crypto = ServerCrypto(key)
    return crypto.encrypt_offline_code(code)


# ==================== 测试 ====================

if __name__ == "__main__":
    # 使用测试密钥进行验证
    test_key = base64.b64encode(bytes(32)).decode()
    crypto = ServerCrypto(test_key)

    # 测试加密解密
    test_code = "AbCd1234"
    encrypted = crypto.encrypt_offline_code(test_code)
    decrypted = crypto.decrypt_offline_code(encrypted)
    print(f"原始码: {test_code}")
    print(f"加密后: {encrypted}")
    print(f"解密后: {decrypted}")
    assert test_code == decrypted, "加密解密验证失败"
    print("✓ 加密解密验证成功")

    # 测试不同长度
    for code in ["12345678", "ABCDEFGH", "a1b2c3d4"]:
        encrypted = crypto.encrypt_offline_code(code)
        decrypted = crypto.decrypt_offline_code(encrypted)
        assert code == decrypted
    print("✓ 多组测试验证成功")