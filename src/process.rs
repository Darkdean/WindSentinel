use crate::config::AgentConfig;
use crate::log_store::LogStore;
use crate::types::{LogRecord, RecordKind};
use anyhow::{Context, Result};
use serde::Serialize;
use sha2::{Digest, Sha256};
use std::collections::HashMap;
use std::fs;
use sysinfo::{ProcessesToUpdate, System};

#[derive(Serialize)]
struct ProcessSnapshot {
    pid: i32,
    action: String,
    hash: Option<String>,
    args: Vec<String>,
    parent_pid: Option<i32>,
    parent_hash: Option<String>,
    parent_args: Vec<String>,
    resource_kind: Option<String>,
    resource_detail: Option<String>,
    timestamp: i64,
}

pub async fn collect_process_events(_config: &AgentConfig, log_store: &tokio::sync::Mutex<LogStore>) -> Result<()> {
    let mut system = System::new_all();
    system.refresh_processes(ProcessesToUpdate::All, true);
    let mut parent_map: HashMap<i32, (Option<std::path::PathBuf>, Vec<String>)> = HashMap::new();
    for (pid, proc_) in system.processes() {
        parent_map.insert(
            pid.as_u32() as i32,
            (
                proc_.exe().map(|p| p.to_path_buf()),
                proc_.cmd().iter().map(|s| s.to_string_lossy().to_string()).collect(),
            ),
        );
    }
    for (pid, proc_) in system.processes() {
        let pid_i = pid.as_u32() as i32;
        let exe = proc_.exe().map(|p| p.to_path_buf());
        let hash = exe
            .as_ref()
            .and_then(|path| fs::read(path).ok())
            .map(|bytes| format!("{:x}", Sha256::digest(&bytes)));
        let parent_pid = proc_.parent().map(|p| p.as_u32() as i32);
        let (parent_hash, parent_args) = if let Some(ppid) = parent_pid {
            if let Some((parent_exe, parent_args)) = parent_map.get(&ppid) {
                let parent_hash = parent_exe
                    .as_ref()
                    .and_then(|path| fs::read(path).ok())
                    .map(|bytes| format!("{:x}", Sha256::digest(&bytes)));
                (parent_hash, parent_args.clone())
            } else {
                (None, Vec::new())
            }
        } else {
            (None, Vec::new())
        };
        let snapshot = ProcessSnapshot {
            pid: pid_i,
            action: "snapshot".to_string(),
            hash,
            args: proc_.cmd().iter().map(|s| s.to_string_lossy().to_string()).collect(),
            parent_pid,
            parent_hash,
            parent_args,
            resource_kind: None,
            resource_detail: None,
            timestamp: chrono::Utc::now().timestamp(),
        };
        let record = LogRecord {
            kind: RecordKind::Process,
            timestamp: snapshot.timestamp,
            data: serde_json::to_value(snapshot).context("serialize snapshot")?,
        };
        log_store.lock().await.append_record(record).await?;
    }
    Ok(())
}
