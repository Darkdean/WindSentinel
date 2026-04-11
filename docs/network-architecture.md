# WindSentinel Network Architecture

## Current known flows
- Agent -> Server: health upload
- Agent -> Server: log upload
- Agent -> Server: policy fetch
- Admin UI -> Server: management APIs

## V1 constraints
- remote shell networking is excluded from V1
- any admin-issued client stop/uninstall command must be auditable
- deployment docs must specify required ports and connectivity

## To be completed
- endpoint inventory
- port/protocol table
- firewall guidance for CentOS/Ubuntu
- trust boundary notes
