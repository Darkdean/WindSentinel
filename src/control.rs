use crate::config::{AgentConfig, ControlConfig};
use anyhow::{anyhow, Context, Result};
use base64::Engine;
use hmac::{Hmac, Mac};
use serde::{Deserialize, Serialize};
use sha2::Sha256;
use std::fs::{self, OpenOptions};
use std::io::{self, Write};
#[cfg(unix)]
use std::os::unix::process::CommandExt;
use std::path::{Path, PathBuf};
use std::process::{Command, Stdio};
use std::time::{SystemTime, UNIX_EPOCH};

const LOG_PATH: &str = "/tmp/log.dat";
const SYSTEMD_UNIT_DIRS: &[&str] = &[
    "/etc/systemd/system",
    "/usr/lib/systemd/system",
    "/lib/systemd/system",
];
const MACOS_SYSTEM_LAUNCHD_DIR: &str = "/Library/LaunchDaemons";
const MACOS_USER_LAUNCHD_SUBDIR: &str = "Library/LaunchAgents";

fn default_running_state() -> String {
    "running".to_string()
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct ControlState {
    pub service_name: String,
    pub offline_code_hash: String,
    pub offline_code_salt: String,
    pub offline_code_version: u32,
    #[serde(default = "default_running_state")]
    pub current_mode: String,
    #[serde(default)]
    pub last_heartbeat_at: Option<i64>,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
struct ControlStateEnvelope {
    control: Option<ControlState>,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
struct ControlTaskEnvelope {
    task: Option<ControlTask>,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
struct ControlTask {
    id: i64,
    agent_id: String,
    task_type: String,
    status: String,
    payload: serde_json::Value,
    audit_correlation_id: Option<String>,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
struct ControlTaskAckPayload {
    status: String,
    result_code: Option<String>,
    result_message: Option<String>,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
struct ControlManifest {
    agent_id: String,
    server_url: String,
    service_name: String,
    action: String,
    task_id: Option<i64>,
    wait_pid: Option<u32>,
    manifest_path: String,
    config_path: String,
    state_dir: String,
    control_state_path: String,
    log_path: String,
    executable_path: String,
}

pub async fn sync_control_state(config: &AgentConfig) -> Result<()> {
    bootstrap_control_state(config)?;
    refresh_control_state_from_server(config).await?;
    Ok(())
}

pub async fn poll_control_tasks(config: &AgentConfig) -> Result<()> {
    let client = reqwest::Client::new();
    let response = client
        .get(format!("{}/api/v1/control-tasks/next", config.server_url))
        .query(&[("agent_id", &config.agent_id)])
        .send()
        .await
        .context("fetch control task")?;
    if !response.status().is_success() {
        return Err(anyhow!("control task fetch failed {}", response.status()));
    }
    let envelope: ControlTaskEnvelope = response.json().await.context("parse control task")?;
    let Some(task) = envelope.task else {
        return Ok(());
    };
    ack_task(
        config,
        task.id,
        "acknowledged",
        Some("received"),
        Some("control task received"),
    )
    .await
    .ok();
    if task.task_type == "stop" {
        set_current_mode(config, "stopped")?;
        ack_task(
            config,
            task.id,
            "running",
            Some("running"),
            Some("agent entered stopped mode"),
        )
        .await
        .ok();
        ack_task(
            config,
            task.id,
            "completed",
            Some("ok"),
            Some("authorized stop completed"),
        )
        .await
        .ok();
        return Ok(());
    }
    let manifest = write_manifest(
        config,
        &task.task_type,
        Some(task.id),
        Some(std::process::id()),
    )?;
    if let Err(err) = spawn_helper(&manifest) {
        ack_task(
            config,
            task.id,
            "failed",
            Some("spawn_failed"),
            Some(&err.to_string()),
        )
        .await
        .ok();
        return Err(err);
    }
    std::process::exit(0);
}

pub async fn heartbeat(config: &AgentConfig) -> Result<()> {
    let mut state = load_control_state(config)?;
    let client = reqwest::Client::new();
    let response = client
        .post(format!("{}/api/v1/control/heartbeat", config.server_url))
        .json(&serde_json::json!({
            "agent_id": config.agent_id,
            "actual_state": state.current_mode,
        }))
        .send()
        .await
        .context("send control heartbeat")?;
    if !response.status().is_success() {
        return Err(anyhow!("control heartbeat failed {}", response.status()));
    }
    let value: serde_json::Value = response.json().await.context("parse control heartbeat")?;
    if let Some(runtime) = value.get("runtime") {
        if runtime
            .get("desired_state")
            .and_then(|v| v.as_str())
            .unwrap_or("running")
            == "running"
            && state.current_mode == "stopped"
        {
            state.current_mode = default_running_state();
        }
        state.last_heartbeat_at = Some(chrono::Utc::now().timestamp());
        write_control_state(&AgentConfig::control_state_path(), &state)?;
    }
    Ok(())
}

pub fn is_stopped(config: &AgentConfig) -> Result<bool> {
    Ok(load_control_state(config)?.current_mode == "stopped")
}

pub async fn handle_cli(config: &AgentConfig, args: &[String]) -> Result<()> {
    if args.len() >= 3 && args[1] == "control" {
        let action = args[2].as_str();
        let mut provided_code: Option<String> = None;
        let mut idx = 3;
        while idx < args.len() {
            if args[idx] == "--code" && idx + 1 < args.len() {
                provided_code = Some(args[idx + 1].clone());
                idx += 2;
                continue;
            }
            idx += 1;
        }
        match action {
            "stop" | "uninstall" => {
                sync_control_state(config).await.ok();
                let state = load_control_state(config)?;
                let code = provided_code.unwrap_or(prompt_for_code(action)?);
                verify_offline_code(&state, &code)?;
                let manifest = write_manifest(config, action, None, None)?;
                spawn_helper(&manifest)?;
                println!(
                    "已授权，{}流程已启动。",
                    if action == "stop" { "停止" } else { "卸载" }
                );
                return Ok(());
            }
            _ => return Err(anyhow!("unsupported control action")),
        }
    }
    if args.len() >= 3 && args[1] == "--internal-control-helper" {
        return run_control_helper(Path::new(&args[2])).await;
    }
    Err(anyhow!("unsupported control command"))
}

fn bootstrap_control_state(config: &AgentConfig) -> Result<()> {
    let state_path = AgentConfig::control_state_path();
    if let Some(control) = build_state_from_config(&config.control) {
        if let Some(existing) = read_control_state(&state_path)? {
            if existing.offline_code_version >= control.offline_code_version {
                return Ok(());
            }
        }
        write_control_state(&state_path, &control)?;
    }
    Ok(())
}

async fn refresh_control_state_from_server(config: &AgentConfig) -> Result<()> {
    let client = reqwest::Client::new();
    let response = client
        .get(format!(
            "{}/api/v1/control/offline-code-meta",
            config.server_url
        ))
        .query(&[("agent_id", &config.agent_id)])
        .send()
        .await
        .context("fetch control state")?;
    if !response.status().is_success() {
        return Ok(());
    }
    let envelope: ControlStateEnvelope = response.json().await.context("parse control state")?;
    if let Some(control) = envelope.control {
        let path = AgentConfig::control_state_path();
        match read_control_state(&path)? {
            Some(existing) if existing.offline_code_version >= control.offline_code_version => {}
            _ => write_control_state(&path, &control)?,
        }
    }
    Ok(())
}

fn build_state_from_config(control: &ControlConfig) -> Option<ControlState> {
    Some(ControlState {
        service_name: control
            .service_name
            .clone()
            .unwrap_or_else(default_service_name),
        offline_code_hash: control.offline_code_hash.clone()?,
        offline_code_salt: control.offline_code_salt.clone()?,
        offline_code_version: control.offline_code_version?,
        current_mode: default_running_state(),
        last_heartbeat_at: None,
    })
}

fn load_control_state(config: &AgentConfig) -> Result<ControlState> {
    let path = AgentConfig::control_state_path();
    if let Some(state) = read_control_state(&path)? {
        return Ok(state);
    }
    if let Some(state) = build_state_from_config(&config.control) {
        write_control_state(&path, &state)?;
        return Ok(state);
    }
    Err(anyhow!("offline authorization metadata unavailable"))
}

fn read_control_state(path: &Path) -> Result<Option<ControlState>> {
    if !path.exists() {
        return Ok(None);
    }
    let contents = fs::read_to_string(path).context("read control state")?;
    let state = serde_json::from_str(&contents).context("parse control state")?;
    Ok(Some(state))
}

fn write_control_state(path: &Path, state: &ControlState) -> Result<()> {
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent).ok();
    }
    let contents = serde_json::to_string_pretty(state).context("serialize control state")?;
    fs::write(path, contents).context("write control state")?;
    Ok(())
}

fn set_current_mode(config: &AgentConfig, mode: &str) -> Result<()> {
    let mut state = load_control_state(config)?;
    state.current_mode = mode.to_string();
    write_control_state(&AgentConfig::control_state_path(), &state)
}

fn prompt_for_code(action: &str) -> Result<String> {
    print!(
        "请输入离线授权码以{}Agent: ",
        if action == "stop" { "停止" } else { "卸载" }
    );
    io::stdout().flush().ok();
    let mut input = String::new();
    io::stdin()
        .read_line(&mut input)
        .context("read authorization code")?;
    let code = input.trim().to_string();
    if code.is_empty() {
        return Err(anyhow!("authorization code is empty"));
    }
    Ok(code)
}

fn verify_offline_code(state: &ControlState, code: &str) -> Result<()> {
    let derived = derive_offline_code_hash(code, &state.offline_code_salt)?;
    if derived != state.offline_code_hash {
        return Err(anyhow!("invalid offline authorization code"));
    }
    Ok(())
}

fn derive_offline_code_hash(code: &str, salt: &str) -> Result<String> {
    let password = format!("{}:{}", salt, code);
    let derived = pbkdf2_sha256(password.as_bytes(), salt.as_bytes(), 200_000, 32)?;
    Ok(base64::engine::general_purpose::STANDARD.encode(derived))
}

fn pbkdf2_sha256(password: &[u8], salt: &[u8], iterations: u32, dklen: usize) -> Result<Vec<u8>> {
    let mut out = Vec::with_capacity(dklen);
    let blocks = (dklen + 31) / 32;
    for block_num in 1..=blocks {
        let mut mac = Hmac::<Sha256>::new_from_slice(password).context("init pbkdf2 mac")?;
        mac.update(salt);
        mac.update(&(block_num as u32).to_be_bytes());
        let mut u = mac.finalize().into_bytes().to_vec();
        let mut t = u.clone();
        for _ in 1..iterations {
            let mut mac =
                Hmac::<Sha256>::new_from_slice(password).context("init pbkdf2 round mac")?;
            mac.update(&u);
            u = mac.finalize().into_bytes().to_vec();
            for (ti, ui) in t.iter_mut().zip(u.iter()) {
                *ti ^= *ui;
            }
        }
        out.extend_from_slice(&t);
    }
    out.truncate(dklen);
    Ok(out)
}

fn write_manifest(
    config: &AgentConfig,
    action: &str,
    task_id: Option<i64>,
    wait_pid: Option<u32>,
) -> Result<ControlManifest> {
    let manifest_path = AgentConfig::uninstall_manifest_path();
    if let Some(parent) = manifest_path.parent() {
        fs::create_dir_all(parent).ok();
    }
    let executable_path = std::env::current_exe().context("resolve current exe")?;
    let manifest = ControlManifest {
        agent_id: config.agent_id.clone(),
        server_url: config.server_url.clone(),
        service_name: config.service_name(),
        action: action.to_string(),
        task_id,
        wait_pid,
        manifest_path: manifest_path.to_string_lossy().to_string(),
        config_path: AgentConfig::config_path().to_string_lossy().to_string(),
        state_dir: AgentConfig::state_dir().to_string_lossy().to_string(),
        control_state_path: AgentConfig::control_state_path()
            .to_string_lossy()
            .to_string(),
        log_path: LOG_PATH.to_string(),
        executable_path: executable_path.to_string_lossy().to_string(),
    };
    let contents = serde_json::to_string_pretty(&manifest).context("serialize manifest")?;
    fs::write(&manifest_path, contents).context("write manifest")?;
    Ok(manifest)
}

fn spawn_helper(manifest: &ControlManifest) -> Result<()> {
    let current_exe = std::env::current_exe().context("resolve helper exe")?;
    let helper_log_path = helper_log_path(manifest);
    if let Some(parent) = helper_log_path.parent() {
        fs::create_dir_all(parent).ok();
    }
    let helper_log = OpenOptions::new()
        .create(true)
        .append(true)
        .open(&helper_log_path)
        .context("open helper log")?;
    let helper_err = helper_log
        .try_clone()
        .context("clone helper log handle")?;
    let mut command = Command::new(current_exe);
    command
        .arg("--internal-control-helper")
        .arg(&manifest.manifest_path)
        .stdin(Stdio::null())
        .stdout(Stdio::from(helper_log))
        .stderr(Stdio::from(helper_err));
    #[cfg(unix)]
    {
        unsafe {
            command.pre_exec(|| {
                if libc::setsid() == -1 {
                    return Err(std::io::Error::last_os_error());
                }
                Ok(())
            });
        }
    }
    command.spawn().context("spawn control helper")?;
    Ok(())
}

async fn run_control_helper(manifest_path: &Path) -> Result<()> {
    let contents = fs::read_to_string(manifest_path).context("read manifest")?;
    let manifest: ControlManifest = serde_json::from_str(&contents).context("parse manifest")?;
    if let Some(pid) = manifest.wait_pid {
        wait_for_pid_exit(pid);
    }
    if let Some(task_id) = manifest.task_id {
        ack_task_by_manifest(
            &manifest,
            task_id,
            "running",
            Some("running"),
            Some("helper started"),
        )
        .await
        .ok();
    }
    let result = match manifest.action.as_str() {
        "stop" => perform_stop(&manifest),
        "uninstall" => perform_uninstall(&manifest),
        other => Err(anyhow!("unsupported helper action {}", other)),
    };
    match result {
        Ok(message) => {
            if let Some(task_id) = manifest.task_id {
                let status = if manifest.action == "stop" {
                    "completed"
                } else {
                    "completed"
                };
                ack_task_by_manifest(&manifest, task_id, status, Some("ok"), Some(&message))
                    .await
                    .ok();
            }
            cleanup_manifest_file(&manifest);
            Ok(())
        }
        Err(err) => {
            if let Some(task_id) = manifest.task_id {
                ack_task_by_manifest(
                    &manifest,
                    task_id,
                    "failed",
                    Some("helper_failed"),
                    Some(&err.to_string()),
                )
                .await
                .ok();
            }
            cleanup_manifest_file(&manifest);
            Err(err)
        }
    }
}

fn wait_for_pid_exit(pid: u32) {
    for _ in 0..50 {
        let proc_path = PathBuf::from(format!("/proc/{}", pid));
        if !proc_path.exists() {
            break;
        }
        std::thread::sleep(std::time::Duration::from_millis(100));
    }
}

fn perform_stop(manifest: &ControlManifest) -> Result<String> {
    if cfg!(target_os = "macos") {
        terminate_agent_processes(&manifest.executable_path)?;
    } else {
        run_systemctl(&["stop", &manifest.service_name]);
    }
    Ok("authorized stop completed".to_string())
}

fn perform_uninstall(manifest: &ControlManifest) -> Result<String> {
    if cfg!(target_os = "macos")
        && requires_privileged_macos_cleanup(manifest)
        && (!is_running_as_root() || manifest.task_id.is_some())
    {
        run_macos_privileged_uninstall(manifest)?;
        return Ok("authorized uninstall completed".to_string());
    }
    if cfg!(target_os = "macos") {
        stop_launchd_service(&manifest.service_name);
        terminate_agent_processes(&manifest.executable_path)?;
        for path in launchd_plist_candidates(&manifest.service_name) {
            remove_path_best_effort(&path);
        }
    } else {
        run_systemctl(&["stop", &manifest.service_name]);
        run_systemctl(&["disable", &manifest.service_name]);
        terminate_agent_processes(&manifest.executable_path)?;
        for dir in SYSTEMD_UNIT_DIRS {
            let path = PathBuf::from(dir).join(format!("{}.service", manifest.service_name));
            remove_path_best_effort(&path);
        }
        run_systemctl(&["daemon-reload"]);
        run_systemctl(&["reset-failed", &manifest.service_name]);
    }

    let _ = std::env::set_current_dir("/tmp");
    remove_path_best_effort(Path::new(&manifest.log_path));
    remove_path_best_effort(Path::new(&manifest.control_state_path));
    remove_path_best_effort(Path::new(&manifest.config_path));
    remove_path_best_effort(Path::new(&manifest.executable_path));
    remove_path_best_effort(Path::new(&manifest.state_dir));
    if let Some(root_dir) = Path::new(&manifest.state_dir).parent() {
        remove_path_best_effort(root_dir);
    }
    Ok("authorized uninstall completed".to_string())
}

fn run_systemctl(args: &[&str]) {
    let _ = Command::new("systemctl").args(args).status();
}

fn default_service_name() -> String {
    if cfg!(target_os = "macos") {
        "com.windsentinel.agent".to_string()
    } else {
        "windsentinel-agent".to_string()
    }
}

fn is_running_as_root() -> bool {
    #[cfg(unix)]
    {
        unsafe { libc::geteuid() == 0 }
    }
    #[cfg(not(unix))]
    {
        false
    }
}

fn requires_privileged_macos_cleanup(manifest: &ControlManifest) -> bool {
    manifest.executable_path.starts_with("/Library/") || manifest.state_dir.starts_with("/Library/")
}

fn stop_launchd_service(service_name: &str) {
    let _ = Command::new("launchctl")
        .args([
            "bootout",
            "system",
            &format!("{}/{}.plist", MACOS_SYSTEM_LAUNCHD_DIR, service_name),
        ])
        .status();
    for path in launchd_plist_candidates(service_name) {
        let _ = Command::new("launchctl")
            .args(["unload", path.to_string_lossy().as_ref()])
            .status();
    }
}

fn launchd_plist_candidates(service_name: &str) -> Vec<PathBuf> {
    let mut paths = vec![PathBuf::from(MACOS_SYSTEM_LAUNCHD_DIR).join(format!("{}.plist", service_name))];
    if let Some(home) = dirs::home_dir() {
        paths.push(home.join(MACOS_USER_LAUNCHD_SUBDIR).join(format!("{}.plist", service_name)));
    }
    paths
}

fn run_macos_privileged_uninstall(manifest: &ControlManifest) -> Result<()> {
    let script_path = write_privileged_cleanup_script(manifest)?;
    let command = format!("/bin/bash {}", shell_escape(&script_path.to_string_lossy()));
    let status = if manifest.task_id.is_some() {
        run_console_user_osascript(&command)?
    } else {
        Command::new("osascript")
            .arg("-e")
            .arg(format!(
                "do shell script {} with administrator privileges",
                apple_script_string(&command)
            ))
            .status()
            .context("run privileged uninstall osascript")?
    };
    if !status.success() {
        return Err(anyhow!("privileged uninstall was not completed"));
    }
    let _ = fs::remove_file(script_path);
    Ok(())
}

fn write_privileged_cleanup_script(manifest: &ControlManifest) -> Result<PathBuf> {
    let stamp = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default()
        .as_secs();
    let path = PathBuf::from(format!("/tmp/windsentinel-privileged-uninstall-{}.sh", stamp));
    let launchd_plist = PathBuf::from(MACOS_SYSTEM_LAUNCHD_DIR).join(format!("{}.plist", manifest.service_name));
    let script = format!(
        r#"#!/bin/bash
set -euo pipefail
launchctl bootout system {plist} >/dev/null 2>&1 || true
pkill -TERM -f {exe} >/dev/null 2>&1 || true
sleep 1
pkill -9 -f {exe} >/dev/null 2>&1 || true
rm -f {plist}
rm -rf {root}
"#,
        plist = shell_escape(&launchd_plist.to_string_lossy()),
        exe = shell_escape(&manifest.executable_path),
        root = shell_escape(
            &Path::new(&manifest.state_dir)
                .parent()
                .unwrap_or_else(|| Path::new(&manifest.state_dir))
                .to_string_lossy()
        ),
    );
    fs::write(&path, script).context("write privileged cleanup script")?;
    Ok(path)
}

fn shell_escape(value: &str) -> String {
    let escaped = value.replace('\'', "'\\''");
    format!("'{}'", escaped)
}

fn apple_script_string(value: &str) -> String {
    let escaped = value.replace('\\', "\\\\").replace('"', "\\\"");
    format!("\"{}\"", escaped)
}

fn run_console_user_osascript(command: &str) -> Result<std::process::ExitStatus> {
    let output = Command::new("stat")
        .args(["-f%Su", "/dev/console"])
        .output()
        .context("read console user")?;
    let console_user = String::from_utf8_lossy(&output.stdout).trim().to_string();
    if console_user.is_empty() || console_user == "root" {
        return Command::new("osascript")
            .arg("-e")
            .arg(format!(
                "do shell script {} with administrator privileges",
                apple_script_string(command)
            ))
            .status()
            .context("run privileged uninstall osascript");
    }
    let uid_output = Command::new("id")
        .args(["-u", &console_user])
        .output()
        .context("read console user uid")?;
    let uid = String::from_utf8_lossy(&uid_output.stdout).trim().to_string();
    let wrapped = format!(
        "do shell script {} with administrator privileges",
        apple_script_string(command)
    );
    Command::new("launchctl")
        .args(["asuser", &uid, "sudo", "-u", &console_user, "osascript", "-e", &wrapped])
        .status()
        .context("run console-user privileged uninstall osascript")
}

fn remove_path_best_effort(path: &Path) {
    if !path.exists() {
        return;
    }
    if path.is_dir() {
        let _ = fs::remove_dir_all(path);
    } else {
        let _ = fs::remove_file(path);
    }
}

fn cleanup_manifest_file(manifest: &ControlManifest) {
    let _ = fs::remove_file(&manifest.manifest_path);
}

fn terminate_agent_processes(executable_path: &str) -> Result<()> {
    let self_pid = std::process::id();
    let output = Command::new("ps")
        .args(["-axo", "pid=,command="])
        .output()
        .context("list agent processes")?;
    let stdout = String::from_utf8_lossy(&output.stdout);
    let mut pids = Vec::new();
    for line in stdout.lines() {
        let trimmed = line.trim();
        if trimmed.is_empty() {
            continue;
        }
        let mut parts = trimmed.splitn(2, ' ');
        let Some(pid_str) = parts.next() else { continue };
        let command = parts.next().unwrap_or("");
        let Ok(pid) = pid_str.trim().parse::<u32>() else { continue };
        if pid == self_pid {
            continue;
        }
        if command.contains(executable_path) || command.contains("windsentinel_agent") {
            pids.push(pid);
        }
    }
    for pid in &pids {
        unsafe {
            libc::kill(*pid as i32, libc::SIGTERM);
        }
    }
    std::thread::sleep(std::time::Duration::from_secs(1));
    for pid in &pids {
        if process_exists(*pid) {
            unsafe {
                libc::kill(*pid as i32, libc::SIGKILL);
            }
        }
    }
    std::thread::sleep(std::time::Duration::from_secs(1));
    let survivors: Vec<u32> = pids.into_iter().filter(|pid| process_exists(*pid)).collect();
    if !survivors.is_empty() {
        return Err(anyhow!("agent processes still running: {:?}", survivors));
    }
    Ok(())
}

fn process_exists(pid: u32) -> bool {
    Command::new("kill")
        .args(["-0", &pid.to_string()])
        .status()
        .map(|status| status.success())
        .unwrap_or(false)
}

fn helper_log_path(manifest: &ControlManifest) -> PathBuf {
    let state_dir = PathBuf::from(&manifest.state_dir);
    if let Some(parent) = state_dir.parent() {
        return parent.join("logs").join("control-helper.log");
    }
    PathBuf::from("/tmp/windsentinel-control-helper.log")
}

async fn ack_task(
    config: &AgentConfig,
    task_id: i64,
    status: &str,
    result_code: Option<&str>,
    result_message: Option<&str>,
) -> Result<()> {
    let manifest = ControlManifest {
        agent_id: config.agent_id.clone(),
        server_url: config.server_url.clone(),
        service_name: config.service_name(),
        action: String::new(),
        task_id: Some(task_id),
        wait_pid: None,
        manifest_path: String::new(),
        config_path: AgentConfig::config_path().to_string_lossy().to_string(),
        state_dir: AgentConfig::state_dir().to_string_lossy().to_string(),
        control_state_path: AgentConfig::control_state_path()
            .to_string_lossy()
            .to_string(),
        log_path: LOG_PATH.to_string(),
        executable_path: String::new(),
    };
    ack_task_by_manifest(&manifest, task_id, status, result_code, result_message).await
}

async fn ack_task_by_manifest(
    manifest: &ControlManifest,
    task_id: i64,
    status: &str,
    result_code: Option<&str>,
    result_message: Option<&str>,
) -> Result<()> {
    let client = reqwest::Client::new();
    let payload = ControlTaskAckPayload {
        status: status.to_string(),
        result_code: result_code.map(|s| s.to_string()),
        result_message: result_message.map(|s| s.to_string()),
    };
    let response = client
        .post(format!(
            "{}/api/v1/control-tasks/{}/ack",
            manifest.server_url, task_id
        ))
        .json(&payload)
        .send()
        .await
        .context("ack control task")?;
    if !response.status().is_success() {
        return Err(anyhow!("ack control task failed {}", response.status()));
    }
    Ok(())
}
