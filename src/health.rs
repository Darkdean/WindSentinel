use crate::config::{AgentConfig, generate_offline_uninstall_code};
use crate::log_store::LogStore;
use crate::system_info::{get_system_info, SystemInfo};
use crate::types::{LogRecord, RecordKind};
use anyhow::{anyhow, Context, Result};
use base64::Engine;
use serde::Serialize;
use sysinfo::{Disks, System};
use std::fs;

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
    /// 计算机名
    computer_name: String,
    /// 系统序列号
    system_serial: String,
    /// 主板序列号
    board_serial: String,
    /// AES加密后的离线卸载码（首次上报时携带）
    offline_uninstall_code_encrypted: Option<String>,
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

    // 获取硬件信息
    let sys_info = get_system_info().unwrap_or_else(|_| SystemInfo {
        computer_name: "unknown".to_string(),
        system_serial: "unknown".to_string(),
        board_serial: "unknown".to_string(),
    });

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
        computer_name: sys_info.computer_name,
        system_serial: sys_info.system_serial,
        board_serial: sys_info.board_serial,
        offline_uninstall_code_encrypted: None, // 本地收集时不携带
    };
    let record = LogRecord {
        kind: RecordKind::Health,
        timestamp: report.timestamp,
        data: serde_json::to_value(report).context("serialize health")?,
    };
    log_store.lock().await.append_record(record).await?;
    Ok(())
}

/// 离线卸载码存储文件名
const OFFLINE_CODE_SENT_MARKER: &str = "offline-code-sent";

pub async fn push_health(config: &AgentConfig, log_store: &tokio::sync::Mutex<LogStore>) -> Result<()> {
    let mut system = System::new_all();
    system.refresh_all();

    // 获取硬件信息
    let sys_info = get_system_info().unwrap_or_else(|_| SystemInfo {
        computer_name: "unknown".to_string(),
        system_serial: "unknown".to_string(),
        board_serial: "unknown".to_string(),
    });

    // 检查是否需要生成并上报离线卸载码（首次启动时）
    let offline_uninstall_code_encrypted = get_or_generate_offline_code(config, log_store).await?;

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
        computer_name: sys_info.computer_name,
        system_serial: sys_info.system_serial,
        board_serial: sys_info.board_serial,
        offline_uninstall_code_encrypted,
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

/// 获取或生成离线卸载码，并在首次上报时加密后返回
async fn get_or_generate_offline_code(config: &AgentConfig, log_store: &tokio::sync::Mutex<LogStore>) -> Result<Option<String>> {
    let state_dir = crate::config::AgentConfig::state_dir();
    let marker_path = state_dir.join(OFFLINE_CODE_SENT_MARKER);

    // 如果已经上报过离线码，不再重复上报
    if marker_path.exists() {
        return Ok(None);
    }

    // 检查配置中是否已有离线码
    let local_code = config.control.offline_uninstall_code_local.clone();

    // 如果没有，生成新的离线码
    let code = if let Some(existing) = local_code {
        existing
    } else {
        let new_code = generate_offline_uninstall_code();
        // 保存到配置
        let mut updated_config = config.clone();
        updated_config.control.offline_uninstall_code_local = Some(new_code.clone());
        let config_path = crate::config::AgentConfig::config_path();
        let contents = serde_json::to_string_pretty(&updated_config).context("serialize config")?;
        fs::write(&config_path, contents).context("write config")?;
        new_code
    };

    // 加密离线码
    let guard = log_store.lock().await;
    let encrypted = guard.session().encrypt_offline_code(&code)?;

    // 标记已上报（在成功上报后会创建）
    // 这里先返回加密后的码，实际标记由上层调用者创建

    Ok(Some(encrypted))
}

/// 标记离线卸载码已成功上报
pub fn mark_offline_code_sent() -> Result<()> {
    let state_dir = crate::config::AgentConfig::state_dir();
    if let Some(parent) = state_dir.parent() {
        fs::create_dir_all(parent).ok();
    }
    fs::create_dir_all(&state_dir).ok();
    let marker_path = state_dir.join(OFFLINE_CODE_SENT_MARKER);
    fs::write(&marker_path, chrono::Utc::now().to_rfc3339()).context("write marker")?;
    Ok(())
}
