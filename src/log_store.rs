use crate::config::AgentConfig;
use crate::crypto::SessionCrypto;
use crate::types::LogRecord;
use anyhow::{anyhow, Context, Result};
use base64::Engine;
use flate2::write::GzEncoder;
use flate2::Compression;
use serde::{Deserialize, Serialize};
use std::fs::{File, OpenOptions};
use std::io::{Read, Seek, SeekFrom, Write};
use std::path::PathBuf;

#[derive(Serialize, Deserialize)]
pub struct EncryptedPayload {
    pub data_b64: String,
}

pub struct LogStore {
    path: PathBuf,
    session: SessionCrypto,
    offset: u64,
}

impl LogStore {
    pub fn new(path: PathBuf, session: SessionCrypto) -> Self {
        LogStore { path, session, offset: 0 }
    }

    pub fn encrypt_payload(&self, data: &[u8]) -> Result<Vec<u8>> {
        self.session.encrypt(data)
    }

    pub async fn append_record(&mut self, record: LogRecord) -> Result<()> {
        let data = serde_json::to_vec(&record).context("serialize record")?;
        let mut encoder = GzEncoder::new(Vec::new(), Compression::default());
        encoder.write_all(&data).context("compress record")?;
        let compressed = encoder.finish().context("finish compress")?;
        let encrypted = self.session.encrypt(&compressed)?;
        let mut file = OpenOptions::new().create(true).append(true).open(&self.path).context("open log")?;
        let len = encrypted.len() as u32;
        file.write_all(&len.to_be_bytes()).context("write len")?;
        file.write_all(&encrypted).context("write payload")?;
        Ok(())
    }

    pub async fn push_incremental(&mut self, config: &AgentConfig) -> Result<()> {
        if !self.path.exists() {
            return Ok(());
        }
        let mut file = OpenOptions::new().read(true).open(&self.path).context("open log read")?;
        let size = file.metadata().context("meta")?.len();
        if self.offset >= size {
            return Ok(());
        }
        file.seek(SeekFrom::Start(self.offset)).context("seek")?;
        let mut buf = Vec::new();
        file.read_to_end(&mut buf).context("read log increment")?;
        let payload = EncryptedPayload { data_b64: base64::engine::general_purpose::STANDARD.encode(buf) };
        let client = reqwest::Client::new();
        let resp = client
            .post(format!("{}/api/v1/logs", config.server_url))
            .json(&serde_json::json!({ "agent_id": config.agent_id, "payload": payload }))
            .send()
            .await
            .context("send logs")?;
        if !resp.status().is_success() {
            return Err(anyhow!("log upload failed {}", resp.status()));
        }
        self.offset = size;
        if size > 500 * 1024 * 1024 {
            let mut file = File::create(&self.path).context("truncate log")?;
            file.write_all(&[]).ok();
            self.offset = 0;
        }
        Ok(())
    }

}
