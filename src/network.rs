use crate::config::AgentConfig;
use crate::log_store::LogStore;
use crate::types::{LogRecord, RecordKind};
use anyhow::{Context, Result};
use serde::Serialize;
use std::process::Command;

#[derive(Serialize)]
struct NetworkEvent {
    sip: Option<String>,
    sport: Option<u16>,
    dip: Option<String>,
    dport: Option<u16>,
    protocol: String,
    url: Option<String>,
    method: Option<String>,
    body: Option<String>,
    timestamp: i64,
}

pub async fn collect_network_events(_config: &AgentConfig, log_store: &tokio::sync::Mutex<LogStore>) -> Result<()> {
    let output = Command::new("netstat")
        .args(["-anv", "-p", "tcp"])
        .output();
    if output.is_err() {
        return Ok(());
    }
    let output = output.unwrap();
    let stdout = String::from_utf8_lossy(&output.stdout);
    for line in stdout.lines() {
        if !line.contains("ESTABLISHED") {
            continue;
        }
        let parts: Vec<&str> = line.split_whitespace().collect();
        if parts.len() < 5 {
            continue;
        }
        let local = parts.get(3).cloned().unwrap_or_default();
        let remote = parts.get(4).cloned().unwrap_or_default();
        let (sip, sport) = split_addr(local);
        let (dip, dport) = split_addr(remote);
        let event = NetworkEvent {
            sip,
            sport,
            dip,
            dport,
            protocol: "tcp".to_string(),
            url: None,
            method: None,
            body: None,
            timestamp: chrono::Utc::now().timestamp(),
        };
        let record = LogRecord {
            kind: RecordKind::Network,
            timestamp: event.timestamp,
            data: serde_json::to_value(event).context("serialize net")?,
        };
        log_store.lock().await.append_record(record).await?;
    }
    Ok(())
}

fn split_addr(addr: &str) -> (Option<String>, Option<u16>) {
    if let Some((host, port)) = addr.rsplit_once('.') {
        if let Ok(port_num) = port.parse::<u16>() {
            return (Some(host.to_string()), Some(port_num));
        }
    }
    (None, None)
}
