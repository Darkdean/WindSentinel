use aes_gcm::aead::Aead;
use aes_gcm::{Aes256Gcm, KeyInit, Nonce};
use anyhow::{anyhow, Context, Result};
use base64::Engine;
use rand::RngCore;

#[derive(Clone)]
pub struct SessionCrypto {
    key: [u8; 32],
}

impl SessionCrypto {
    pub fn new(shared_key_b64: &str) -> Result<Self> {
        let key = base64::engine::general_purpose::STANDARD
            .decode(shared_key_b64)
            .context("decode shared key")?;
        if key.len() != 32 {
            return Err(anyhow!("shared key length invalid"));
        }
        let mut key_bytes = [0u8; 32];
        key_bytes.copy_from_slice(&key);
        Ok(SessionCrypto { key: key_bytes })
    }

    pub fn encrypt(&self, plaintext: &[u8]) -> Result<Vec<u8>> {
        let cipher = Aes256Gcm::new_from_slice(&self.key).context("init cipher")?;
        let mut nonce_bytes = [0u8; 12];
        rand::thread_rng().fill_bytes(&mut nonce_bytes);
        let nonce = Nonce::from_slice(&nonce_bytes);
        let mut out = Vec::with_capacity(12 + plaintext.len() + 16);
        let ciphertext = cipher.encrypt(nonce, plaintext).map_err(|_| anyhow!("encrypt"))?;
        out.extend_from_slice(&nonce_bytes);
        out.extend_from_slice(&ciphertext);
        Ok(out)
    }

    pub fn decrypt(&self, encrypted: &[u8]) -> Result<Vec<u8>> {
        if encrypted.len() < 12 + 16 {
            return Err(anyhow!("encrypted data too short"));
        }
        let cipher = Aes256Gcm::new_from_slice(&self.key).context("init cipher")?;
        let nonce_bytes = &encrypted[..12];
        let ciphertext = &encrypted[12..];
        let nonce = Nonce::from_slice(nonce_bytes);
        cipher.decrypt(nonce, ciphertext).map_err(|_| anyhow!("decrypt"))
    }

    /// 加密离线卸载码，返回 base64 编码的加密数据
    pub fn encrypt_offline_code(&self, code: &str) -> Result<String> {
        let encrypted = self.encrypt(code.as_bytes())?;
        Ok(base64::engine::general_purpose::STANDARD.encode(&encrypted))
    }

    /// 解密离线卸载码，从 base64 编码的加密数据中还原原始码
    pub fn decrypt_offline_code(&self, encrypted_b64: &str) -> Result<String> {
        let encrypted = base64::engine::general_purpose::STANDARD
            .decode(encrypted_b64)
            .context("decode base64")?;
        let decrypted = self.decrypt(&encrypted)?;
        String::from_utf8(decrypted).context("convert to string")
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use base64::Engine;

    fn test_key() -> String {
        base64::engine::general_purpose::STANDARD.encode([0u8; 32])
    }

    #[test]
    fn test_encrypt_decrypt() {
        let crypto = SessionCrypto::new(&test_key()).unwrap();
        let plaintext = b"hello world";
        let encrypted = crypto.encrypt(plaintext).unwrap();
        let decrypted = crypto.decrypt(&encrypted).unwrap();
        assert_eq!(plaintext.to_vec(), decrypted);
    }

    #[test]
    fn test_encrypt_decrypt_offline_code() {
        let crypto = SessionCrypto::new(&test_key()).unwrap();
        let code = "AbCd1234";
        let encrypted = crypto.encrypt_offline_code(code).unwrap();
        let decrypted = crypto.decrypt_offline_code(&encrypted).unwrap();
        assert_eq!(code, decrypted);
    }

    #[test]
    fn test_encrypt_offline_code_length() {
        let crypto = SessionCrypto::new(&test_key()).unwrap();
        // 8位字符码加密后应该产生 base64 编码的输出
        let code = "AbCd1234";
        let encrypted = crypto.encrypt_offline_code(code).unwrap();
        // 原始加密数据: 12 nonce + 8 plaintext + 16 tag = 36 bytes
        // base64 编码后大约 48 字符
        assert!(encrypted.len() > 36);
    }

    #[test]
    fn test_decrypt_invalid_data() {
        let crypto = SessionCrypto::new(&test_key()).unwrap();
        // 太短的数据应该失败
        let result = crypto.decrypt(&[0u8; 10]);
        assert!(result.is_err());
    }

    #[test]
    fn test_decrypt_invalid_base64() {
        let crypto = SessionCrypto::new(&test_key()).unwrap();
        let result = crypto.decrypt_offline_code("not-valid-base64!!!");
        assert!(result.is_err());
    }
}
