use anyhow::{anyhow, Context, Result};
use base64::Engine;
use hmac::{Hmac, Mac};
use rand::Rng;
use serde::{Deserialize, Serialize};
use sha2::Sha256;
use std::fs;
use std::path::PathBuf;
use uuid::Uuid;

#[derive(Clone, Debug, Serialize, Deserialize, Default)]
pub struct ControlConfig {
    pub service_name: Option<String>,
    pub offline_code_hash: Option<String>,
    pub offline_code_salt: Option<String>,
    pub offline_code_version: Option<u32>,
    /// AES加密后的离线卸载码（base64编码）
    #[serde(default)]
    pub offline_uninstall_code_encrypted: Option<String>,
    /// 本地存储的离线卸载码（明文，用于本地验证）
    #[serde(default)]
    pub offline_uninstall_code_local: Option<String>,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct AgentConfig {
    pub agent_id: String,
    pub server_url: String,
    pub shared_key_b64: String,
    #[serde(default)]
    pub control: ControlConfig,
}

 impl AgentConfig {
     pub fn load() -> Result<Self> {
         let path = Self::config_path();
        if path.exists() {
            let contents = fs::read_to_string(&path).context("read config")?;
            let value: serde_json::Value =
                serde_json::from_str(&contents).context("parse config")?;
            if value.get("config_json").is_some() {
                let signed: SignedConfig =
                    serde_json::from_value(value).context("parse signed config")?;
                verify_signature(&signed)?;
                let cfg: AgentConfig =
                    serde_json::from_str(&signed.config_json).context("parse config json")?;
                return Ok(cfg);
            }
            let cfg: AgentConfig = serde_json::from_str(&contents).context("parse config")?;
            return Ok(cfg);
        }
        let cfg = AgentConfig {
            agent_id: Uuid::new_v4().to_string(),
            server_url: "https://127.0.0.1:8443".to_string(),
            shared_key_b64: base64::engine::general_purpose::STANDARD.encode([0u8; 32]),
            control: ControlConfig::default(),
        };
        let contents = serde_json::to_string_pretty(&cfg).context("serialize config")?;
        fs::create_dir_all(path.parent().unwrap()).ok();
        fs::write(&path, contents).context("write config")?;
        Ok(cfg)
     }
 
     pub fn config_path() -> PathBuf {
         if let Ok(path) = std::env::var("WINDSENTINEL_AGENT_CONFIG_PATH") {
             return PathBuf::from(path);
         }
         let mut base = dirs::config_dir().unwrap_or_else(|| PathBuf::from("/tmp"));
         base.push("WindSentinelAgent");
         base.push("config.json");
         base
     }

     pub fn state_dir() -> PathBuf {
         if let Ok(path) = std::env::var("WINDSENTINEL_AGENT_STATE_DIR") {
             return PathBuf::from(path);
         }
         let mut base = dirs::config_dir().unwrap_or_else(|| PathBuf::from("/tmp"));
         base.push("WindSentinelAgent");
         base
     }

    pub fn control_state_path() -> PathBuf {
        let mut path = Self::state_dir();
        path.push("control-state.json");
        path
    }

    pub fn uninstall_manifest_path() -> PathBuf {
        let mut path = Self::state_dir();
        path.push("uninstall-manifest.json");
        path
    }

    pub fn service_name(&self) -> String {
        self.control
            .service_name
            .clone()
            .unwrap_or_else(|| "windsentinel-agent".to_string())
    }
}

#[derive(Clone, Debug, Serialize, Deserialize)]
struct SignedConfig {
    config_json: String,
    signature: String,
    signed_at: Option<i64>,
    key_id: Option<String>,
}

fn verify_signature(signed: &SignedConfig) -> Result<()> {
    let key_b64 = std::env::var("WINDSENTINEL_CONFIG_VERIFY_KEY_B64")
        .map_err(|_| anyhow!("missing config verify key"))?;
    let key = base64::engine::general_purpose::STANDARD
        .decode(key_b64.as_bytes())
        .context("decode config verify key")?;
    let mut mac = Hmac::<Sha256>::new_from_slice(&key).context("init hmac")?;
    mac.update(signed.config_json.as_bytes());
    let sig = base64::engine::general_purpose::STANDARD
        .decode(signed.signature.as_bytes())
        .context("decode config signature")?;
    mac.verify_slice(&sig).context("verify config signature")?;
    Ok(())
}

/// 离线卸载码字符集：数字 + 大写字母 + 小写字母
const OFFLINE_CODE_CHARSET: &[u8] = b"0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz";

/// 生成8位离线卸载码（数字 + 大小写字母）
pub fn generate_offline_uninstall_code() -> String {
    let mut rng = rand::thread_rng();
    let code: String = (0..8)
        .map(|_| {
            let idx = rng.gen_range(0..OFFLINE_CODE_CHARSET.len());
            OFFLINE_CODE_CHARSET[idx] as char
        })
        .collect();
    code
}

/// 保存离线卸载码到本地配置
pub fn save_offline_uninstall_code_local(config: &mut AgentConfig, code: &str) -> Result<()> {
    config.control.offline_uninstall_code_local = Some(code.to_string());
    let path = AgentConfig::config_path();
    let contents = serde_json::to_string_pretty(config).context("serialize config")?;
    fs::write(&path, contents).context("write config")?;
    Ok(())
}

/// 验证用户输入的离线卸载码是否正确
pub fn verify_offline_uninstall_code(config: &AgentConfig, user_input: &str) -> bool {
    match &config.control.offline_uninstall_code_local {
        Some(local_code) => local_code == user_input,
        None => false,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_generate_offline_code_length() {
        let code = generate_offline_uninstall_code();
        assert_eq!(code.len(), 8);
    }

    #[test]
    fn test_generate_offline_code_charset() {
        for _ in 0..100 {
            let code = generate_offline_uninstall_code();
            for c in code.chars() {
                assert!(c.is_ascii_alphanumeric(), "Character '{}' not in charset", c);
            }
        }
    }

    #[test]
    fn test_generate_offline_code_uniqueness() {
        let codes: Vec<String> = (0..1000).map(|_| generate_offline_uninstall_code()).collect();
        // 检查生成的码有一定的随机性（至少99%不同）
        let unique_count = codes.iter().collect::<std::collections::HashSet<_>>().len();
        assert!(unique_count > 990, "Generated codes should be mostly unique");
    }

    #[test]
    fn test_verify_offline_code() {
        let code = generate_offline_uninstall_code();
        let config = AgentConfig {
            agent_id: "test".to_string(),
            server_url: "http://test".to_string(),
            shared_key_b64: "test".to_string(),
            control: ControlConfig {
                offline_uninstall_code_local: Some(code.clone()),
                ..Default::default()
            },
        };
        assert!(verify_offline_uninstall_code(&config, &code));
        assert!(!verify_offline_uninstall_code(&config, "wrongcode"));
        assert!(!verify_offline_uninstall_code(&config, ""));
    }
}
