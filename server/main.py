import asyncio
import base64
import gzip
import json
import os
import hashlib
import hmac
import time
import io
import csv
import difflib
import zipfile
import uuid
import logging
import secrets
import traceback
from typing import Any, Dict, Optional

import pyotp
import qrcode
import qrcode.image.pure
import yara
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from fastapi import Depends, FastAPI, HTTPException, Header, Request
from fastapi.responses import PlainTextResponse, FileResponse, StreamingResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from config import DEBUG, LOG_LEVEL, LOG_FILE, LOG_REQUEST_BODY, MFA_ISSUER
from models import (
    AgentProfilePayload,
    AgentTagsPayload,
    AgentControlBootstrapPayload,
    AgentConfigPayload,
    AgentConfigTemplatePayload,
    AgentConfigTemplateImportPayload,
    AgentControlTaskAckPayload,
    ApiEndpointPayload,
    BatchPolicyPayload,
    ChangePasswordRequest,
    ClientControlTaskRequest,
    CreateUserRequest,
    GroupPayload,
    HealthPayload,
    LogPayload,
    LoginRequest,
    MfaVerifyRequest,
    OfflineCodeRotateRequest,
    PolicyResponse,
    RulePayload,
    SqlQuery,
    TagPayload,
    LogExportPayload,
    LogRetentionPayload,
    LoginBlacklistPayload,
    LoginWhitelistPayload,
)
from storage import (
    add_audit,
    add_user,
    create_api_endpoint,
    create_group,
    create_agent_control_task,
    create_tag,
    cleanup_inactive_agent_records,
    delete_user,
    delete_agent_record,
    delete_group,
    delete_api_endpoint,
    delete_tag,
    generate_token,
    get_logs_sql,
    get_agent_detail,
    get_agent_offline_code,
    get_agent_runtime_state,
    get_next_agent_control_task,
    get_policy,
    get_user_mfa as get_user_mfa_secret,
    get_latest_health,
    get_api_endpoint_by_key_hash,
    get_api_endpoint,
    init_db,
    list_agents,
    list_agent_control_tasks,
    list_audits,
    list_api_endpoints,
    list_groups,
    list_rules,
    list_agent_ids_by_group,
    list_agent_ids_by_tag,
    list_tags,
    list_users,
    list_config_templates,
    get_config_template,
    upsert_config_template,
    delete_config_template,
    list_config_template_versions,
    get_config_template_version,
    list_rule_versions,
    get_rule_version,
    get_rule_content,
    restore_rule_version,
    save_rule,
    list_audit_stats,
    create_log_export,
    list_log_exports,
    delete_log_export,
    set_log_export_enabled,
    set_log_retention,
    set_login_blacklist,
    set_login_whitelist,
    get_log_retention,
    get_login_blacklist,
    get_login_whitelist,
    purge_logs_older_than,
    purge_logs_by_size,
    set_policy,
    set_agent_tags,
    set_user_mfa,
    set_user_password,
    store_health,
    store_log,
    update_agent_control_task_status,
    upsert_agent_runtime_state,
    mark_agent_heartbeat,
    upsert_agent_offline_code,
    upsert_agent_profile,
    update_api_endpoint_last_used,
    verify_user,
)

app = FastAPI()
logger = logging.getLogger("windsentinel")
logger.setLevel(LOG_LEVEL)
if not logger.handlers:
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)
    if LOG_FILE:
        file_handler = logging.FileHandler(LOG_FILE)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
ASSETS_DIR = os.path.join(STATIC_DIR, "assets")
PAGES_DIR = os.path.join(STATIC_DIR, "pages")
app.mount("/admin/ui/assets", StaticFiles(directory=ASSETS_DIR, html=False), name="admin_assets")

SHARED_KEY_B64 = os.getenv("WINDSENTINEL_SHARED_KEY_B64", base64.b64encode(b"\x00" * 32).decode())
SHARED_KEY = base64.b64decode(SHARED_KEY_B64)

TOKENS: Dict[str, Dict[str, Any]] = {}
POLICY_KEYS: Dict[str, str] = {}

RULES = None

ROLE_PERMISSIONS = {
    "admin": {
        "agents_view",
        "agents_manage",
        "policy_manage",
        "config_manage",
        "rules_manage",
        "audits_view",
        "logs_query",
        "users_manage",
        "api_keys_manage",
        "log_export_manage",
        "log_retention_manage",
        "login_blacklist_manage",
        "login_whitelist_manage",
        "client_control",
    },
    "auditor": {"agents_view", "audits_view", "logs_query", "api_keys_manage"},
    "operator": {"agents_view", "agents_manage", "policy_manage", "config_manage", "rules_manage", "api_keys_manage", "login_blacklist_manage", "login_whitelist_manage", "client_control"},
}

PAGE_PERMISSIONS = {
    "personal_mfa": {"agents_view", "audits_view", "logs_query", "agents_manage", "policy_manage", "config_manage", "rules_manage", "users_manage", "api_keys_manage", "log_export_manage", "log_retention_manage"},
    "personal_password": {"agents_view", "audits_view", "logs_query", "agents_manage", "policy_manage", "config_manage", "rules_manage", "users_manage", "api_keys_manage", "log_export_manage", "log_retention_manage"},
    "agents": {"agents_view"},
    "agent_manage": {"agents_manage"},
    "config": {"config_manage"},
    "policy": {"policy_manage"},
    "users": {"users_manage"},
    "audits": {"audits_view"},
    "rules": {"rules_manage"},
    "logs": {"logs_query"},
    "api_keys": {"api_keys_manage"},
    "log_management": {"log_export_manage", "log_retention_manage"},
    "login_blacklist": {"login_blacklist_manage"},
    "login_whitelist": {"login_whitelist_manage"},
}


def aesgcm_decrypt(key: bytes, payload: bytes) -> bytes:
    if len(payload) < 12:
        raise ValueError("payload too short")
    nonce = payload[:12]
    data = payload[12:]
    return AESGCM(key).decrypt(nonce, data, None)


def aesgcm_encrypt(key: bytes, data: bytes) -> bytes:
    nonce = os.urandom(12)
    ciphertext = AESGCM(key).encrypt(nonce, data, None)
    return nonce + ciphertext


def get_signing_key():
    key_b64 = os.getenv("WINDSENTINEL_CONFIG_SIGNING_KEY_B64")
    key_id = os.getenv("WINDSENTINEL_CONFIG_SIGNING_KEY_ID", "default")
    if not key_b64:
        key_b64 = SHARED_KEY_B64
        key_id = "shared_key"
    return base64.b64decode(key_b64), key_id


def sign_agent_config(config):
    config_json = json.dumps(config, sort_keys=True, separators=(",", ":"))
    key, key_id = get_signing_key()
    signature = hmac.new(key, config_json.encode(), hashlib.sha256).digest()
    return {
        "config": config,
        "config_json": config_json,
        "signature": base64.b64encode(signature).decode(),
        "signed_at": int(time.time()),
        "key_id": key_id,
        "package": build_agent_package_meta(),
    }


def ensure_agent_control_bootstrap(agent_id: str, created_by: str = "system"):
    current = get_agent_offline_code(agent_id)
    if current:
        return {
            "service_name": default_agent_service_name(),
            "offline_code_hash": current["code_hash"],
            "offline_code_salt": current["code_salt"],
            "offline_code_version": current["code_version"],
        }, None
    offline_code = generate_offline_authorization_code()
    code_salt = generate_code_salt()
    code_hash = hash_offline_authorization_code(offline_code, code_salt)
    upsert_agent_offline_code(agent_id, code_hash, code_salt, 1, "active", created_by)
    return {
        "service_name": default_agent_service_name(),
        "offline_code_hash": code_hash,
        "offline_code_salt": code_salt,
        "offline_code_version": 1,
    }, offline_code


def default_agent_service_name():
    return "com.windsentinel.agent" if os.uname().sysname.lower() == "darwin" else "windsentinel-agent"


def prepare_agent_config(config: Dict[str, Any], created_by: str = "system"):
    prepared = dict(config)
    agent_id = prepared.get("agent_id") or str(uuid.uuid4())
    prepared["agent_id"] = agent_id
    bootstrap, offline_code = ensure_agent_control_bootstrap(agent_id, created_by)
    control = dict(prepared.get("control") or {})
    control.setdefault("service_name", bootstrap["service_name"])
    control["offline_code_hash"] = bootstrap["offline_code_hash"]
    control["offline_code_salt"] = bootstrap["offline_code_salt"]
    control["offline_code_version"] = bootstrap["offline_code_version"]
    prepared["control"] = control
    return prepared, offline_code


def default_agent_config(request: Request):
    host = request.headers.get("host", "127.0.0.1:8000")
    scheme = request.url.scheme
    server_url = f"{scheme}://{host}"
    return {
        "agent_id": str(uuid.uuid4()),
        "server_url": server_url,
        "shared_key_b64": base64.b64encode(os.urandom(32)).decode(),
        "control": AgentControlBootstrapPayload(service_name=default_agent_service_name()).model_dump(),
    }


def agent_binary_path():
    override = os.getenv("WINDSENTINEL_AGENT_BINARY_PATH")
    if override:
        return override
    base = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "target"))
    candidates = [
        os.path.join(base, "release", "windsentinel_agent"),
        os.path.join(base, "release", "WindSentinelAgent"),
        os.path.join(base, "debug", "windsentinel_agent"),
        os.path.join(base, "debug", "WindSentinelAgent"),
    ]
    for candidate in candidates:
        if os.path.exists(candidate):
            return candidate
    return candidates[0]


def agent_version():
    return os.getenv("WINDSENTINEL_AGENT_VERSION", "unknown")


def build_agent_package_meta():
    path = agent_binary_path()
    meta = {"agent_version": agent_version(), "binary_present": os.path.exists(path)}
    if not os.path.exists(path):
        return meta
    hasher = hashlib.sha256()
    size = 0
    with open(path, "rb") as fh:
        while True:
            chunk = fh.read(1024 * 1024)
            if not chunk:
                break
            hasher.update(chunk)
            size += len(chunk)
    meta["binary_sha256"] = hasher.hexdigest()
    meta["binary_size"] = size
    return meta


def load_rules():
    rules_path = os.path.join(os.path.dirname(__file__), "rules")
    rule_files = [os.path.join(rules_path, name) for name in os.listdir(rules_path) if name.endswith(".yar")]
    if not rule_files:
        return None
    return yara.compile(filepaths={str(i): p for i, p in enumerate(rule_files)})


def ensure_rules():
    global RULES
    if RULES is None:
        RULES = load_rules()


def get_client_ip(request: Request):
    if request.client:
        return request.client.host
    return None


def get_user_agent(request: Optional[Request]):
    if not request:
        return None
    return request.headers.get("user-agent")


def get_request_method(request: Optional[Request]):
    if not request:
        return None
    return request.method


def get_request_path(request: Optional[Request]):
    if not request:
        return None
    return request.url.path


def get_request_referer(request: Optional[Request]):
    if not request:
        return None
    return request.headers.get("referer")


def get_request_query(request: Optional[Request]):
    if not request:
        return None
    return request.url.query or None


def get_device_type(request: Optional[Request]):
    if not request:
        return "unknown"
    header_value = request.headers.get("x-device-type")
    if header_value:
        return header_value.strip().lower()
    ua = (request.headers.get("user-agent") or "").lower()
    if any(token in ua for token in ["bot", "spider", "crawler"]):
        return "bot"
    if any(token in ua for token in ["ipad", "tablet"]):
        return "tablet"
    if any(token in ua for token in ["iphone", "android", "mobile"]):
        return "mobile"
    if any(token in ua for token in ["windows", "macintosh", "linux"]):
        return "desktop"
    return "unknown"


def get_user_agent_lower(request: Optional[Request]):
    if not request:
        return ""
    return (request.headers.get("user-agent") or "").lower()


def get_browser_name(request: Optional[Request]):
    ua = get_user_agent_lower(request)
    if "edg/" in ua or "edge/" in ua:
        return "edge"
    if "chrome/" in ua and "edg/" not in ua:
        return "chrome"
    if "firefox/" in ua:
        return "firefox"
    if "safari/" in ua and "chrome/" not in ua:
        return "safari"
    if "msie" in ua or "trident/" in ua:
        return "ie"
    return "unknown"


def get_os_name(request: Optional[Request]):
    ua = get_user_agent_lower(request)
    if "windows" in ua:
        return "windows"
    if "macintosh" in ua or "mac os x" in ua:
        return "macos"
    if "iphone" in ua or "ipad" in ua or "ios" in ua:
        return "ios"
    if "android" in ua:
        return "android"
    if "linux" in ua:
        return "linux"
    return "unknown"


def hash_api_key(api_key: str) -> str:
    return hashlib.sha256(api_key.encode()).hexdigest()


def authenticate_request(request: Request, authorization: Optional[str], api_key: Optional[str]):
    if authorization and authorization.startswith("Bearer "):
        token = authorization.split(" ", 1)[1]
        data = TOKENS.get(token)
        if not data:
            raise HTTPException(status_code=401, detail="invalid token")
        if data.get("must_change"):
            if request.url.path not in (
                "/admin/bind_mfa",
                "/admin/verify_mfa",
                "/admin/change_password",
                "/admin/ui/app",
                "/admin/ui/pages/personal_mfa",
                "/admin/ui/pages/personal_password",
                "/admin/me",
                "/admin/logout",
            ):
                raise HTTPException(status_code=403, detail="password change required")
        return {**data, "via_api": False, "api_functions": None}
    if api_key:
        endpoint = get_api_endpoint_by_key_hash(hash_api_key(api_key))
        if not endpoint:
            raise HTTPException(status_code=401, detail="invalid api key")
        update_api_endpoint_last_used(endpoint["id"])
        return {
            "username": endpoint["created_by"],
            "role": endpoint["role"],
            "via_api": True,
            "api_functions": endpoint["functions"],
            "api_endpoint_id": endpoint["id"],
        }
    raise HTTPException(status_code=401, detail="missing token")


def require_auth(
    request: Request,
    authorization: Optional[str] = Header(None),
    api_key: Optional[str] = Header(None, alias="X-API-Key"),
):
    return authenticate_request(request, authorization, api_key)


def require_role(user, allowed):
    if user["role"] not in allowed:
        raise HTTPException(status_code=404, detail="not found")


def require_feature(user, feature):
    role_perms = ROLE_PERMISSIONS.get(user["role"], set())
    if feature not in role_perms:
        raise HTTPException(status_code=404, detail="not found")
    if user.get("via_api") and feature not in set(user.get("api_functions") or []):
        raise HTTPException(status_code=404, detail="not found")


def require_access(user, allowed_roles, feature):
    require_role(user, allowed_roles)
    require_feature(user, feature)


def require_page_access(user, page_name):
    allowed = PAGE_PERMISSIONS.get(page_name)
    if allowed is None:
        raise HTTPException(status_code=404, detail="not found")
    role_perms = ROLE_PERMISSIONS.get(user["role"], set())
    if not (role_perms & allowed):
        raise HTTPException(status_code=404, detail="not found")


def audit_action(user, action, request: Optional[Request], target=None, result="ok", auth_type: Optional[str] = None):
    if request is not None:
        setattr(request.state, "audit_logged", True)
    auth_value = auth_type or ("api_key" if user.get("via_api") else "token")
    add_audit(
        user["username"],
        action,
        ip=get_client_ip(request) if request else None,
        target=target,
        result=result,
        via_api=bool(user.get("via_api")),
        user_agent=get_user_agent(request),
        method=get_request_method(request),
        path=get_request_path(request),
        referer=get_request_referer(request),
        query=get_request_query(request),
        role=user.get("role"),
        auth_type=auth_value,
        api_endpoint_id=user.get("api_endpoint_id"),
    )
    payload = {
        "username": user["username"],
        "action": action,
        "target": target,
        "result": result,
        "ip": get_client_ip(request) if request else None,
        "via_api": bool(user.get("via_api")),
        "user_agent": get_user_agent(request),
        "method": get_request_method(request),
        "path": get_request_path(request),
        "referer": get_request_referer(request),
        "query": get_request_query(request),
        "role": user.get("role"),
        "auth_type": auth_value,
        "api_endpoint_id": user.get("api_endpoint_id"),
        "ts": int(time.time()),
    }
    try:
        asyncio.create_task(dispatch_log_exports(None, payload, "audit"))
    except Exception:
        pass


def audit_client_control(user, action, request: Optional[Request], agent_id: str, result: str, correlation_id: Optional[str] = None):
    auth_value = "api_key" if user.get("via_api") else "token"
    add_audit(
        user["username"],
        action,
        ip=get_client_ip(request) if request else None,
        target=agent_id,
        result=result,
        via_api=bool(user.get("via_api")),
        user_agent=get_user_agent(request),
        method=get_request_method(request),
        path=get_request_path(request),
        referer=get_request_referer(request),
        query=get_request_query(request),
        role=user.get("role"),
        auth_type=auth_value,
        api_endpoint_id=user.get("api_endpoint_id"),
        correlation_id=correlation_id,
    )
    payload = {
        "username": user["username"],
        "action": action,
        "target": agent_id,
        "result": result,
        "ip": get_client_ip(request) if request else None,
        "via_api": bool(user.get("via_api")),
        "user_agent": get_user_agent(request),
        "method": get_request_method(request),
        "path": get_request_path(request),
        "referer": get_request_referer(request),
        "query": get_request_query(request),
        "role": user.get("role"),
        "auth_type": auth_value,
        "api_endpoint_id": user.get("api_endpoint_id"),
        "correlation_id": correlation_id,
        "ts": int(time.time()),
    }
    try:
        asyncio.create_task(dispatch_log_exports(None, payload, "audit"))
    except Exception:
        pass


def require_client_control_permission(user, request: Request, agent_id: str, correlation_id: Optional[str] = None):
    if user.get("via_api"):
        audit_client_control(user, "client_control_permission_denied", request, agent_id, "api_key_not_allowed", correlation_id)
        raise HTTPException(status_code=403, detail="无权限")
    allowed_roles = {"admin", "operator"}
    if user.get("role") not in allowed_roles:
        audit_client_control(user, "client_control_permission_denied", request, agent_id, "role_denied", correlation_id)
        raise HTTPException(status_code=403, detail="无权限")
    role_perms = ROLE_PERMISSIONS.get(user.get("role"), set())
    if "client_control" not in role_perms:
        audit_client_control(user, "client_control_permission_denied", request, agent_id, "feature_denied", correlation_id)
        raise HTTPException(status_code=403, detail="无权限")


def require_client_control_mfa(user, request: Request, agent_id: str, mfa_code: str, correlation_id: Optional[str] = None):
    try:
        secret = get_user_mfa(user["username"])
    except HTTPException:
        audit_client_control(user, "client_control_mfa_missing", request, agent_id, "mfa_not_bound", correlation_id)
        raise HTTPException(status_code=400, detail="请先绑定MFA")
    if not mfa_code or not pyotp.TOTP(secret).verify(mfa_code):
        audit_client_control(user, "client_control_mfa_invalid", request, agent_id, "invalid_mfa", correlation_id)
        raise HTTPException(status_code=401, detail="验证码错误")
    return int(time.time())


def generate_offline_authorization_code():
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    groups = ["".join(secrets.choice(alphabet) for _ in range(4)) for _ in range(6)]
    return "WS-" + "-".join(groups)


def generate_code_salt():
    return base64.b64encode(os.urandom(16)).decode()


def hash_offline_authorization_code(code: str, salt: str) -> str:
    material = (salt + ":" + code).encode()
    digest = hashlib.pbkdf2_hmac("sha256", material, salt.encode(), 200000)
    return base64.b64encode(digest).decode()


def audit_login_attempt(username: str, request: Request, result: str, auth_type: str):
    add_audit(
        username,
        "login",
        ip=get_client_ip(request),
        target=None,
        result=result,
        via_api=False,
        user_agent=get_user_agent(request),
        method=get_request_method(request),
        path=get_request_path(request),
        referer=get_request_referer(request),
        query=get_request_query(request),
        role=None,
        auth_type=auth_type,
        api_endpoint_id=None,
    )
    payload = {
        "username": username,
        "action": "login",
        "target": None,
        "result": result,
        "ip": get_client_ip(request),
        "via_api": False,
        "user_agent": get_user_agent(request),
        "method": get_request_method(request),
        "path": get_request_path(request),
        "referer": get_request_referer(request),
        "query": get_request_query(request),
        "role": None,
        "auth_type": auth_type,
        "api_endpoint_id": None,
        "ts": int(time.time()),
    }
    try:
        asyncio.create_task(dispatch_log_exports(None, payload, "audit"))
    except Exception:
        pass


@app.middleware("http")
async def log_middleware(request: Request, call_next):
    start = time.time()
    body_preview = None
    if LOG_REQUEST_BODY:
        try:
            body = await request.body()
            if body:
                body_preview = body[:1024].decode(errors="ignore")
        except Exception:
            body_preview = None
    try:
        response = await call_next(request)
    except Exception:
        logger.exception(f"{request.method} {request.url.path} failed")
        raise
    duration = int((time.time() - start) * 1000)
    logger.info(f"{request.method} {request.url.path} {response.status_code} {duration}ms {body_preview or ''}".strip())
    return response


@app.middleware("http")
async def audit_middleware(request: Request, call_next):
    response = await call_next(request)
    if request.url.path.startswith("/admin") and request.url.path not in ("/admin/login", "/admin/ui/login"):
        if not getattr(request.state, "audit_logged", False):
            try:
                user = authenticate_request(request, request.headers.get("authorization"), request.headers.get("x-api-key"))
                action = f"{request.method} {request.url.path}"
                audit_action(
                    user,
                    action,
                    request,
                    target=request.url.query or None,
                    result=str(response.status_code),
                )
            except Exception:
                pass
    return response


@app.on_event("startup")
async def startup():
    init_db()
    ensure_rules()
    asyncio.create_task(retention_worker())


@app.post("/api/v1/health")
async def health(payload: HealthPayload):
    data = base64.b64decode(payload.payload)
    decrypted = aesgcm_decrypt(SHARED_KEY, data)
    report = json.loads(decrypted.decode())
    store_health(payload.agent_id, report)
    asyncio.create_task(dispatch_log_exports(payload.agent_id, report, "health"))
    return {"status": "ok"}


@app.post("/api/v1/logs")
async def logs(payload: LogPayload):
    data_b64 = payload.payload.get("data_b64")
    if not data_b64:
        raise HTTPException(status_code=400, detail="missing payload")
    raw = base64.b64decode(data_b64)
    records = parse_records(raw)
    for record in records:
        store_log(payload.agent_id, record)
        apply_rules(payload.agent_id, record)
        asyncio.create_task(dispatch_log_exports(payload.agent_id, record, "client_logs"))
    return {"status": "ok", "count": len(records)}


@app.get("/api/v1/policy", response_model=PolicyResponse)
async def policy(agent_id: str):
    payload = get_policy(agent_id)
    if not payload:
        payload = {
            "enabled_modules": ["process", "network", "health", "lock"],
            "kill_pids": [],
            "block_network_pids": [],
            "block_all_network": False,
            "lock": None,
            "unlock": None,
        }
    return payload


@app.post("/admin/login")
async def admin_login(payload: LoginRequest, request: Request):
    blacklist = get_login_blacklist()
    whitelist = get_login_whitelist()
    ip_blacklist = {str(item).strip() for item in (blacklist.get("ip_list") or []) if str(item).strip()}
    ip_whitelist = {str(item).strip() for item in (whitelist.get("ip_list") or []) if str(item).strip()}
    device_list = {str(item).strip().lower() for item in (blacklist.get("device_types") or []) if str(item).strip()}
    ua_keywords = {str(item).strip().lower() for item in (blacklist.get("ua_keywords") or []) if str(item).strip()}
    browser_list = {str(item).strip().lower() for item in (blacklist.get("browser_list") or []) if str(item).strip()}
    os_list = {str(item).strip().lower() for item in (blacklist.get("os_list") or []) if str(item).strip()}
    device_type = get_device_type(request)
    browser_name = get_browser_name(request)
    os_name = get_os_name(request)
    ua_text = get_user_agent_lower(request)
    client_ip = get_client_ip(request)
    if ip_whitelist and client_ip not in ip_whitelist:
        audit_login_attempt(payload.username, request, "blocked_whitelist", "whitelist")
        return FileResponse(os.path.join(STATIC_DIR, "404.html"), status_code=404)
    if (not ip_whitelist) and client_ip in ip_blacklist:
        audit_login_attempt(payload.username, request, "blocked_blacklist_ip", "blacklist")
        return FileResponse(os.path.join(STATIC_DIR, "404.html"), status_code=404)
    if device_type in device_list:
        audit_login_attempt(payload.username, request, "blocked_blacklist_device", "blacklist")
        return FileResponse(os.path.join(STATIC_DIR, "404.html"), status_code=404)
    if browser_name in browser_list:
        audit_login_attempt(payload.username, request, "blocked_blacklist_browser", "blacklist")
        return FileResponse(os.path.join(STATIC_DIR, "404.html"), status_code=404)
    if os_name in os_list:
        audit_login_attempt(payload.username, request, "blocked_blacklist_os", "blacklist")
        return FileResponse(os.path.join(STATIC_DIR, "404.html"), status_code=404)
    if ua_keywords and any(keyword in ua_text for keyword in ua_keywords):
        audit_login_attempt(payload.username, request, "blocked_blacklist_ua", "blacklist")
        return FileResponse(os.path.join(STATIC_DIR, "404.html"), status_code=404)
    user = verify_user(payload.username, payload.password)
    if not user:
        audit_login_attempt(payload.username, request, "invalid_credentials", "password")
        raise HTTPException(status_code=401, detail="invalid credentials")
    if user["mfa_secret"]:
        if not payload.mfa or not pyotp.TOTP(user["mfa_secret"]).verify(payload.mfa):
            audit_login_attempt(payload.username, request, "invalid_mfa", "password+mfa")
            raise HTTPException(status_code=401, detail="invalid mfa")
    token = generate_token()
    TOKENS[token] = {"username": user["username"], "role": user["role"], "must_change": user["must_change_password"]}
    auth_type = "password+mfa" if user["mfa_secret"] else "password"
    audit_action({"username": user["username"], "role": user["role"], "via_api": False}, "login", request, result="ok", auth_type=auth_type)
    return {
        "token": token,
        "role": user["role"],
        "must_change": bool(user["must_change_password"]),
        "mfa_bound": bool(user["mfa_secret"]),
    }


@app.post("/admin/logout")
async def admin_logout(request: Request, user=Depends(require_auth)):
    token = request.headers.get("authorization", "").replace("Bearer ", "")
    TOKENS.pop(token, None)
    audit_action(user, "logout", request)
    return {"status": "ok"}


@app.get("/admin/me")
async def admin_me(user=Depends(require_auth)):
    return {
        "username": user["username"],
        "role": user["role"],
        "must_change": bool(user.get("must_change")),
        "via_api": bool(user.get("via_api")),
    }


@app.get("/admin/ui")
async def admin_ui_root():
    return RedirectResponse("/admin/ui/login")


@app.get("/admin/ui/")
async def admin_ui_root_slash():
    return RedirectResponse("/admin/ui/login")


@app.get("/admin/ui/index.html")
async def admin_ui_index():
    return RedirectResponse("/admin/ui/login")


@app.get("/admin/ui/login")
async def admin_ui_login():
    return FileResponse(os.path.join(STATIC_DIR, "login.html"))


@app.get("/admin/ui/app")
async def admin_ui_app():
    return FileResponse(os.path.join(STATIC_DIR, "admin.html"))


@app.get("/admin/ui/legacy/app.js")
async def admin_ui_legacy_app():
    return FileResponse(os.path.join(STATIC_DIR, "app.js"))


@app.get("/admin/ui/pages/{page}")
async def admin_ui_page(page: str, user=Depends(require_auth)):
    require_page_access(user, page)
    path = os.path.join(PAGES_DIR, f"{page}.html")
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="not found")
    return FileResponse(path)


@app.get("/admin/agent-config/template")
async def agent_config_template(request: Request, user=Depends(require_auth)):
    require_access(user, {"admin", "operator"}, "config_manage")
    return {"config": default_agent_config(request)}


@app.get("/admin/agent-config/meta")
async def agent_config_meta(user=Depends(require_auth)):
    require_access(user, {"admin", "operator"}, "config_manage")
    return build_agent_package_meta()


@app.get("/admin/agent-config/templates")
async def agent_config_templates(user=Depends(require_auth)):
    require_access(user, {"admin", "operator"}, "config_manage")
    return list_config_templates()


@app.get("/admin/agent-config/templates/{name}")
async def agent_config_template_detail(name: str, user=Depends(require_auth)):
    require_access(user, {"admin", "operator"}, "config_manage")
    data = get_config_template(name)
    if not data:
        raise HTTPException(status_code=404, detail="no template")
    return data


@app.post("/admin/agent-config/templates")
async def agent_config_template_upsert(payload: AgentConfigTemplatePayload, request: Request, user=Depends(require_auth)):
    require_access(user, {"admin", "operator"}, "config_manage")
    upsert_config_template(payload.name, payload.config.model_dump())
    audit_action(user, "agent_config_template_upsert", request, target=payload.name)
    return {"status": "ok"}


@app.delete("/admin/agent-config/templates/{name}")
async def agent_config_template_delete(name: str, request: Request, user=Depends(require_auth)):
    require_access(user, {"admin", "operator"}, "config_manage")
    delete_config_template(name)
    audit_action(user, "agent_config_template_delete", request, target=name)
    return {"status": "ok"}


@app.get("/admin/agent-config/templates/{name}/versions")
async def agent_config_template_versions(name: str, limit: int = 50, user=Depends(require_auth)):
    require_access(user, {"admin", "operator"}, "config_manage")
    return list_config_template_versions(name, limit)


@app.get("/admin/agent-config/templates/{name}/versions/{version_id}")
async def agent_config_template_version_detail(name: str, version_id: int, user=Depends(require_auth)):
    require_access(user, {"admin", "operator"}, "config_manage")
    data = get_config_template_version(name, version_id)
    if not data:
        raise HTTPException(status_code=404, detail="no version")
    return data


@app.post("/admin/agent-config/templates/{name}/rollback/{version_id}")
async def agent_config_template_rollback(name: str, version_id: int, request: Request, user=Depends(require_auth)):
    require_access(user, {"admin", "operator"}, "config_manage")
    data = get_config_template_version(name, version_id)
    if not data:
        raise HTTPException(status_code=404, detail="no version")
    upsert_config_template(name, data["config"])
    audit_action(user, "agent_config_template_rollback", request, target=f"{name}:{version_id}")
    return {"status": "ok"}


@app.get("/admin/agent-config/templates/export")
async def agent_config_templates_export(request: Request, user=Depends(require_auth)):
    require_access(user, {"admin", "operator"}, "config_manage")
    items = list_config_templates()
    data = []
    for item in items:
        detail = get_config_template(item["name"])
        if detail:
            data.append({"name": detail["name"], "config": detail["config"]})
    content = json.dumps({"templates": data}, indent=2).encode()
    audit_action(user, "agent_config_templates_export", request)
    return StreamingResponse(
        io.BytesIO(content),
        media_type="application/json",
        headers={"Content-Disposition": "attachment; filename=windsentinel-agent-templates.json"},
    )


@app.post("/admin/agent-config/templates/import")
async def agent_config_templates_import(payload: Dict[str, Any], request: Request, user=Depends(require_auth)):
    require_access(user, {"admin", "operator"}, "config_manage")
    templates = payload.get("templates")
    if not isinstance(templates, list):
        raise HTTPException(status_code=400, detail="invalid templates")
    count = 0
    for item in templates:
        try:
            parsed = AgentConfigTemplateImportPayload(**item)
        except Exception:
            continue
        upsert_config_template(parsed.name, parsed.config.model_dump())
        count += 1
    audit_action(user, "agent_config_templates_import", request, target=str(count))
    return {"status": "ok", "count": count}


@app.post("/admin/agent-config/sign")
async def agent_config_sign(payload: AgentConfigPayload, request: Request, user=Depends(require_auth)):
    require_access(user, {"admin", "operator"}, "config_manage")
    config, offline_code = prepare_agent_config(payload.model_dump(), user["username"])
    signed = sign_agent_config(config)
    if offline_code:
        signed["offline_authorization_code"] = offline_code
    audit_action(user, "agent_config_sign", request)
    return signed


@app.post("/admin/agent-config/download")
async def agent_config_download(
    payload: AgentConfigPayload,
    request: Request,
    format: str = "config",
    user=Depends(require_auth),
):
    require_access(user, {"admin", "operator"}, "config_manage")
    config, offline_code = prepare_agent_config(payload.model_dump(), user["username"])
    signed = sign_agent_config(config)
    if offline_code:
        signed["offline_authorization_code"] = offline_code
    if format == "config":
        content = json.dumps(signed, indent=2).encode()
        audit_action(user, "agent_config_download", request, target="config")
        return StreamingResponse(
            io.BytesIO(content),
            media_type="application/json",
            headers={"Content-Disposition": "attachment; filename=windsentinel-agent-config.json"},
        )
    if format == "zip":
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("config.json", json.dumps(signed, indent=2))
            zf.writestr("manifest.json", json.dumps({"package": signed.get("package"), "signed_at": signed.get("signed_at"), "key_id": signed.get("key_id")}, indent=2))
            agent_path = agent_binary_path()
            if os.path.exists(agent_path):
                zf.write(agent_path, arcname="WindSentinelAgent")
        buffer.seek(0)
        audit_action(user, "agent_config_package", request, target="zip")
        return StreamingResponse(
            buffer,
            media_type="application/zip",
            headers={"Content-Disposition": "attachment; filename=windsentinel-agent-package.zip"},
        )
    raise HTTPException(status_code=400, detail="invalid format")


@app.post("/admin/bind_mfa")
async def bind_mfa(request: Request, user=Depends(require_auth)):
    secret = pyotp.random_base32()
    set_user_mfa(user["username"], secret)
    uri = pyotp.totp.TOTP(secret).provisioning_uri(name=user["username"], issuer_name=MFA_ISSUER)
    qr = qrcode.QRCode(border=2)
    qr.add_data(uri)
    qr.make(fit=True)
    img = qr.make_image(image_factory=qrcode.image.pure.PyPNGImage)
    buffer = io.BytesIO()
    img.save(buffer)
    qr_b64 = base64.b64encode(buffer.getvalue()).decode()
    audit_action(user, "bind_mfa", request)
    return {"mfa_secret": secret, "otpauth_uri": uri, "qr_png_b64": qr_b64}


@app.post("/admin/verify_mfa")
async def verify_mfa(payload: MfaVerifyRequest, request: Request, user=Depends(require_auth)):
    secret = get_user_mfa(user["username"])
    if not pyotp.TOTP(secret).verify(payload.code):
        audit_action(user, "verify_mfa", request, result="invalid")
        raise HTTPException(status_code=401, detail="invalid mfa")
    audit_action(user, "verify_mfa", request, result="ok")
    return {"status": "ok"}


@app.post("/admin/change_password")
async def change_password(payload: ChangePasswordRequest, request: Request, user=Depends(require_auth)):
    if not pyotp.TOTP(get_user_mfa(user["username"])).verify(payload.mfa):
        raise HTTPException(status_code=401, detail="invalid mfa")
    if not verify_user(user["username"], payload.old_password):
        raise HTTPException(status_code=401, detail="invalid password")
    if not strong_password(payload.new_password):
        raise HTTPException(status_code=400, detail="weak password")
    set_user_password(user["username"], payload.new_password)
    for token, data in list(TOKENS.items()):
        if data.get("username") == user["username"]:
            data["must_change"] = False
    audit_action(user, "change_password", request)
    return {"status": "ok"}


@app.post("/admin/users")
async def create_user(request: CreateUserRequest, req: Request, user=Depends(require_auth)):
    require_access(user, {"admin"}, "users_manage")
    add_user(request.username, request.password, request.role)
    audit_action(user, "create_user", req, target=request.username)
    return {"status": "ok"}


@app.get("/admin/users")
async def users(user=Depends(require_auth)):
    require_access(user, {"admin"}, "users_manage")
    return list_users()


@app.delete("/admin/users/{username}")
async def remove_user(username: str, req: Request, user=Depends(require_auth)):
    require_access(user, {"admin"}, "users_manage")
    delete_user(username)
    audit_action(user, "delete_user", req, target=username)
    return {"status": "ok"}


@app.get("/admin/api-endpoints")
async def api_endpoints(user=Depends(require_auth)):
    require_access(user, {"admin", "auditor", "operator"}, "api_keys_manage")
    if user["role"] == "admin":
        return list_api_endpoints()
    return list_api_endpoints(role=user["role"], created_by=user["username"])


@app.post("/admin/api-endpoints")
async def create_api_endpoint_api(payload: ApiEndpointPayload, request: Request, user=Depends(require_auth)):
    require_access(user, {"admin", "auditor", "operator"}, "api_keys_manage")
    if user["role"] != "admin" and payload.role != user["role"]:
        raise HTTPException(status_code=404, detail="not found")
    allowed = ROLE_PERMISSIONS.get(payload.role, set())
    if not payload.functions or any(item not in allowed for item in payload.functions):
        raise HTTPException(status_code=400, detail="invalid functions")
    alias = payload.alias or f"{user['username']}-{'-'.join(payload.functions)}"
    api_key = base64.urlsafe_b64encode(os.urandom(24)).decode().rstrip("=")
    endpoint_id = create_api_endpoint(
        payload.name,
        alias,
        payload.role,
        payload.functions,
        hash_api_key(api_key),
        user["username"],
    )
    audit_action(user, "create_api_endpoint", request, target=str(endpoint_id))
    return {"id": endpoint_id, "name": payload.name, "alias": alias, "role": payload.role, "functions": payload.functions, "api_key": api_key}


@app.delete("/admin/api-endpoints/{endpoint_id}")
async def delete_api_endpoint_api(endpoint_id: int, request: Request, user=Depends(require_auth)):
    require_access(user, {"admin", "auditor", "operator"}, "api_keys_manage")
    endpoint = get_api_endpoint(endpoint_id)
    if not endpoint:
        raise HTTPException(status_code=404, detail="not found")
    if user["role"] != "admin" and endpoint["created_by"] != user["username"]:
        raise HTTPException(status_code=404, detail="not found")
    delete_api_endpoint(endpoint_id)
    audit_action(user, "delete_api_endpoint", request, target=str(endpoint_id))
    return {"status": "ok"}


@app.post("/admin/logs/query")
async def query_logs(req: SqlQuery, user=Depends(require_auth)):
    require_access(user, {"admin", "auditor"}, "logs_query")
    return get_logs_sql(req.query)


@app.get("/admin/audits")
async def audits(
    limit: int = 200,
    username: Optional[str] = None,
    action: Optional[str] = None,
    since: Optional[int] = None,
    until: Optional[int] = None,
    user=Depends(require_auth),
):
    require_access(user, {"admin", "auditor"}, "audits_view")
    return list_audits(limit, username, action, since, until)


@app.get("/admin/audits/stats")
async def audit_stats(
    bucket: str = "day",
    username: Optional[str] = None,
    action: Optional[str] = None,
    since: Optional[int] = None,
    until: Optional[int] = None,
    user=Depends(require_auth),
):
    require_access(user, {"admin", "auditor"}, "audits_view")
    return list_audit_stats(bucket, username, action, since, until)


@app.get("/admin/log-exports")
async def log_exports(user=Depends(require_auth)):
    require_access(user, {"admin"}, "log_export_manage")
    return list_log_exports()


@app.post("/admin/log-exports")
async def create_log_export_api(payload: LogExportPayload, request: Request, user=Depends(require_auth)):
    require_access(user, {"admin"}, "log_export_manage")
    if payload.target_type not in {"kafka", "rabbitmq", "elasticsearch"}:
        raise HTTPException(status_code=400, detail="invalid target")
    allowed_types = {"health", "client_logs", "audit"}
    log_types = payload.log_types or ["health", "client_logs", "audit"]
    if any(item not in allowed_types for item in log_types):
        raise HTTPException(status_code=400, detail="invalid log types")
    export_id = create_log_export(payload.target_type, payload.config, payload.enabled, log_types)
    audit_action(user, "create_log_export", request, target=str(export_id))
    return {"status": "ok", "id": export_id, "log_types": log_types}


@app.delete("/admin/log-exports/{export_id}")
async def delete_log_export_api(export_id: int, request: Request, user=Depends(require_auth)):
    require_access(user, {"admin"}, "log_export_manage")
    delete_log_export(export_id)
    audit_action(user, "delete_log_export", request, target=str(export_id))
    return {"status": "ok"}


@app.get("/admin/log-retention")
async def log_retention(user=Depends(require_auth)):
    require_access(user, {"admin"}, "log_retention_manage")
    return get_log_retention()


@app.post("/admin/log-retention")
async def set_log_retention_api(payload: LogRetentionPayload, request: Request, user=Depends(require_auth)):
    require_access(user, {"admin"}, "log_retention_manage")
    set_log_retention(payload.max_days, payload.max_bytes)
    audit_action(user, "set_log_retention", request)
    return {"status": "ok"}


@app.get("/admin/login-blacklist")
async def get_login_blacklist_api(user=Depends(require_auth)):
    require_access(user, {"admin", "operator"}, "login_blacklist_manage")
    return get_login_blacklist()


@app.post("/admin/login-blacklist")
async def set_login_blacklist_api(payload: LoginBlacklistPayload, request: Request, user=Depends(require_auth)):
    require_access(user, {"admin", "operator"}, "login_blacklist_manage")
    ip_list = [item.strip() for item in payload.ip_list if item and item.strip()]
    device_types = [item.strip().lower() for item in payload.device_types if item and item.strip()]
    ua_keywords = [item.strip().lower() for item in payload.ua_keywords if item and item.strip()]
    browser_list = [item.strip().lower() for item in payload.browser_list if item and item.strip()]
    os_list = [item.strip().lower() for item in payload.os_list if item and item.strip()]
    set_login_blacklist(ip_list, device_types, ua_keywords, browser_list, os_list)
    target = f"ip:{len(ip_list)},device:{len(device_types)},ua:{len(ua_keywords)},browser:{len(browser_list)},os:{len(os_list)}"
    audit_action(user, "set_login_blacklist", request, target=target)
    return {
        "status": "ok",
        "ip_list": ip_list,
        "device_types": device_types,
        "ua_keywords": ua_keywords,
        "browser_list": browser_list,
        "os_list": os_list,
    }


@app.get("/admin/login-whitelist")
async def get_login_whitelist_api(user=Depends(require_auth)):
    require_access(user, {"admin", "operator"}, "login_whitelist_manage")
    return get_login_whitelist()


@app.post("/admin/login-whitelist")
async def set_login_whitelist_api(payload: LoginWhitelistPayload, request: Request, user=Depends(require_auth)):
    require_access(user, {"admin", "operator"}, "login_whitelist_manage")
    ip_list = [item.strip() for item in payload.ip_list if item and item.strip()]
    set_login_whitelist(ip_list)
    audit_action(user, "set_login_whitelist", request, target=f"ip:{len(ip_list)}")
    return {"status": "ok", "ip_list": ip_list}


@app.get("/admin/rules")
async def get_rules(user=Depends(require_auth)):
    require_access(user, {"admin", "operator"}, "rules_manage")
    return list_rules()


@app.post("/admin/rules")
async def upsert_rule(payload: RulePayload, req: Request, user=Depends(require_auth)):
    require_access(user, {"admin", "operator"}, "rules_manage")
    name = save_rule(payload.name, payload.content)
    ensure_rules()
    audit_action(user, "save_rule", req, target=name)
    return {"status": "ok", "name": name}


@app.get("/admin/rules/export")
async def export_rules(request: Request, names: Optional[str] = None, user=Depends(require_auth)):
    require_access(user, {"admin", "operator"}, "rules_manage")
    rules = list_rules()
    if names:
        allow = {name.strip() for name in names.split(",") if name.strip()}
        if allow:
            rules = [item for item in rules if item.get("name") in allow]
    content = json.dumps({"rules": rules}, indent=2).encode()
    audit_action(user, "rules_export", request, target=names)
    return StreamingResponse(
        io.BytesIO(content),
        media_type="application/json",
        headers={"Content-Disposition": "attachment; filename=windsentinel-rules.json"},
    )


@app.post("/admin/rules/import")
async def import_rules(payload: Dict[str, Any], request: Request, mode: str = "overwrite", user=Depends(require_auth)):
    require_access(user, {"admin", "operator"}, "rules_manage")
    rules = payload.get("rules")
    if not isinstance(rules, list):
        raise HTTPException(status_code=400, detail="invalid rules")
    created = 0
    updated = 0
    skipped = 0
    for item in rules:
        name = item.get("name")
        content = item.get("content")
        if not name or content is None:
            continue
        existing = get_rule_content(name)
        if existing is None:
            save_rule(name, content)
            created += 1
        elif existing == content:
            skipped += 1
        else:
            if mode == "skip":
                skipped += 1
            else:
                save_rule(name, content)
                updated += 1
    ensure_rules()
    total = created + updated + skipped
    audit_action(user, "rules_import", request, target=str(total))
    return {"status": "ok", "created": created, "updated": updated, "skipped": skipped, "total": total}


@app.post("/admin/rules/import/preview")
async def import_rules_preview(payload: Dict[str, Any], user=Depends(require_auth)):
    require_access(user, {"admin", "operator"}, "rules_manage")
    rules = payload.get("rules")
    if not isinstance(rules, list):
        raise HTTPException(status_code=400, detail="invalid rules")
    items = []
    for item in rules:
        name = item.get("name")
        content = item.get("content")
        if not name or content is None:
            continue
        existing = get_rule_content(name)
        if existing is None:
            status = "new"
        elif existing == content:
            status = "same"
        else:
            status = "conflict"
        items.append({"name": name, "status": status})
    return {"items": items, "total": len(items)}


@app.get("/admin/rules/{name}/versions")
async def rule_versions(name: str, user=Depends(require_auth)):
    require_access(user, {"admin", "operator"}, "rules_manage")
    return list_rule_versions(name)


@app.get("/admin/rules/{name}/versions/{version}")
async def rule_version(name: str, version: str, user=Depends(require_auth)):
    require_access(user, {"admin", "operator"}, "rules_manage")
    content = get_rule_version(name, version)
    if content is None:
        raise HTTPException(status_code=404, detail="no version")
    return {"name": name, "version": version, "content": content}


@app.post("/admin/rules/{name}/restore")
async def restore_rule(name: str, version: str, request: Request, user=Depends(require_auth)):
    require_access(user, {"admin", "operator"}, "rules_manage")
    restored = restore_rule_version(name, version)
    if restored is None:
        raise HTTPException(status_code=404, detail="no version")
    ensure_rules()
    audit_action(user, "restore_rule", request, target=f"{restored}:{version}")
    return {"status": "ok", "name": restored, "version": version}


@app.get("/admin/rules/{name}/diff")
async def rule_diff(name: str, left: str = "current", right: str = "current", user=Depends(require_auth)):
    require_access(user, {"admin", "operator"}, "rules_manage")
    if left == "current":
        left_content = get_rule_content(name)
    else:
        left_content = get_rule_version(name, left)
    if right == "current":
        right_content = get_rule_content(name)
    else:
        right_content = get_rule_version(name, right)
    if left_content is None or right_content is None:
        raise HTTPException(status_code=404, detail="no content")
    diff = difflib.unified_diff(
        left_content.splitlines(),
        right_content.splitlines(),
        fromfile=left,
        tofile=right,
        lineterm="",
    )
    return {"diff": "\n".join(diff)}


@app.get("/admin/groups")
async def groups(user=Depends(require_auth)):
    require_access(user, {"admin", "operator"}, "agents_manage")
    return list_groups()


@app.post("/admin/groups")
async def create_group_api(payload: GroupPayload, request: Request, user=Depends(require_auth)):
    require_access(user, {"admin", "operator"}, "agents_manage")
    group_id = create_group(payload.name, payload.description)
    audit_action(user, "create_group", request, target=payload.name)
    return {"status": "ok", "id": group_id}


@app.delete("/admin/groups/{group_id}")
async def delete_group_api(group_id: int, request: Request, user=Depends(require_auth)):
    require_access(user, {"admin", "operator"}, "agents_manage")
    delete_group(group_id)
    audit_action(user, "delete_group", request, target=str(group_id))
    return {"status": "ok"}


@app.get("/admin/tags")
async def tags(user=Depends(require_auth)):
    require_access(user, {"admin", "operator"}, "agents_manage")
    return list_tags()


@app.post("/admin/tags")
async def create_tag_api(payload: TagPayload, request: Request, user=Depends(require_auth)):
    require_access(user, {"admin", "operator"}, "agents_manage")
    tag_id = create_tag(payload.name)
    audit_action(user, "create_tag", request, target=payload.name)
    return {"status": "ok", "id": tag_id}


@app.delete("/admin/tags/{tag_id}")
async def delete_tag_api(tag_id: int, request: Request, user=Depends(require_auth)):
    require_access(user, {"admin", "operator"}, "agents_manage")
    delete_tag(tag_id)
    audit_action(user, "delete_tag", request, target=str(tag_id))
    return {"status": "ok"}


@app.get("/admin/agents")
async def agents(
    group_id: Optional[int] = None,
    tag_id: Optional[int] = None,
    q: Optional[str] = None,
    offset: int = 0,
    limit: int = 200,
    include_inactive: bool = False,
    user=Depends(require_auth),
):
    require_access(user, {"admin", "auditor", "operator"}, "agents_view")
    return list_agents(group_id, tag_id, q, offset, limit, include_inactive)


@app.get("/admin/agents/{agent_id}")
async def agent_detail(agent_id: str, user=Depends(require_auth)):
    require_access(user, {"admin", "auditor", "operator"}, "agents_view")
    data = get_agent_detail(agent_id)
    if not data:
        raise HTTPException(status_code=404, detail="no agent")
    return data


@app.post("/admin/agents/{agent_id}/profile")
async def update_agent_profile(agent_id: str, payload: AgentProfilePayload, request: Request, user=Depends(require_auth)):
    require_access(user, {"admin", "operator"}, "agents_manage")
    upsert_agent_profile(agent_id, payload.display_name, payload.notes, payload.group_id)
    audit_action(user, "update_agent_profile", request, target=agent_id)
    return {"status": "ok"}


@app.post("/admin/agents/{agent_id}/tags")
async def update_agent_tags(agent_id: str, payload: AgentTagsPayload, request: Request, user=Depends(require_auth)):
    require_access(user, {"admin", "operator"}, "agents_manage")
    set_agent_tags(agent_id, payload.tags)
    audit_action(user, "update_agent_tags", request, target=agent_id)
    return {"status": "ok"}


@app.delete("/admin/agents/{agent_id}/record")
async def delete_agent_record_api(agent_id: str, request: Request, user=Depends(require_auth)):
    require_access(user, {"admin", "operator"}, "agents_manage")
    delete_agent_record(agent_id)
    audit_action(user, "delete_agent_record", request, target=agent_id)
    return {"status": "ok", "agent_id": agent_id}


@app.post("/admin/agents/cleanup-inactive")
async def cleanup_inactive_agents(request: Request, inactive_after_seconds: int = 1800, user=Depends(require_auth)):
    require_access(user, {"admin", "operator"}, "agents_manage")
    removed = cleanup_inactive_agent_records(inactive_after_seconds)
    audit_action(user, "cleanup_inactive_agents", request, target=str(len(removed)))
    return {"status": "ok", "removed": removed, "count": len(removed)}


@app.get("/admin/health/{agent_id}")
async def latest_health(agent_id: str, user=Depends(require_auth)):
    require_access(user, {"admin", "auditor", "operator"}, "agents_view")
    data = get_latest_health(agent_id)
    if not data:
        raise HTTPException(status_code=404, detail="no health")
    return data


@app.get("/admin/agents/{agent_id}/control/offline-code")
async def get_agent_offline_code_meta(agent_id: str, request: Request, user=Depends(require_auth)):
    correlation_id = str(uuid.uuid4())
    require_client_control_permission(user, request, agent_id, correlation_id)
    data = get_agent_offline_code(agent_id)
    if not data:
        audit_client_control(user, "offline_auth_code_meta_read", request, agent_id, "not_found", correlation_id)
        raise HTTPException(status_code=404, detail="no offline authorization code")
    audit_client_control(user, "offline_auth_code_meta_read", request, agent_id, "ok", correlation_id)
    return {
        "agent_id": data["agent_id"],
        "code_version": data["code_version"],
        "status": data["status"],
        "created_at": data["created_at"],
        "rotated_at": data["rotated_at"],
        "rotated_by": data["rotated_by"],
        "correlation_id": correlation_id,
    }


@app.post("/admin/agents/{agent_id}/control/offline-code/rotate")
async def rotate_agent_offline_code(agent_id: str, payload: OfflineCodeRotateRequest, request: Request, user=Depends(require_auth)):
    correlation_id = str(uuid.uuid4())
    require_client_control_permission(user, request, agent_id, correlation_id)
    require_client_control_mfa(user, request, agent_id, payload.mfa_code, correlation_id)
    current = get_agent_offline_code(agent_id)
    next_version = (int(current["code_version"]) + 1) if current else 1
    offline_code = generate_offline_authorization_code()
    code_salt = generate_code_salt()
    code_hash = hash_offline_authorization_code(offline_code, code_salt)
    upsert_agent_offline_code(agent_id, code_hash, code_salt, next_version, "active", user["username"])
    audit_client_control(user, "offline_auth_code_rotated", request, agent_id, "ok", correlation_id)
    return {
        "agent_id": agent_id,
        "offline_code": offline_code,
        "code_version": next_version,
        "reason": payload.reason,
        "correlation_id": correlation_id,
    }


@app.get("/admin/agents/{agent_id}/control/tasks")
async def list_control_tasks(agent_id: str, request: Request, limit: int = 50, user=Depends(require_auth)):
    correlation_id = str(uuid.uuid4())
    require_client_control_permission(user, request, agent_id, correlation_id)
    items = list_agent_control_tasks(agent_id, limit)
    audit_client_control(user, "client_control_task_list", request, agent_id, "ok", correlation_id)
    return {"items": items, "correlation_id": correlation_id}


@app.get("/admin/agents/{agent_id}/control/runtime-state")
async def get_control_runtime_state(agent_id: str, request: Request, user=Depends(require_auth)):
    correlation_id = str(uuid.uuid4())
    require_client_control_permission(user, request, agent_id, correlation_id)
    state = get_agent_runtime_state(agent_id) or {
        "agent_id": agent_id,
        "desired_state": "running",
        "actual_state": "running",
        "reason": None,
        "updated_at": None,
        "last_heartbeat_at": None,
    }
    audit_client_control(user, "client_control_runtime_state_read", request, agent_id, "ok", correlation_id)
    return {**state, "correlation_id": correlation_id}


@app.post("/admin/agents/{agent_id}/control/task")
async def create_control_task(agent_id: str, payload: ClientControlTaskRequest, request: Request, user=Depends(require_auth)):
    correlation_id = str(uuid.uuid4())
    require_client_control_permission(user, request, agent_id, correlation_id)
    require_client_control_mfa(user, request, agent_id, payload.mfa_code, correlation_id)
    task_type = (payload.task_type or "").strip().lower()
    if task_type not in {"stop", "uninstall"}:
        raise HTTPException(status_code=400, detail="invalid task_type")
    expires_in_seconds = max(60, min(int(payload.expires_in_seconds or 86400), 7 * 86400))
    expires_at = int(time.time()) + expires_in_seconds
    task_payload = {
        "reason": payload.reason,
        "requested_by": user["username"],
        "requested_role": user["role"],
    }
    task_id = create_agent_control_task(
        agent_id,
        task_type,
        task_payload,
        user["username"],
        user["role"],
        mfa_verified_at=int(time.time()),
        expires_at=expires_at,
        audit_correlation_id=correlation_id,
    )
    if task_type == "stop":
        upsert_agent_runtime_state(agent_id, "stopped", "running", payload.reason)
    elif task_type == "uninstall":
        upsert_agent_runtime_state(agent_id, "uninstalling", "running", payload.reason)
    audit_client_control(user, f"client_{task_type}_task_created", request, agent_id, "ok", correlation_id)
    return {
        "status": "ok",
        "task_id": task_id,
        "task_type": task_type,
        "agent_id": agent_id,
        "expires_at": expires_at,
        "correlation_id": correlation_id,
    }


@app.get("/api/v1/control/offline-code-meta")
async def offline_code_meta(agent_id: str):
    data = get_agent_offline_code(agent_id)
    if not data:
        return {"control": None}
    return {
        "control": {
            "service_name": default_agent_service_name(),
            "offline_code_hash": data["code_hash"],
            "offline_code_salt": data["code_salt"],
            "offline_code_version": data["code_version"],
        }
    }


@app.post("/api/v1/control/heartbeat")
async def control_heartbeat(payload: Dict[str, Any]):
    agent_id = payload.get("agent_id")
    actual_state = str(payload.get("actual_state") or "running")
    if not agent_id:
        raise HTTPException(status_code=400, detail="missing agent_id")
    state = mark_agent_heartbeat(agent_id, actual_state)
    return {"runtime": state}


@app.get("/api/v1/control-tasks/next")
async def next_control_task(agent_id: str):
    task = get_next_agent_control_task(agent_id)
    if not task:
        return {"task": None}
    add_audit(
        task["created_by"],
        f"client_{task['task_type']}_task_delivered",
        target=agent_id,
        result="delivered",
        role=task["created_role"],
        auth_type="token",
        correlation_id=task.get("audit_correlation_id"),
    )
    return {"task": task}


@app.post("/api/v1/control-tasks/{task_id}/ack")
async def ack_control_task(task_id: int, payload: AgentControlTaskAckPayload):
    status = (payload.status or "").strip().lower()
    if status not in {"acknowledged", "running", "completed", "failed", "expired", "cancelled"}:
        raise HTTPException(status_code=400, detail="invalid status")
    task = update_agent_control_task_status(task_id, status, payload.result_code, payload.result_message)
    if not task:
        raise HTTPException(status_code=404, detail="no task")
    correlation_id = task.get("audit_correlation_id")
    add_audit(
        task["created_by"],
        f"client_{task['task_type']}_{status}",
        target=task["agent_id"],
        result=payload.result_code or status,
        role=task["created_role"],
        auth_type="token",
        correlation_id=correlation_id,
    )
    if task["task_type"] == "stop":
        desired = "stopped"
        actual = "stopped" if status == "completed" else "running"
        upsert_agent_runtime_state(task["agent_id"], desired, actual, task["payload"].get("reason"))
    elif task["task_type"] == "uninstall":
        desired = "uninstalled"
        actual = "uninstalled" if status == "completed" else "running"
        upsert_agent_runtime_state(task["agent_id"], desired, actual, task["payload"].get("reason"))
    return {"status": "ok", "task": task}


@app.post("/admin/policy/{agent_id}")
async def set_policy_admin(agent_id: str, payload: PolicyResponse, request: Request, user=Depends(require_auth)):
    require_access(user, {"admin", "operator"}, "policy_manage")
    set_policy(agent_id, payload.model_dump())
    audit_action(user, "set_policy", request, target=agent_id)
    return {"status": "ok"}


@app.post("/admin/policy/group/{group_id}")
async def set_policy_group(group_id: int, payload: PolicyResponse, request: Request, user=Depends(require_auth)):
    require_access(user, {"admin", "operator"}, "policy_manage")
    agent_ids = list_agent_ids_by_group(group_id)
    result = apply_policy_batch(agent_ids, payload)
    audit_action(user, "set_policy_group", request, target=f"{group_id}:{result['count']}")
    return result


@app.post("/admin/policy/tag/{tag_id}")
async def set_policy_tag(tag_id: int, payload: PolicyResponse, request: Request, user=Depends(require_auth)):
    require_access(user, {"admin", "operator"}, "policy_manage")
    agent_ids = list_agent_ids_by_tag(tag_id)
    result = apply_policy_batch(agent_ids, payload)
    audit_action(user, "set_policy_tag", request, target=f"{tag_id}:{result['count']}")
    return result


@app.post("/admin/policy/batch")
async def set_policy_batch(payload: BatchPolicyPayload, request: Request, user=Depends(require_auth)):
    require_access(user, {"admin", "operator"}, "policy_manage")
    result = apply_policy_batch(payload.agent_ids, payload.policy)
    audit_action(user, "set_policy_batch", request, target=str(result["count"]))
    return result


@app.post("/admin/policy/{agent_id}/lock")
async def lock_agent(agent_id: str, request: Request, user=Depends(require_auth)):
    require_access(user, {"admin"}, "policy_manage")
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()
    public_pem = key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode()
    payload = {
        "enabled_modules": ["process", "network", "health", "lock"],
        "kill_pids": [],
        "block_network_pids": [],
        "block_all_network": False,
        "lock": {"public_key_pem": public_pem},
        "unlock": None,
    }
    set_policy(agent_id, payload)
    POLICY_KEYS[agent_id] = private_pem
    audit_action(user, "lock", request, target=agent_id)
    return {"status": "ok"}


@app.post("/admin/policy/{agent_id}/unlock")
async def unlock_agent(agent_id: str, request: Request, user=Depends(require_auth)):
    require_access(user, {"admin"}, "policy_manage")
    private_pem = POLICY_KEYS.get(agent_id)
    if not private_pem:
        raise HTTPException(status_code=400, detail="no key")
    payload = {
        "enabled_modules": ["process", "network", "health", "lock"],
        "kill_pids": [],
        "block_network_pids": [],
        "block_all_network": False,
        "lock": None,
        "unlock": {"private_key_pem": private_pem},
    }
    set_policy(agent_id, payload)
    POLICY_KEYS.pop(agent_id, None)
    audit_action(user, "unlock", request, target=agent_id)
    return {"status": "ok"}


def parse_records(raw: bytes):
    records = []
    cursor = 0
    while cursor + 4 <= len(raw):
        length = int.from_bytes(raw[cursor : cursor + 4], "big")
        cursor += 4
        if cursor + length > len(raw):
            break
        payload = raw[cursor : cursor + length]
        cursor += length
        decrypted = aesgcm_decrypt(SHARED_KEY, payload)
        decompressed = gzip.decompress(decrypted)
        record = json.loads(decompressed.decode())
        records.append(record)
    return records


def apply_rules(agent_id: str, record: Dict[str, Any]):
    if RULES is None:
        return
    data = json.dumps(record)
    matches = RULES.match(data=data)
    if not matches:
        return
    kill_pids = []
    if "pid" in record.get("data", {}):
        kill_pids.append(record["data"]["pid"])
    policy = {
        "enabled_modules": ["process", "network", "health", "lock"],
        "kill_pids": kill_pids,
        "block_network_pids": kill_pids,
        "block_all_network": False,
        "lock": None,
        "unlock": None,
    }
    set_policy(agent_id, policy)


async def dispatch_log_exports(agent_id: Optional[str], record: Dict[str, Any], log_type: str):
    exports = list_log_exports()
    if not exports:
        return
    payload = {"agent_id": agent_id, "log_type": log_type, "data": record, "ts": int(time.time())}
    for item in exports:
        if not item.get("enabled"):
            continue
        log_types = item.get("log_types") or []
        if log_types and log_type not in log_types:
            continue
        target_type = item.get("target_type")
        config = item.get("config") or {}
        if target_type == "kafka":
            try:
                await asyncio.to_thread(send_kafka_log, config, payload)
            except Exception:
                logger.exception("kafka export failed")
        elif target_type == "rabbitmq":
            try:
                await asyncio.to_thread(send_rabbitmq_log, config, payload)
            except Exception:
                logger.exception("rabbitmq export failed")
        elif target_type == "elasticsearch":
            try:
                await asyncio.to_thread(send_elasticsearch_log, config, payload)
            except Exception:
                logger.exception("elasticsearch export failed")


def send_kafka_log(config: Dict[str, Any], payload: Dict[str, Any]):
    try:
        from kafka import KafkaProducer
    except Exception:
        return
    servers = config.get("bootstrap_servers")
    topic = config.get("topic")
    if not servers or not topic:
        return
    producer = KafkaProducer(bootstrap_servers=servers, value_serializer=lambda v: json.dumps(v).encode())
    producer.send(topic, payload)
    producer.flush()
    producer.close()


def send_rabbitmq_log(config: Dict[str, Any], payload: Dict[str, Any]):
    try:
        import pika
    except Exception:
        return
    url = config.get("url")
    queue = config.get("queue")
    if not url or not queue:
        return
    params = pika.URLParameters(url)
    connection = pika.BlockingConnection(params)
    channel = connection.channel()
    channel.queue_declare(queue=queue, durable=True)
    channel.basic_publish(exchange="", routing_key=queue, body=json.dumps(payload).encode())
    connection.close()


def send_elasticsearch_log(config: Dict[str, Any], payload: Dict[str, Any]):
    try:
        from elasticsearch import Elasticsearch
    except Exception:
        return
    url = config.get("url")
    index = config.get("index")
    if not url or not index:
        return
    client = Elasticsearch(url)
    client.index(index=index, document=payload)


async def retention_worker():
    while True:
        retention = get_log_retention()
        max_days = retention.get("max_days")
        max_bytes = retention.get("max_bytes")
        if max_days:
            cutoff = int(time.time()) - int(max_days) * 86400
            purge_logs_older_than(cutoff)
        if max_bytes:
            purge_logs_by_size(int(max_bytes))
        await asyncio.sleep(600)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    trace = traceback.format_exc()
    logger.error(f"Unhandled exception {request.method} {request.url.path}\n{trace}")
    if DEBUG:
        return JSONResponse(status_code=500, content={"detail": "internal error", "trace": trace})
    return JSONResponse(status_code=500, content={"detail": "internal error"})


@app.exception_handler(404)
async def not_found_handler(request: Request, exc: HTTPException):
    accept = request.headers.get("accept", "")
    if "text/html" in accept or request.url.path.startswith("/admin/ui"):
        path = os.path.join(STATIC_DIR, "404.html")
        if os.path.exists(path):
            return FileResponse(path, status_code=404)
    return PlainTextResponse("404", status_code=404)


def strong_password(password: str) -> bool:
    if len(password) < 12:
        return False
    has_upper = any(c.isupper() for c in password)
    has_lower = any(c.islower() for c in password)
    has_digit = any(c.isdigit() for c in password)
    has_symbol = any(not c.isalnum() for c in password)
    return has_upper and has_lower and has_digit and has_symbol


def apply_policy_batch(agent_ids, payload):
    ok = []
    failed = []
    for agent_id in agent_ids:
        if not agent_id:
            failed.append({"agent_id": agent_id, "error": "empty agent_id"})
            continue
        try:
            set_policy(agent_id, payload.model_dump())
            ok.append(agent_id)
        except Exception as exc:
            failed.append({"agent_id": agent_id, "error": str(exc)})
    return {"status": "ok", "count": len(ok), "ok": ok, "failed": failed}


def get_user_mfa(username: str) -> str:
    secret = get_user_mfa_secret(username)
    if not secret:
        raise HTTPException(status_code=400, detail="mfa not bound")
    return secret
