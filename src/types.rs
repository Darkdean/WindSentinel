use serde::{Deserialize, Serialize};

#[derive(Clone, Debug, Serialize, Deserialize)]
pub enum RecordKind {
    Process,
    Network,
    Health,
    Policy,
    Transport,
    Shell,
    Lock,
    Error,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct LogRecord {
    pub kind: RecordKind,
    pub timestamp: i64,
    pub data: serde_json::Value,
}

impl LogRecord {
    pub fn error(kind: RecordKind, message: String) -> Self {
        LogRecord {
            kind,
            timestamp: chrono::Utc::now().timestamp(),
            data: serde_json::json!({ "error": message }),
        }
    }
}
