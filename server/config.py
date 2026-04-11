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

POSTGRES_DSN = os.getenv("WINDSENTINEL_POSTGRES_DSN") or os.getenv("WINDSENTINEL_DATABASE_URL")
POSTGRES_HOST = os.getenv("WINDSENTINEL_DB_HOST", "127.0.0.1")
POSTGRES_PORT = int(os.getenv("WINDSENTINEL_DB_PORT", "5432"))
POSTGRES_DB = os.getenv("WINDSENTINEL_DB_NAME", "windsentinel")
POSTGRES_USER = os.getenv("WINDSENTINEL_DB_USER", "windsentinel")
POSTGRES_PASSWORD = os.getenv("WINDSENTINEL_DB_PASSWORD", "windsentinel")
POSTGRES_SSLMODE = os.getenv("WINDSENTINEL_DB_SSLMODE", "prefer")


def build_postgres_dsn() -> str:
    if POSTGRES_DSN:
        return POSTGRES_DSN
    return (
        f"dbname={POSTGRES_DB} user={POSTGRES_USER} password={POSTGRES_PASSWORD} "
        f"host={POSTGRES_HOST} port={POSTGRES_PORT} sslmode={POSTGRES_SSLMODE}"
    )
