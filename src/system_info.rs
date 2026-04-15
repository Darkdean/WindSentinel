use anyhow::{Context, Result};
use std::process::Command;

/// 系统硬件信息结构
#[derive(Debug, Clone)]
pub struct SystemInfo {
    pub computer_name: String,
    pub system_serial: String,
    pub board_serial: String,
}

/// 获取计算机名
pub fn get_computer_name() -> Result<String> {
    if cfg!(target_os = "macos") {
        let output = Command::new("hostname")
            .arg("-s")
            .output()
            .context("run hostname")?;
        let name = String::from_utf8_lossy(&output.stdout).trim().to_string();
        if !name.is_empty() {
            return Ok(name);
        }
        // fallback: scutil
        let output = Command::new("scutil")
            .arg("--get")
            .arg("ComputerName")
            .output()
            .context("run scutil")?;
        Ok(String::from_utf8_lossy(&output.stdout).trim().to_string())
    } else {
        let output = Command::new("hostname")
            .output()
            .context("run hostname")?;
        Ok(String::from_utf8_lossy(&output.stdout).trim().to_string())
    }
}

/// 获取系统序列号
pub fn get_system_serial_number() -> Result<String> {
    if cfg!(target_os = "macos") {
        // macOS: 使用 ioreg 获取 IOPlatformSerialNumber
        let output = Command::new("ioreg")
            .arg("-l")
            .output()
            .context("run ioreg")?;
        let stdout = String::from_utf8_lossy(&output.stdout);
        for line in stdout.lines() {
            if line.contains("IOPlatformSerialNumber") {
                // 提取序列号，格式通常是 "IOPlatformSerialNumber" = "XXXXXXXXXX"
                let parts: Vec<&str> = line.split('"').collect();
                if parts.len() >= 4 {
                    return Ok(parts[parts.len() - 2].to_string());
                }
            }
        }
        // fallback: system_profiler
        let output = Command::new("system_profiler")
            .arg("SPHardwareDataType")
            .output()
            .context("run system_profiler")?;
        let stdout = String::from_utf8_lossy(&output.stdout);
        for line in stdout.lines() {
            if line.contains("Serial Number") {
                let parts: Vec<&str> = line.split(':').collect();
                if parts.len() >= 2 {
                    return Ok(parts[1].trim().to_string());
                }
            }
        }
        Ok("unknown".to_string())
    } else {
        // Linux: 尝试 dmidecode（需要 root 权限）
        let output = Command::new("dmidecode")
            .arg("-s")
            .arg("system-serial-number")
            .output();
        if let Ok(output) = output {
            if output.status.success() {
                let serial = String::from_utf8_lossy(&output.stdout).trim().to_string();
                if !serial.is_empty() && serial != "None" && serial != "To Be Filled By O.E.M." {
                    return Ok(serial);
                }
            }
        }
        // fallback: /etc/machine-id
        if let Ok(contents) = std::fs::read_to_string("/etc/machine-id") {
            return Ok(contents.trim().to_string());
        }
        Ok("unknown".to_string())
    }
}

/// 获取主板序列号
pub fn get_board_serial_number() -> Result<String> {
    if cfg!(target_os = "macos") {
        // macOS: 主板序列号通常与系统序列号相同或无法单独获取
        // 使用 system_profiler 尝试获取
        let output = Command::new("system_profiler")
            .arg("SPHardwareDataType")
            .output()
            .context("run system_profiler")?;
        let stdout = String::from_utf8_lossy(&output.stdout);
        for line in stdout.lines() {
            if line.contains("Board Serial") || line.contains("Serial Number (system)") {
                let parts: Vec<&str> = line.split(':').collect();
                if parts.len() >= 2 {
                    return Ok(parts[1].trim().to_string());
                }
            }
        }
        // fallback: 返回系统序列号
        get_system_serial_number()
    } else {
        // Linux: dmidecode
        let output = Command::new("dmidecode")
            .arg("-s")
            .arg("baseboard-serial-number")
            .output();
        if let Ok(output) = output {
            if output.status.success() {
                let serial = String::from_utf8_lossy(&output.stdout).trim().to_string();
                if !serial.is_empty() && serial != "None" && serial != "To Be Filled By O.E.M." {
                    return Ok(serial);
                }
            }
        }
        Ok("unknown".to_string())
    }
}

/// 获取完整的系统信息
pub fn get_system_info() -> Result<SystemInfo> {
    Ok(SystemInfo {
        computer_name: get_computer_name().unwrap_or_else(|_| "unknown".to_string()),
        system_serial: get_system_serial_number().unwrap_or_else(|_| "unknown".to_string()),
        board_serial: get_board_serial_number().unwrap_or_else(|_| "unknown".to_string()),
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_get_computer_name() {
        // 基本功能测试 - 不验证具体值，只验证不崩溃
        let result = get_computer_name();
        assert!(result.is_ok());
        let name = result.unwrap();
        assert!(!name.is_empty());
    }

    #[test]
    fn test_get_system_info() {
        let result = get_system_info();
        assert!(result.is_ok());
        let info = result.unwrap();
        assert!(!info.computer_name.is_empty());
        // serial 可能是 "unknown"，这也是有效结果
    }
}
