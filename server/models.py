from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class HealthPayload(BaseModel):
    agent_id: str
    payload: str


class LogPayload(BaseModel):
    agent_id: str
    payload: Dict[str, Any]


class PolicyResponse(BaseModel):
    enabled_modules: List[str]
    kill_pids: List[int]
    block_network_pids: List[int]
    block_all_network: bool
    lock: Optional[Dict[str, Any]] = None
    unlock: Optional[Dict[str, Any]] = None


class LoginRequest(BaseModel):
    username: str
    password: str
    mfa: Optional[str] = None


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str
    mfa: str


class MfaVerifyRequest(BaseModel):
    code: str


class CreateUserRequest(BaseModel):
    username: str
    password: str
    role: str


class SqlQuery(BaseModel):
    query: str


class RulePayload(BaseModel):
    name: str
    content: str


class AuditQuery(BaseModel):
    limit: int = 200


class AgentProfilePayload(BaseModel):
    display_name: Optional[str] = None
    notes: Optional[str] = None
    group_id: Optional[int] = None


class GroupPayload(BaseModel):
    name: str
    description: Optional[str] = None


class TagPayload(BaseModel):
    name: str


class AgentTagsPayload(BaseModel):
    tags: List[str]


class BatchPolicyPayload(BaseModel):
    agent_ids: List[str]
    policy: PolicyResponse


class AgentConfigPayload(BaseModel):
    agent_id: Optional[str] = None
    server_url: str
    shared_key_b64: str


class AgentConfigTemplatePayload(BaseModel):
    name: str
    config: AgentConfigPayload


class AgentConfigTemplateImportPayload(BaseModel):
    name: str
    config: AgentConfigPayload


class ClientControlTaskRequest(BaseModel):
    task_type: str
    mfa_code: str
    reason: Optional[str] = None
    expires_in_seconds: int = 86400


class OfflineCodeRotateRequest(BaseModel):
    mfa_code: str
    reason: Optional[str] = None


class AgentControlTaskAckPayload(BaseModel):
    status: str
    result_code: Optional[str] = None
    result_message: Optional[str] = None


class ApiEndpointPayload(BaseModel):
    name: str
    role: str
    functions: List[str]
    alias: Optional[str] = None


class LogExportPayload(BaseModel):
    target_type: str
    config: Dict[str, Any]
    enabled: bool = True
    log_types: List[str] = Field(default_factory=lambda: ["health", "client_logs", "audit"])


class LogRetentionPayload(BaseModel):
    max_days: Optional[int] = None
    max_bytes: Optional[int] = None


class LoginBlacklistPayload(BaseModel):
    ip_list: List[str] = Field(default_factory=list)
    device_types: List[str] = Field(default_factory=list)
    ua_keywords: List[str] = Field(default_factory=list)
    browser_list: List[str] = Field(default_factory=list)
    os_list: List[str] = Field(default_factory=list)


class LoginWhitelistPayload(BaseModel):
    ip_list: List[str] = Field(default_factory=list)
