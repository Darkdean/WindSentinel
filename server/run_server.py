import argparse
import os
from pathlib import Path

import uvicorn


def default_app_dir() -> Path:
    return Path(__file__).resolve().parent


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the WindSentinel server on Linux or macOS")
    parser.add_argument("--host", default=os.getenv("WINDSENTINEL_SERVER_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.getenv("WINDSENTINEL_SERVER_PORT", "8000")))
    parser.add_argument(
        "--reload",
        action="store_true" if os.getenv("WINDSENTINEL_SERVER_RELOAD") in {"1", "true", "yes", "on"} else "store_false",
        default=os.getenv("WINDSENTINEL_SERVER_RELOAD", "0").strip().lower() in {"1", "true", "yes", "on"},
        help="Enable uvicorn reload mode for local development",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    uvicorn.run(
        "main:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        app_dir=str(default_app_dir()),
    )


if __name__ == "__main__":
    main()
