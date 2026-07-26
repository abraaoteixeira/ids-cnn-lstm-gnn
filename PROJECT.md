# Project: SPECTRE GRID IaC, pfSense Integration, and Dockerization

## Architecture
SPECTRE GRID is a hybrid Intrusion Detection/Prevention System (IDS/IPS) consisting of:
1. **eBPF/XDP C++ Host Engine**: Runs directly on the host kernel space and user space. Intercepts and parses network packets. Communicates with the FastAPI backend using a Unix Domain Socket (UDS) at `/var/run/spectre/spectre.sock`.
2. **FastAPI Backend (Docker Container)**: Receives alerts and stats from the C++ Engine via the UDS socket. Triggers defense mechanisms and exposes REST endpoints. Integrates the pfSense module to block malicious IPs at the gateway.
3. **React Frontend (Docker Container - Nginx)**: Renders the dashboard and configuration panel, interacting with the FastAPI backend.
4. **Ansible Playbook**: automates dependency installation, C++ Engine compilation, and systemd service setup.
5. **pfSense Integration**: A Python integration module that communicates with pfSense (via SSH or XML-RPC or API) to add IPs to a target blocklist alias.

```
+-------------------------------------------------------------+
| Linux Host                                                  |
|  +------------------------+                                 |
|  | C++ Engine (Host)      |                                 |
|  | - eBPF/XDP Driver      |                                 |
|  | - Unix Domain Socket   |                                 |
|  +-----------+------------+                                 |
|              | (Mounts UDS Socket Volume)                   |
|              v                                              |
|  +------------------------+                                 |
|  | Docker Compose         |                                 |
|  |  +------------------+  |                                 |
|  |  | FastAPI Backend  |  |                                 |
|  |  | - API Server     |  |                                 |
|  |  | - pfSense Module |=======> pfSense Gateway (SSH/API)  |
|  |  +--------^---------+  |                                 |
|  |           | (JSON)     |                                 |
|  |  +--------v---------+  |                                 |
|  |  | React Frontend   |  |                                 |
|  |  | - Nginx Server   |  |                                 |
|  |  +------------------+  |                                 |
|  +------------------------+                                 |
+-------------------------------------------------------------+
```

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|---|---|---|---|
| 1 | Repository Exploration & Path Cleanup | Scan workspace for absolute Windows paths and clean them up | None | PLANNED |
| 2 | pfSense Integration Module | Python/Shell integration with mock unit tests to block IPs on pfSense | None | PLANNED |
| 3 | IaC Ansible Setup | Playbook `deploy/ansible/spectre_deploy.yml` with dependencies, LibTorch, build steps, and syntax-check | M1 | PLANNED |
| 4 | Dockerization | FastAPI Dockerfile, React Dockerfile with Nginx, and docker-compose.yml with Unix Socket volumes | M2 | PLANNED |
| 5 | E2E Verification & Auditing | Integration tests, container boot verification, and Forensic Audit check | M3, M4 | PLANNED |

## Interface Contracts
### 1. Unix Domain Socket (C++ Host Engine <-> FastAPI Backend)
- Path on Host: `/var/run/spectre/spectre.sock` (mapped via Docker volume to container `/var/run/spectre/spectre.sock`)
- Protocol: JSON messages over stream socket.
- Message Format (Alert):
  ```json
  {
    "type": "ALERT",
    "src_ip": "192.168.1.100",
    "dst_ip": "192.168.1.1",
    "reason": "DDoS attempt detected by STGNN",
    "severity": "CRITICAL",
    "timestamp": 1690000000
  }
  ```

### 2. pfSense Integration Interface (Python)
- File: `backend/app/defense/pfsense.py` (or similar location)
- Class: `PfSenseBlocker`
- Methods:
  - `block_ip(ip: str) -> bool`: Adds the IP address to the pfSense alias. Returns `True` on success.
  - `unblock_ip(ip: str) -> bool`: Removes the IP address from the pfSense alias.
  - `is_ip_blocked(ip: str) -> bool`: Checks if IP is in the alias list.
- Parameters needed: URL/Host, Username, Password/SSH-Key, Alias Name.

### 3. Docker Compose Volume Layout
- Socket Volume:
  - `spectre_socket_vol:/var/run/spectre` (shared between FastAPI service and host `/var/run/spectre` if possible, or bind mount `/var/run/spectre:/var/run/spectre`).

## Code Layout
- `deploy/ansible/spectre_deploy.yml` - Ansible playbook
- `backend/` - FastAPI backend application directory
- `backend/Dockerfile` - Dockerfile for backend
- `backend/app/defense/pfsense.py` - pfSense integration module
- `backend/tests/test_pfsense.py` - Mocked unit tests for pfSense integration
- `frontend/` - React frontend application directory
- `frontend/Dockerfile` - Dockerfile for React (Nginx based)
- `docker-compose.yml` - Docker compose file at root
