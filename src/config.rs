use anyhow::{anyhow, Context, Result};
use base64::Engine;
use hmac::{Hmac, Mac};
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
