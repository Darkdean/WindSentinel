"""
测试 AES-256-GCM 加密解密模块
"""
import pytest
import base64
from crypto import ServerCrypto, decrypt_offline_uninstall_code, encrypt_offline_uninstall_code


class TestServerCrypto:
    """测试 ServerCrypto 类"""

    def test_init_with_valid_key(self):
        """测试有效密钥初始化"""
        key_b64 = base64.b64encode(bytes(32)).decode()
        crypto = ServerCrypto(key_b64)
        assert crypto.key == bytes(32)

    def test_init_with_invalid_key_length(self):
        """测试无效密钥长度"""
        key_b64 = base64.b64encode(bytes(16)).decode()
        with pytest.raises(ValueError, match="must be 32 bytes"):
            ServerCrypto(key_b64)

    def test_encrypt_decrypt_roundtrip(self):
        """测试加密解密往返"""
        key_b64 = base64.b64encode(bytes(32)).decode()
        crypto = ServerCrypto(key_b64)
        plaintext = b"hello world"
        encrypted = crypto.encrypt(plaintext)
        decrypted = crypto.decrypt(encrypted)
        assert decrypted == plaintext

    def test_encrypt_produces_different_nonces(self):
        """测试每次加密产生不同的 nonce"""
        key_b64 = base64.b64encode(bytes(32)).decode()
        crypto = ServerCrypto(key_b64)
        plaintext = b"same data"
        encrypted1 = crypto.encrypt(plaintext)
        encrypted2 = crypto.encrypt(plaintext)
        # nonce 不同，所以加密结果不同
        assert encrypted1 != encrypted2
        # 但都能正确解密
        assert crypto.decrypt(encrypted1) == plaintext
        assert crypto.decrypt(encrypted2) == plaintext

    def test_decrypt_invalid_data_too_short(self):
        """测试解密过短数据"""
        key_b64 = base64.b64encode(bytes(32)).decode()
        crypto = ServerCrypto(key_b64)
        with pytest.raises(ValueError, match="too short"):
            crypto.decrypt(bytes(10))

    def test_decrypt_invalid_base64(self):
        """测试解密无效 base64"""
        key_b64 = base64.b64encode(bytes(32)).decode()
        crypto = ServerCrypto(key_b64)
        with pytest.raises(Exception):
            crypto.decrypt_from_base64("not-valid-base64!!!")

    def test_decrypt_offline_code(self):
        """测试解密离线卸载码"""
        key_b64 = base64.b64encode(bytes(32)).decode()
        crypto = ServerCrypto(key_b64)
        code = "AbCd1234"
        encrypted = crypto.encrypt_offline_code(code)
        decrypted = crypto.decrypt_offline_code(encrypted)
        assert decrypted == code
        assert len(decrypted) == 8

    def test_encrypt_offline_code_produces_base64(self):
        """测试加密离线码产生 base64 输出"""
        key_b64 = base64.b64encode(bytes(32)).decode()
        crypto = ServerCrypto(key_b64)
        code = "12345678"
        encrypted = crypto.encrypt_offline_code(code)
        # 验证是有效的 base64
        decoded = base64.b64decode(encrypted)
        assert len(decoded) >= 28  # 12 nonce + 8 plaintext + 16 tag


class TestConvenienceFunctions:
    """测试便捷函数"""

    def test_decrypt_offline_uninstall_code_default_key(self):
        """测试使用默认密钥解密"""
        key_b64 = base64.b64encode(bytes(32)).decode()
        code = "TestCode"
        encrypted = encrypt_offline_uninstall_code(code, key_b64)
        decrypted = decrypt_offline_uninstall_code(encrypted, key_b64)
        assert decrypted == code

    def test_encrypt_decrypt_offline_code_roundtrip(self):
        """测试加密解密往返"""
        key_b64 = base64.b64encode(bytes(32)).decode()
        for code in ["12345678", "ABCDEFGH", "a1b2c3d4", "XyZ9WvU7"]:
            encrypted = encrypt_offline_uninstall_code(code, key_b64)
            decrypted = decrypt_offline_uninstall_code(encrypted, key_b64)
            assert decrypted == code


class TestCrossPlatformCompatibility:
    """测试跨平台兼容性"""

    def test_8_digit_charset(self):
        """测试8位码字符集"""
        key_b64 = base64.b64encode(bytes(32)).decode()
        crypto = ServerCrypto(key_b64)
        # 测试各种字符组合
        test_codes = [
            "12345678",  # 纯数字
            "ABCDEFGH",  # 纯大写
            "abcdefgh",  # 纯小写
            "A1b2C3d4",  # 混合
            "XyZ9WvU7",  # 混合2
        ]
        for code in test_codes:
            encrypted = crypto.encrypt_offline_code(code)
            decrypted = crypto.decrypt_offline_code(encrypted)
            assert decrypted == code
