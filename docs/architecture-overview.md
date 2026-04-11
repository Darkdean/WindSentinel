# WindSentinel Architecture Overview

## Current architecture
- Rust agent in `src/`
- Python FastAPI server in `server/`
- static admin UI in `server/static/`
- SQLite persistence in `server/`

## V1 architectural goals
- Linux-first release hardening
- systemd-managed agent residency
- bare-metal server/admin deployment first
- Docker Compose artifact after bare-metal deployment is complete
- remote shell excluded from V1

## To be detailed during implementation
- deployment topology
- trust boundaries
- anti-tamper boundary and authorization model
- release packaging flow
