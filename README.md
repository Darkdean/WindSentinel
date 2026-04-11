# WindSentinel 使用文档

## 项目结构
- WindSentinelAgent（Rust 客户端）：`/src`
- WindSentinelAdmin（Python 服务端）：`/server`
- 管理界面静态资源：`/server/static`

## 代码结构树形图
```
vRoutePlan/
├── Cargo.lock
├── Cargo.toml
├── README.md
├── ReadMe_man.MD
├── src/
│   ├── config.rs
│   ├── crypto.rs
│   ├── health.rs
│   ├── lock.rs
│   ├── log_store.rs
│   ├── main.rs
│   ├── network.rs
│   ├── policy.rs
│   ├── process.rs
│   ├── remote_shell.rs
│   └── types.rs
└── server/
    ├── main.py
    ├── models.py
    ├── requirements.txt
    ├── rules/
    │   └── default.yar
    ├── static/
    │   ├── app.js
    │   ├── index.html
    │   └── styles.css
    └── storage.py
```

## 代码文件与函数说明
### WindSentinelAgent（/src）
- config.rs：客户端配置读取与签名校验
  - AgentConfig::load：加载配置文件，支持带签名配置并校验
  - AgentConfig::config_path：生成配置文件路径
  - verify_signature：校验配置签名 HMAC
- crypto.rs：会话加密工具
  - SessionCrypto::new：从 Base64 密钥初始化会话加密
  - SessionCrypto::encrypt：AES-GCM 加密并拼接 nonce
- log_store.rs：本地日志缓存与增量上报
  - LogStore::new：创建日志存储实例
  - LogStore::encrypt_payload：加密任意数据载荷
  - LogStore::append_record：压缩并加密记录写入本地日志
  - LogStore::push_incremental：读取增量日志并上传到服务端
- health.rs：主机健康采集与上报
  - collect_health：采集健康数据并写入日志
  - push_health：加密并上报健康数据
- network.rs：网络连接采集
  - collect_network_events：解析 netstat 输出并记录网络事件
  - split_addr：拆分地址字符串为 IP 与端口
- process.rs：进程快照采集
  - collect_process_events：采集进程快照并记录
- policy.rs：策略拉取与执行
  - PolicyState::new：初始化策略状态
  - is_enabled：判断模块是否启用
  - fetch_and_apply：拉取策略并应用
  - apply_policy：执行 kill、网络阻断、锁定等策略动作
  - apply_block_all：调用 pfctl 设置全量阻断规则
  - apply_block_pids：预留按 PID 阻断接口
- lock.rs：锁定与解锁本地文件
  - lock_home：生成密钥并加密文件，写入锁定元数据
  - unlock_home：解密密钥并还原文件
  - walk_files：遍历目录下文件列表
- remote_shell.rs：远程 Shell 会话
  - ensure_shell：依据策略判断是否启动远程 shell
  - start_shell_session：建立 TCP 连接并转发 shell I/O
  - encrypt_frame：封装加密帧
  - decrypt_frame：解密并解析帧
- main.rs：客户端入口与任务调度
  - main：初始化配置、日志与策略循环任务
- types.rs：日志记录类型
  - LogRecord::error：构造错误类型日志记录

### WindSentinelAdmin（/server）
- main.py：服务端 API 与管理逻辑
  - aesgcm_decrypt：AES-GCM 解密工具
  - aesgcm_encrypt：AES-GCM 加密工具
  - get_signing_key：读取配置签名密钥与 key_id
  - sign_agent_config：生成配置签名包
  - default_agent_config：构造默认 Agent 配置模板
  - agent_binary_path：确定 Agent 二进制路径
  - agent_version：读取 Agent 版本标识
  - build_agent_package_meta：构造包元信息（版本/校验和）
  - load_rules：加载 yara 规则
  - ensure_rules：确保规则编译可用
  - require_auth：校验 Bearer Token
  - require_role：校验角色权限
  - startup：初始化数据库与 shell 服务
  - health：接收健康上报
  - logs：接收日志上报并应用规则
  - policy：返回策略配置
  - admin_login：管理员登录与 MFA 校验
  - admin_ui：返回管理界面入口
  - agent_config_template：获取默认配置模板
  - agent_config_meta：获取包元信息
  - agent_config_templates：列出配置模板
  - agent_config_template_detail：读取单个模板
  - agent_config_template_upsert：保存/更新模板
  - agent_config_template_delete：删除模板
  - agent_config_template_versions：列出模板历史版本
  - agent_config_template_version_detail：读取模板历史版本详情
  - agent_config_template_rollback：回滚模板到历史版本
  - agent_config_templates_export：导出模板集合
  - agent_config_templates_import：导入模板集合
  - agent_config_sign：签名配置预览
  - agent_config_download：下载配置或打包
  - bind_mfa：绑定 MFA
  - change_password：修改密码并校验强度
  - create_user：创建用户
  - users：列出用户
  - remove_user：删除用户
  - query_logs：执行 SQL 查询日志
  - audits：查询审计日志
  - audit_stats：审计统计
  - get_rules：列出规则
  - upsert_rule：保存规则并生成版本
  - export_rules：导出规则（支持筛选）
  - import_rules：导入规则（覆盖/跳过冲突）
  - import_rules_preview：规则导入预览
  - rule_versions：规则版本列表
  - rule_version：读取规则版本内容
  - restore_rule：恢复规则版本
  - rule_diff：规则差异对比
  - groups：列出分组
  - create_group_api：创建分组
  - delete_group_api：删除分组
  - tags：列出标签
  - create_tag_api：创建标签
  - delete_tag_api：删除标签
  - agents：列出 Agent
  - agent_detail：查询 Agent 详情
  - update_agent_profile：更新 Agent 资料
  - update_agent_tags：更新 Agent 标签
  - latest_health：读取最新健康状态
  - set_policy_admin：下发策略到单个 Agent
  - set_policy_group：按分组下发策略
  - set_policy_tag：按标签下发策略
  - set_policy_batch：批量下发策略
  - start_shell：触发远程 shell 会话
  - lock_agent：触发远程锁定
  - unlock_agent：触发远程解锁
  - send_shell：发送 shell 命令
  - recv_shell：拉取 shell 输出
  - shell_history：获取 shell 历史
  - search_shell_history：搜索 shell 历史
  - clear_shell_history：清空 shell 历史
  - export_shell_history：导出 shell 历史
  - parse_records：解析上传日志的加密记录
  - apply_rules：命中规则后应用策略
  - strong_password：强密码校验
  - apply_policy_batch：批量策略写入存储
  - get_user_mfa：读取用户 MFA 密钥
  - shell_server：启动 shell 服务端口
  - handle_shell：处理 shell 握手与会话
  - read_shell_stream：读取 shell 数据流
  - build_frame：封装 AES-GCM 帧
- storage.py：SQLite 数据访问层
  - get_conn：创建数据库连接
  - init_db：初始化数据库表结构
  - ensure_default_admin：写入默认管理员
  - verify_user：校验用户名密码
  - set_user_password：更新密码
  - set_user_mfa：更新 MFA
  - add_user：新增用户
  - list_users：列出用户
  - delete_user：删除用户
  - upsert_config_template：保存/更新配置模板并写入历史
  - list_config_templates：列出模板
  - get_config_template：读取模板
  - delete_config_template：删除模板与历史
  - list_config_template_versions：列出模板历史版本
  - get_config_template_version：读取模板历史版本
  - store_health：保存健康上报
  - store_log：保存日志
  - get_logs_sql：执行自定义 SQL
  - set_policy：写入策略
  - get_policy：读取策略
  - list_agents：列出 Agent 汇总信息
  - get_agent_detail：读取 Agent 详情
  - upsert_agent_profile：更新 Agent 资料
  - list_groups：列出分组
  - create_group：创建分组
  - delete_group：删除分组
  - list_tags：列出标签
  - create_tag：创建标签
  - delete_tag：删除标签
  - set_agent_tags：更新 Agent 标签
  - list_agent_ids_by_group：按分组取 Agent 列表
  - list_agent_ids_by_tag：按标签取 Agent 列表
  - get_latest_health：读取最新健康数据
  - add_audit：写入审计记录
  - list_audits：查询审计记录
  - list_rules：列出规则文件
  - save_rule：保存规则并写入版本
  - list_rule_versions：列出规则版本
  - get_rule_version：读取规则版本
  - get_rule_content：读取当前规则内容
  - restore_rule_version：恢复规则版本
  - list_audit_stats：审计统计
  - generate_token：生成登录 Token
- models.py：API 数据模型定义
  - HealthPayload：健康上报载荷
  - LogPayload：日志上报载荷
  - PolicyResponse：策略响应结构
  - LoginRequest：登录请求
  - ChangePasswordRequest：修改密码请求
  - CreateUserRequest：创建用户请求
  - ShellCommand：远程 shell 指令
  - SqlQuery：日志 SQL 查询
  - RulePayload：规则保存请求
  - AuditQuery：审计查询结构
  - AgentProfilePayload：Agent 资料更新
  - GroupPayload：分组创建请求
  - TagPayload：标签创建请求
  - AgentTagsPayload：Agent 标签更新
  - BatchPolicyPayload：批量策略下发
  - AgentConfigPayload：Agent 配置内容
  - AgentConfigTemplatePayload：模板保存结构
  - AgentConfigTemplateImportPayload：模板导入结构
- rules/default.yar：默认 yara 规则示例
- requirements.txt：服务端依赖列表

### 管理界面（/server/static）
- index.html：管理界面布局与表单结构
- styles.css：管理界面样式
- app.js：管理界面交互逻辑
  - api：封装带鉴权的请求
  - bind：绑定 DOM 事件
  - initDefaults：初始化时间范围与搜索
  - getConfigPayload：读取配置表单值
  - loadConfigTemplate：加载默认配置模板
  - signConfigPreview：签名并预览配置
  - downloadConfig：下载配置或打包
  - readError：读取接口错误响应
  - loadPackageMeta：加载包信息
  - loadConfigTemplates：加载模板列表
  - saveConfigTemplate：保存模板
  - loadSelectedTemplate：加载选中模板
  - deleteSelectedTemplate：删除选中模板
  - startMetaAutoRefresh：自动刷新包信息
  - stopMetaAutoRefresh：停止自动刷新包信息
  - exportTemplates：导出模板
  - importTemplates：导入模板
  - loadTemplateVersions：加载模板历史列表
  - rollbackTemplateVersion：回滚模板历史版本
  - login：登录并加载初始化数据
  - bindMfa：绑定 MFA
  - changePassword：修改密码
  - loadAgents：加载 Agent 列表
  - selectAgent：切换当前 Agent
  - loadHealth：加载健康状态
  - loadGroups：加载分组列表
  - loadTags：加载标签列表
  - loadAgentProfile：加载 Agent 资料
  - saveAgentProfile：保存 Agent 资料
  - createGroup：创建分组
  - deleteGroup：删除分组
  - createTag：创建标签
  - deleteTag：删除标签
  - parseTags：解析标签字符串
  - sendPolicy：向当前 Agent 下发策略
  - sendPolicyToGroup：向分组下发策略
  - sendPolicyToTag：向标签下发策略
  - retryPolicyBatch：重试失败的策略下发
  - applyAgentFilter：应用 Agent 过滤条件
  - resetAgentFilter：重置过滤条件
  - pageAgents：Agent 列表翻页
  - startShell：启动远程 shell
  - lockAgent：锁定 Agent
  - unlockAgent：解锁 Agent
  - runQuery：执行日志 SQL 查询
  - sendShell：发送 shell 命令
  - loadUsers：加载用户列表
  - createUser：创建用户
  - deleteUser：删除用户
  - loadAudits：加载审计日志
  - loadAuditCharts：加载审计图表数据
  - loadRules：加载规则列表
  - selectRule：选择规则与版本列表
  - saveRule：保存规则
  - exportRules：导出规则
  - importRules：导入规则
  - previewImportRules：导入预览
  - restoreRule：恢复规则版本
  - diffRule：计算规则差异
  - loadShellHistory：加载 shell 历史
  - clearShellHistory：清空 shell 历史
  - exportShellHistory：导出 shell 历史
  - searchShellHistory：搜索 shell 历史
  - pageShellHistory：shell 历史翻页
  - loadShellHistoryPage：加载 shell 历史分页
  - drawBarChart：绘制柱状图
  - drawLineChart：绘制折线图
  - renderDiff：渲染规则差异
  - formatBucketLabel：格式化时间桶
  - copyDiff：复制差异内容
  - formatNumber：格式化数值
  - toLocalInput：时间转 input 格式
  - getEpochFromInput：读取时间输入为 epoch
  - validateRange：校验时间范围
  - showToast：显示提示信息
  - copyText：复制文本
  - startShellPoll：轮询 shell 输出

## 快速启动（服务端）
1. 创建虚拟环境并安装依赖

```bash
cd server
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -r requirements.txt --upgrade --force-reinstall
```

2. 启动服务

```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```

3. 管理界面

```
http://<server>:8000/admin/ui/login
http://<server>:8000/admin/ui/app
```
未授权或无权限访问会返回 404。

## 默认账号与安全要求
- 默认管理员：`windmap`
- 默认密码：`admin`
- 首次登录必须绑定 MFA 并修改为强密码
- 强密码要求：长度≥12，且包含大小写字母、数字、符号

## 角色与权限
- 管理员：admin（全部功能）
- 审计员：auditor（日志查询、审计日志、客户端查看）
- 操作员：operator（Agent 管理、策略下发、配置生成、规则配置、客户端查看）

## 关键端口
- 管理 API：`/admin/*`
- 客户端 API：`/api/v1/*`
- 远程 shell 反向连接端口：`9001`

## 规则与审计
- 规则文件目录：`/server/rules/*.yar`
- 规则支持版本历史与对比、恢复
- 审计日志支持筛选与图表统计

## API Key 调用
- 在“API 配置”中创建端点，复制生成的 API Key
- 请求头：`X-API-Key: <key>`
- 功能列表决定可调用的接口，越权访问返回 404

## 日志导出与保留
- 日志导出支持 Kafka / RabbitMQ / ElasticSearch
- 配置示例（Kafka）：
```
{"bootstrap_servers":["127.0.0.1:9092"],"topic":"logs"}
```
- 配置示例（RabbitMQ）：
```
{"url":"amqp://guest:guest@127.0.0.1:5672/","queue":"logs"}
```
- 配置示例（ElasticSearch）：
```
{"url":"http://127.0.0.1:9200","index":"logs"}
```

## 客户端运行说明（WindSentinelAgent）
1. 编译客户端

```bash
cargo build --release
```

2. 运行客户端

```bash
./target/release/WindSentinelAgent
```

3. 运行前准备
- 确保服务端可访问（管理 API 与客户端 API）
- 设置 `WINDSENTINEL_SHARED_KEY_B64` 与服务端保持一致
- macOS 环境需要相应权限（进程/网络监控）

## 打包与部署步骤
### 服务端
1. 安装依赖并启动（推荐系统服务或容器化）
2. 暴露 8000（管理与客户端 API）和 9001（反向 shell）端口
3. 生产环境建议使用反向代理（如 Nginx）并启用 HTTPS

### 客户端
1. 使用 `cargo build --release` 构建二进制
2. 将二进制部署到目标 macOS 主机
3. 通过系统服务（launchd）保持常驻运行

#### launchd 配置示例（客户端）
将以下内容保存为 `/Library/LaunchDaemons/com.windsentinel.agent.plist`，并按需调整路径与环境变量。

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
  <dict>
    <key>Label</key>
    <string>com.windsentinel.agent</string>
    <key>ProgramArguments</key>
    <array>
      <string>/usr/local/bin/WindSentinelAgent</string>
    </array>
    <key>EnvironmentVariables</key>
    <dict>
      <key>WINDSENTINEL_SHARED_KEY_B64</key>
      <string>BASE64_KEY_HERE</string>
    </dict>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/var/log/windsentinel-agent.log</string>
    <key>StandardErrorPath</key>
    <string>/var/log/windsentinel-agent.err</string>
  </dict>
</plist>
```

启用与管理：

```bash
sudo launchctl load /Library/LaunchDaemons/com.windsentinel.agent.plist
sudo launchctl unload /Library/LaunchDaemons/com.windsentinel.agent.plist
sudo launchctl list | grep windsentinel
```

#### HTTPS 反代示例（Nginx）
将以下内容保存为 `/etc/nginx/conf.d/windsentinel.conf`，并替换域名与证书路径。

```nginx
server {
  listen 443 ssl;
  server_name admin.example.com;
  ssl_certificate     /etc/ssl/certs/admin.example.com.crt;
  ssl_certificate_key /etc/ssl/private/admin.example.com.key;

  location / {
    proxy_pass http://127.0.0.1:8000;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
  }
}
```

#### 密钥生成脚本示例
生成 32 字节 Base64 密钥：

```bash
python - <<'PY'
import os, base64
print(base64.b64encode(os.urandom(32)).decode())
PY
```

## 环境变量安全指南
- `WINDSENTINEL_SHARED_KEY_B64` 必须为强随机密钥（32 字节 Base64）
- 不要在仓库中提交密钥或明文配置文件
- 生产环境使用受控的密钥管理（如系统密钥链/环境注入）
- 轮换密钥时要确保客户端与服务端同步更新

## 重要环境变量
- `WINDSENTINEL_SHARED_KEY_B64`：会话密钥（Base64），用于客户端与服务端加密通讯

## curl 接口调用示例
以下示例以 `BASE_URL=http://127.0.0.1:8000` 为例。

### 登录
```bash
curl -s -X POST "$BASE_URL/admin/login" \
  -H "Content-Type: application/json" \
  -d '{"username":"windmap","password":"admin","mfa":null}'
```

### 获取客户端列表
```bash
curl -s "$BASE_URL/admin/agents" \
  -H "Authorization: Bearer $TOKEN"
```

### 查看最新健康状态
```bash
curl -s "$BASE_URL/admin/health/<agent_id>" \
  -H "Authorization: Bearer $TOKEN"
```

### 审计日志筛选
```bash
curl -s "$BASE_URL/admin/audits?limit=100&username=windmap&since=1700000000&until=1800000000" \
  -H "Authorization: Bearer $TOKEN"
```

### 审计统计（图表数据）
```bash
curl -s "$BASE_URL/admin/audits/stats?bucket=day&since=1700000000&until=1800000000" \
  -H "Authorization: Bearer $TOKEN"
```

### 规则列表
```bash
curl -s "$BASE_URL/admin/rules" \
  -H "Authorization: Bearer $TOKEN"
```

### 规则保存
```bash
curl -s -X POST "$BASE_URL/admin/rules" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"demo","content":"rule demo { condition: true }"}'
```

### 规则版本列表
```bash
curl -s "$BASE_URL/admin/rules/demo/versions" \
  -H "Authorization: Bearer $TOKEN"
```

### 规则对比
```bash
curl -s "$BASE_URL/admin/rules/demo/diff?left=current&right=1700000000" \
  -H "Authorization: Bearer $TOKEN"
```

### 规则恢复
```bash
curl -s -X POST "$BASE_URL/admin/rules/demo/restore?version=1700000000" \
  -H "Authorization: Bearer $TOKEN"
```

### 终端历史检索（分页）
```bash
curl -s "$BASE_URL/admin/shell/<agent_id>/history/search?offset=0&limit=100&q=whoami" \
  -H "Authorization: Bearer $TOKEN"
```

### 终端历史导出（CSV/JSON）
```bash
curl -s "$BASE_URL/admin/shell/<agent_id>/history/export?format=json&since=1700000000&until=1800000000" \
  -H "Authorization: Bearer $TOKEN"
```

### 日志 SQL 查询
```bash
curl -s -X POST "$BASE_URL/admin/logs/query" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query":"select * from logs limit 10"}'
```
