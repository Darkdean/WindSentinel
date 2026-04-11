use crate::config::AgentConfig;
use crate::log_store::LogStore;
use crate::types::{LogRecord, RecordKind};
use anyhow::{anyhow, Context, Result};
use base64::Engine;
use serde::Serialize;
use sysinfo::{Disks, System};

#[derive(Serialize)]
pub struct HealthReport {
    agent_id: String,
    uid: u32,
    gid: u32,
    running_as_root: bool,
    cpu_usage: f32,
    memory_used: u64,
    memory_total: u64,
    disks: Vec<DiskInfo>,
    host_name: Option<String>,
    os_version: Option<String>,
    timestamp: i64,
}

#[derive(Serialize)]
pub struct DiskInfo {
    name: String,
    total: u64,
    available: u64,
}

pub async fn collect_health(config: &AgentConfig, log_store: &tokio::sync::Mutex<LogStore>) -> Result<()> {
    let mut system = System::new_all();
    system.refresh_all();
    let cpu_usage = system.global_cpu_usage();
    let memory_used = system.used_memory();
    let memory_total = system.total_memory();
    let disks = Disks::new_with_refreshed_list()
        .iter()
        .map(|disk| DiskInfo {
            name: disk.name().to_string_lossy().to_string(),
            total: disk.total_space(),
            available: disk.available_space(),
        })
        .collect();
    let report = HealthReport {
        agent_id: config.agent_id.clone(),
        uid: unsafe { libc::geteuid() },
        gid: unsafe { libc::getegid() },
        running_as_root: unsafe { libc::geteuid() == 0 },
        cpu_usage,
        memory_used,
        memory_total,
        disks,
        host_name: System::host_name(),
        os_version: System::os_version(),
        timestamp: chrono::Utc::now().timestamp(),
    };
    let record = LogRecord {
        kind: RecordKind::Health,
        timestamp: report.timestamp,
        data: serde_json::to_value(report).context("serialize health")?,
    };
    log_store.lock().await.append_record(record).await?;
    Ok(())
}

pub async fn push_health(config: &AgentConfig, log_store: &tokio::sync::Mutex<LogStore>) -> Result<()> {
    let mut system = System::new_all();
    system.refresh_all();
    let report = HealthReport {
        agent_id: config.agent_id.clone(),
        uid: unsafe { libc::geteuid() },
        gid: unsafe { libc::getegid() },
        running_as_root: unsafe { libc::geteuid() == 0 },
        cpu_usage: system.global_cpu_usage(),
        memory_used: system.used_memory(),
        memory_total: system.total_memory(),
        disks: Disks::new_with_refreshed_list()
            .iter()
            .map(|disk| DiskInfo {
                name: disk.name().to_string_lossy().to_string(),
                total: disk.total_space(),
                available: disk.available_space(),
            })
            .collect(),
        host_name: System::host_name(),
        os_version: System::os_version(),
        timestamp: chrono::Utc::now().timestamp(),
    };
    let payload = serde_json::to_vec(&report).context("serialize health")?;
    let encrypted = log_store.lock().await.encrypt_payload(&payload)?;
    let payload_b64 = base64::engine::general_purpose::STANDARD.encode(encrypted);
    let client = reqwest::Client::new();
    let resp = client
        .post(format!("{}/api/v1/health", config.server_url))
        .json(&serde_json::json!({ "agent_id": config.agent_id, "payload": payload_b64 }))
        .send()
        .await
        .context("send health")?;
    if !resp.status().is_success() {
        return Err(anyhow!("health upload failed {}", resp.status()));
    }
    Ok(())
}
