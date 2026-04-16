# WindSentinel 安装包 MD5 校验文件

本文件记录各版本安装包的 MD5 hash 值，用于下载验证和完整性检查。

> **注意：** 每次版本发布时，请更新对应版本的 hash 值。

---

## macOS 版本

### v26

| 平台 | 架构 | 文件路径 | MD5 Hash | 更新日期 |
|------|------|----------|----------|----------|
| macOS | aarch64 | `installPack/macos/26/aarch64/WindSentinel-Agent.pkg` | `06b3c3e298563290825d2634aa892a2c` | 2026-04-16 |

---

## 如何计算 MD5

```bash
# macOS
md5 installPack/macos/26/aarch64/WindSentinel-Agent.pkg

# Linux
md5sum installPack/linux/xx/arch/WindSentinel-Agent.tar.gz
```

---

## 版本历史

| 版本 | 发布日期 | 说明 |
|------|----------|------|
| v26 | 2026-04-16 | 验收测试改进版本：离线卸载码、硬件信息、MFA弹窗、UI重构 |
