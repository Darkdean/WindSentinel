use crate::config::AgentConfig;
use crate::lock;
use crate::log_store::LogStore;
use crate::types::{LogRecord, RecordKind};
use anyhow::{anyhow, Context, Result};
use serde::{Deserialize, Serialize};
use std::collections::HashSet;
use std::process::Command;

#[derive(Clone, Debug, Default)]
pub struct PolicyState {
    pub enabled_modules: HashSet<String>,
    pub last_policy: Option<PolicyResponse>,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct PolicyResponse {
    pub enabled_modules: Vec<String>,
    pub kill_pids: Vec<i32>,
    pub block_network_pids: Vec<i32>,
    pub block_all_network: bool,
    pub start_shell: bool,
    pub lock: Option<LockRequest>,
    pub unlock: Option<UnlockRequest>,
    pub session_key_b64: Option<String>,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct LockRequest {
    pub public_key_pem: String,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct UnlockRequest {
    pub private_key_pem: String,
}

impl PolicyState {
    pub fn new() -> Self {
        PolicyState { enabled_modules: HashSet::new(), last_policy: None }
    }
}

pub async fn is_enabled(state: &tokio::sync::Mutex<PolicyState>, module: &str) -> bool {
    let guard = state.lock().await;
    if guard.enabled_modules.is_empty() {
        return true;
    }
    guard.enabled_modules.contains(module)
}

pub async fn fetch_and_apply(
    config: &AgentConfig,
    state: &tokio::sync::Mutex<PolicyState>,
    log_store: &tokio::sync::Mutex<LogStore>,
) -> Result<()> {
    let client = reqwest::Client::new();
    let resp = client
        .get(format!("{}/api/v1/policy", config.server_url))
        .query(&[("agent_id", &config.agent_id)])
        .send()
        .await
        .context("fetch policy")?;
    if !resp.status().is_success() {
        return Err(anyhow!("policy fetch failed {}", resp.status()));
    }
    let policy: PolicyResponse = resp.json().await.context("parse policy")?;
    {
        let mut guard = state.lock().await;
        guard.enabled_modules = policy.enabled_modules.iter().cloned().collect();
        guard.last_policy = Some(policy.clone());
    }
    apply_policy(config, policy, log_store).await?;
    Ok(())
}

async fn apply_policy(config: &AgentConfig, policy: PolicyResponse, log_store: &tokio::sync::Mutex<LogStore>) -> Result<()> {
    for pid in policy.kill_pids {
        unsafe {
            libc::kill(pid, libc::SIGKILL);
        }
        let record = LogRecord {
            kind: RecordKind::Policy,
            timestamp: chrono::Utc::now().timestamp(),
            data: serde_json::json!({ "action": "kill", "pid": pid }),
        };
        log_store.lock().await.append_record(record).await?;
    }
    if policy.block_all_network {
        apply_block_all(config)?;
        let record = LogRecord {
            kind: RecordKind::Policy,
            timestamp: chrono::Utc::now().timestamp(),
            data: serde_json::json!({ "action": "block_all_network" }),
        };
        log_store.lock().await.append_record(record).await?;
    }
    if !policy.block_network_pids.is_empty() {
        apply_block_pids(config, &policy.block_network_pids)?;
        let record = LogRecord {
            kind: RecordKind::Policy,
            timestamp: chrono::Utc::now().timestamp(),
            data: serde_json::json!({ "action": "block_pids", "pids": policy.block_network_pids }),
        };
        log_store.lock().await.append_record(record).await?;
    }
    if let Some(lock_req) = policy.lock {
        lock::lock_home(&lock_req.public_key_pem, log_store).await?;
    }
    if let Some(unlock_req) = policy.unlock {
        lock::unlock_home(&unlock_req.private_key_pem, log_store).await?;
    }
    Ok(())
}

fn apply_block_all(config: &AgentConfig) -> Result<()> {
    let host = config
        .server_url
        .trim_start_matches("https://")
        .trim_start_matches("http://")
        .split('/')
        .next()
        .unwrap_or("127.0.0.1:8443");
    let rules = format!(
        "block drop all\npass out proto tcp from any to {} keep state\npass in proto tcp from {} to any keep state\n",
        host, host
    );
    let mut child = Command::new("pfctl")
        .args(["-a", "windsentinel", "-f", "-"])
        .stdin(std::process::Stdio::piped())
        .spawn()
        .context("spawn pfctl")?;
    if let Some(mut stdin) = child.stdin.take() {
        use std::io::Write;
        stdin.write_all(rules.as_bytes()).ok();
    }
    Ok(())
}

fn apply_block_pids(_config: &AgentConfig, _pids: &[i32]) -> Result<()> {
    Ok(())
}
