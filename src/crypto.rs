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

}
