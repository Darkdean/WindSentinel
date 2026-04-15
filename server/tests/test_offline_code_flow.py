"""
测试离线卸载码完整流程
"""
import pytest
import base64
from crypto import ServerCrypto, encrypt_offline_uninstall_code, decrypt_offline_uninstall_code


class TestOfflineCodeFlow:
    """测试离线卸载码生成、加密、解密完整流程"""

    def test_generate_and_encrypt_8_digit_code(self):
        """测试生成和加密8位码"""
        key_b64 = base64.b64encode(bytes(32)).decode()
        crypto = ServerCrypto(key_b64)
        
        # 模拟客户端生成8位码
        code = "X7K9m2Pq"  # 8位: 数字+大小写字母
        
        # 加密
        encrypted = crypto.encrypt_offline_code(code)
        
        # 验证加密后是 base64
        assert encrypted.isascii()
        assert len(encrypted) > 8
        
        # 服务端解密
        decrypted = crypto.decrypt_offline_code(encrypted)
        
        # 验证解密后与原始一致
        assert decrypted == code
        assert len(decrypted) == 8

    def test_multiple_codes_encrypted_differently(self):
        """测试相同码每次加密结果不同（nonce不同）"""
        key_b64 = base64.b64encode(bytes(32)).decode()
        crypto = ServerCrypto(key_b64)
        
        code = "SameCode1"
        
        encrypted1 = crypto.encrypt_offline_code(code)
        encrypted2 = crypto.encrypt_offline_code(code)
        
        # 加密结果不同（因为nonce）
        assert encrypted1 != encrypted2
        
        # 但都能正确解密
        assert crypto.decrypt_offline_code(encrypted1) == code
        assert crypto.decrypt_offline_code(encrypted2) == code

    def test_code_charset_validation(self):
        """测试码字符集验证"""
        import re
        
        charset_pattern = re.compile(r'^[0-9A-Za-z]{8}$')
        
        valid_codes = ["12345678", "ABCDEFGH", "abcdefgh", "A1b2C3d4", "X9Y8Z7W6"]
        for code in valid_codes:
            assert charset_pattern.match(code) is not None
        
        invalid_codes = ["1234567", "ABCDEFGHI", "abc!defg", "A1b2C3d"]
        for code in invalid_codes:
            assert charset_pattern.match(code) is None

    def test_server_stores_encrypted_code(self):
        """测试服务端存储加密码流程"""
        key_b64 = base64.b64encode(bytes(32)).decode()
        
        # 模拟客户端上报的加密码
        client_code = "R4t5Y6u7"
        encrypted_from_client = encrypt_offline_uninstall_code(client_code, key_b64)
        
        # 服务端收到后存储（mock）
        stored_encrypted = encrypted_from_client
        
        # 管理员请求查看时解密
        decrypted_for_admin = decrypt_offline_uninstall_code(stored_encrypted, key_b64)
        
        # 验证
        assert decrypted_for_admin == client_code
