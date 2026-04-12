use anyhow::{Context, Result};
use std::path::PathBuf;
use std::sync::Arc;
use tokio::sync::Mutex;

mod config;
mod control;
mod crypto;
mod health;
mod lock;
mod log_store;
mod network;
mod policy;
mod process;
mod types;

use config::AgentConfig;
use log_store::LogStore;
use policy::PolicyState;
use types::{LogRecord, RecordKind};

#[tokio::main]
async fn main() -> Result<()> {
    let args: Vec<String> = std::env::args().collect();
    let config = AgentConfig::load().context("load config")?;
    if args.len() > 1 {
        return control::handle_cli(&config, &args).await;
    }
    let session = crypto::SessionCrypto::new(&config.shared_key_b64)?;
    let log_path = PathBuf::from("/tmp/log.dat");
    let log_store = Arc::new(Mutex::new(LogStore::new(log_path, session.clone())));
    let policy_state = Arc::new(Mutex::new(PolicyState::new()));

    let log_store_clone = log_store.clone();
    let config_clone = config.clone();
    let policy_clone = policy_state.clone();
    tokio::spawn(async move {
        loop {
            let stopped = control::is_stopped(&config_clone).unwrap_or(false);
            if !stopped && policy::is_enabled(&policy_clone, "process").await {
                if let Err(err) =
                    process::collect_process_events(&config_clone, &log_store_clone).await
                {
                    let _ = log_store_clone
                        .lock()
                        .await
                        .append_record(LogRecord::error(RecordKind::Process, err.to_string()))
                        .await;
                }
            }
            if !stopped && policy::is_enabled(&policy_clone, "network").await {
                if let Err(err) =
                    network::collect_network_events(&config_clone, &log_store_clone).await
                {
                    let _ = log_store_clone
                        .lock()
                        .await
                        .append_record(LogRecord::error(RecordKind::Network, err.to_string()))
                        .await;
                }
            }
            if !stopped && policy::is_enabled(&policy_clone, "health").await {
                if let Err(err) = health::collect_health(&config_clone, &log_store_clone).await {
                    let _ = log_store_clone
                        .lock()
                        .await
                        .append_record(LogRecord::error(RecordKind::Health, err.to_string()))
                        .await;
                }
            }
            tokio::time::sleep(std::time::Duration::from_secs(5)).await;
        }
    });

    let log_store_clone = log_store.clone();
    let config_clone = config.clone();
    let policy_clone = policy_state.clone();
    tokio::spawn(async move {
        loop {
            let _ = control::sync_control_state(&config_clone).await;
            let stopped = control::is_stopped(&config_clone).unwrap_or(false);
            if stopped {
                if let Err(err) = control::heartbeat(&config_clone).await {
                    let _ = log_store_clone
                        .lock()
                        .await
                        .append_record(LogRecord::error(RecordKind::Control, err.to_string()))
                        .await;
                }
            } else {
                if let Err(err) = log_store_clone
                    .lock()
                    .await
                    .push_incremental(&config_clone)
                    .await
                {
                    let _ = log_store_clone
                        .lock()
                        .await
                        .append_record(LogRecord::error(RecordKind::Transport, err.to_string()))
                        .await;
                }
                if policy::is_enabled(&policy_clone, "health").await {
                    if let Err(err) = health::push_health(&config_clone, &log_store_clone).await {
                        let _ = log_store_clone
                            .lock()
                            .await
                            .append_record(LogRecord::error(RecordKind::Health, err.to_string()))
                            .await;
                    }
                }
                if let Err(err) =
                    policy::fetch_and_apply(&config_clone, &policy_clone, &log_store_clone).await
                {
                    let _ = log_store_clone
                        .lock()
                        .await
                        .append_record(LogRecord::error(RecordKind::Policy, err.to_string()))
                        .await;
                }
            }
            if let Err(err) = control::poll_control_tasks(&config_clone).await {
                let _ = log_store_clone
                    .lock()
                    .await
                    .append_record(LogRecord::error(RecordKind::Control, err.to_string()))
                    .await;
            }
            tokio::time::sleep(std::time::Duration::from_secs(5)).await;
        }
    });

    loop {
        tokio::time::sleep(std::time::Duration::from_secs(60)).await;
    }
}
