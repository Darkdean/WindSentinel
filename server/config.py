import os


def _env_bool(key: str, default: bool = False) -> bool:
    value = os.getenv(key)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


DEBUG = _env_bool("WINDSENTINEL_DEBUG", True)
LOG_LEVEL = os.getenv("WINDSENTINEL_LOG_LEVEL", "INFO").upper()
LOG_FILE = os.getenv("WINDSENTINEL_LOG_FILE")
LOG_REQUEST_BODY = _env_bool("WINDSENTINEL_LOG_REQUEST_BODY", False)
MFA_ISSUER = os.getenv("WINDSENTINEL_MFA_ISSUER", "WindSentinel")
