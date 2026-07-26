# pfSense Border Defense Integration

This module integrates the SPECTRE GRID Intrusion Detection System (IDS) with a pfSense border gateway. It enables the IDS to dynamically block malicious IPs on the network perimeter.

## Directory Structure

```
backend/
├── app/
│   └── defense/
│       ├── __init__.py
│       ├── pfsense.py     # Main pfSenseBlocker class
│       └── README.md      # This documentation file
└── tests/
    ├── __init__.py
    ├── test_pfsense.py    # Mock tests for PfSenseBlocker
    └── test_dashboard_routes.py # Mock tests for Dashboard API routes
```

## Prerequisite Setup on pfSense

To allow SPECTRE GRID to authenticate and execute firewall changes on the pfSense gateway:

### 1. SSH Authentication Method (Recommended)
- **Enable SSH**: Go to `System > Advanced > Admin Access` in the pfSense WebGUI and check **Enable Secure Shell**.
- **Configure User & Keys**: It is highly recommended to use SSH key-based authentication.
  - Go to `System > User Manager` and add a new user or use the default `admin`.
  - Add your SSH public key (`id_rsa.pub`) to the user's **Authorized SSH Keys** section.
- **Easyrule Utility**: pfSense comes with the `easyrule` command-line utility pre-installed. The SSH blocker executes `easyrule block {interface} {ip}`.

### 2. API Method
- If you use a REST API package on pfSense (e.g. pfSense-API or FauxAPI), you can use the `api` method.
- The module sends JSON payloads to the configured host to register blocked addresses in aliases.

### 3. XML-RPC Method
- Requires the admin user and password. It runs PHP shell scripts inside pfSense using the built-in XML-RPC service (`pfsense.exec_php`).

---

## Configuration Variables

Configure the integration using the following environment variables (defined in your system or in a `.env` file):

| Variable Name | Description | Default |
|---|---|---|
| `PFSENSE_ENABLED` | Set to `true` to activate automated blocking on threat detection. | `false` |
| `PFSENSE_HOST` | Hostname or IP address of the pfSense gateway. | *Required if enabled* |
| `PFSENSE_USER` | Username for pfSense authentication (SSH/API/XML-RPC). | *Required if enabled* |
| `PFSENSE_PASS` | Password (required for password SSH, API basic auth, or XML-RPC). | *Optional* |
| `PFSENSE_SSH_KEY_PATH` | Path to the private SSH key file on the host running the API. | *Optional* |
| `PFSENSE_INTERFACE` | Network interface to apply block rules on pfSense (e.g. `wan`, `lan`). | `wan` |
| `PFSENSE_METHOD` | Authentication/connection method: `ssh`, `api`, or `xmlrpc`. | `ssh` |

---

## Integration Details

### Automatic Threat Blocking
When the dashboard API receives a threat log via the Unix Domain Socket (IPC):
1. It validates the alert payload (`is_threat == true`).
2. If `PFSENSE_ENABLED` is true, it schedules the block operation.
3. To protect the main network processing thread and socket read loop from I/O blocks (caused by network latency to the gateway), the blocker is executed asynchronously using Python's `asyncio.get_running_loop().run_in_executor()`.

### Manual Blocking & Unblocking REST Endpoints
The dashboard exposes the following endpoints:

#### 1. Block IP
- **Route**: `POST /api/defense/block`
- **Request Body**:
  ```json
  {
    "ip": "192.168.100.22",
    "interface": "wan"
  }
  ```
- **Response**:
  ```json
  {
    "status": "success",
    "message": "IP 192.168.100.22 blocked successfully on pfSense."
  }
  ```

#### 2. Unblock IP
- **Route**: `POST /api/defense/unblock`
- **Request Body**:
  ```json
  {
    "ip": "192.168.100.22"
  }
  ```
- **Response**:
  ```json
  {
    "status": "success",
    "message": "IP 192.168.100.22 unblocked successfully on pfSense."
  }
  ```
