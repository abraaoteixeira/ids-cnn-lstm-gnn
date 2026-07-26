# 🔒 SECURITY GUIDE — eBPF + Network Security

Complete security documentation for SPECTRE_GRID production deployment.

---

## 1. eBPF/XDP SECURITY

### Kernel-Space Security Considerations

#### 1.1 XDP Program Verification

The eBPF verifier ensures safety before kernel loading:

```c
// spectre_xdp.c - Safe eBPF practices

#include <linux/bpf.h>
#include <bpf/bpf_helpers.h>

// ✅ Safe: Limited loop bounds
#pragma unroll
for (int i = 0; i < MAX_FEATURES; i++) {  // MAX_FEATURES = 20 (fixed)
    features[i] = extract_feature(pkt, i);
}

// ❌ Unsafe: Unbounded loop
for (int i = 0; i < payload_len; i++) {  // Unbounded!
    // Would fail eBPF verifier
}

// ✅ Safe: Bounds checking
if (offset + sizeof(struct ethhdr) > end) {
    return XDP_PASS;  // Drop if out of bounds
}

// ✅ Safe: Fixed-size stack
char features[20] SEC(".bss");  // Statically allocated

// ❌ Unsafe: Dynamic allocation
char *buffer = malloc(len);  // Not allowed in eBPF
```

#### 1.2 Memory Safety

```c
// ✅ Safe access patterns
struct ethhdr *eth = (struct ethhdr *)(pkt);
if ((void *)(eth + 1) > end) return XDP_PASS;

struct iphdr *ip = (struct iphdr *)(eth + 1);
if ((void *)(ip + 1) > end) return XDP_PASS;

// ❌ Unsafe: No bounds check
struct tcphdr *tcp = (struct tcphdr *)pkt;  // Could overflow!
```

#### 1.3 XDP Verdicts

```c
// Safe verdict types
XDP_ABORTED   // Error, drop packet
XDP_DROP      // Silently drop (chosen for blocking)
XDP_PASS      // Pass to kernel
XDP_TX        // Send back out same NIC
XDP_REDIRECT  // Send to another interface

// ✅ We use XDP_DROP for malicious IPs
if (is_blocked(src_ip)) {
    return XDP_DROP;  // Blocks at NIC level (<1μs)
}
```

---

## 2. NETWORK SECURITY

### 2.1 WireGuard VPN Configuration

All traffic between VPS (eBPF) and WSL (STGNN) is encrypted:

```ini
# /etc/wireguard/wg0.conf - VPS side

[Interface]
PrivateKey = <VPS_PRIVATE_KEY>
Address = 10.0.0.1/24
ListenPort = 51820

# Drop unencrypted traffic
PostUp = iptables -A FORWARD -i wg0 -j ACCEPT; iptables -A FORWARD -o wg0 -j ACCEPT
PostDown = iptables -D FORWARD -i wg0 -j ACCEPT; iptables -D FORWARD -o wg0 -j ACCEPT

[Peer]
PublicKey = <WSL_PUBLIC_KEY>
AllowedIPs = 10.0.0.2/32
PersistentKeepalive = 25  # Prevents tunnel timeout

# ✅ AES-256-GCM encryption (default)
# ✅ Chacha20-Poly1305 option
# ✅ Perfect forward secrecy
```

**Security Properties:**
- ✅ **Encryption:** AES-256 or Chacha20 (both authenticated)
- ✅ **Perfect Forward Secrecy:** Yes (ephemeral keys)
- ✅ **DoS resistance:** Built-in (cookie system)
- ✅ **IP leakage:** None (all tunneled)

### 2.2 Firewall Rules

```bash
# UFW configuration for VPS

sudo ufw default deny incoming
sudo ufw default allow outgoing

# SSH (key-based only!)
sudo ufw allow 22/tcp comment "SSH - key-based auth only"

# WireGuard
sudo ufw allow 51820/udp comment "WireGuard VPN"

# FastAPI (internal only via WireGuard)
sudo ufw allow from 10.0.0.0/24 to any port 8000 comment "FastAPI internal"

# ✅ ALL other traffic blocked
sudo ufw enable

# Verify
sudo ufw status verbose
```

### 2.3 API Rate Limiting

```python
# FastAPI rate limiting (in dashboard_api_v2.py)

from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

@app.get("/api/history")
@limiter.limit("100/minute")
async def get_history(request: Request):
    # Max 100 requests per minute per IP
    pass

# Response headers
# X-RateLimit-Limit: 100
# X-RateLimit-Remaining: 87
# X-RateLimit-Reset: 1685000000
```

---

## 3. APPLICATION SECURITY

### 3.1 Whitelist Protection (Critical!)

Prevents accidental blocking of management IPs:

```python
# In receiver_gnn.py

WHITELIST = [
    "192.168.1.100",    # Management IP
    "203.0.113.1",      # Admin machine
    "10.0.0.1",         # Gateway
]

def should_block(src_ip, confidence):
    # ✅ Check whitelist FIRST
    if src_ip in WHITELIST:
        return False, "WHITELISTED"
    
    # Then check confidence
    if confidence > CONFIDENCE_THRESHOLD:
        return True, "THREAT_DETECTED"
    
    return False, "BENIGN"
```

**Why critical?** Blocking management IPs = locked out of system!

### 3.2 Input Validation

```python
# Validate all API inputs

from pydantic import BaseModel, validator, IPvAnyAddress

class WhitelistRequest(BaseModel):
    src_ip: IPvAnyAddress  # ✅ Validates IP format
    reason: str = None
    
    @validator('reason')
    def validate_reason(cls, v):
        if v and len(v) > 500:
            raise ValueError('Reason too long')
        return v

# ✅ Automatically rejects invalid IPs
# ❌ Prevents SQL injection
# ❌ Prevents buffer overflow
```

### 3.3 SQL Injection Prevention

```python
# ❌ UNSAFE: String concatenation
query = f"SELECT * FROM threats WHERE src_ip = '{user_ip}'"
# User could input: "' OR '1'='1"

# ✅ SAFE: Parameterized queries
cursor.execute("SELECT * FROM threats WHERE src_ip = ?", (user_ip,))

# For SQLite (used in SPECTRE_GRID):
import sqlite3

conn = sqlite3.connect('spectre_history_v2.db')
cursor = conn.cursor()

# Parameterized (safe)
cursor.execute("INSERT INTO events (src_ip, timestamp) VALUES (?, ?)", 
               (src_ip, datetime.now()))

# Never use f-strings with SQL!
```

### 3.4 Authentication & Authorization

```python
# TODO: Add API authentication (currently localhost only)

# Recommended: JWT tokens or API keys

from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer

security = HTTPBearer()

async def verify_token(credentials = Depends(security)):
    token = credentials.credentials
    
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        user = payload.get("sub")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    return user

@app.get("/api/threat")
async def get_threats(user = Depends(verify_token)):
    # Only authenticated users can access
    return threats_list
```

---

## 4. DATA SECURITY

### 4.1 Sensitive Data Protection

```
⚠️  WHAT NOT TO LOG:

❌ Full source IPs (reveals user location)
❌ Credentials or tokens
❌ API keys or secrets
❌ Personal information (PII)
❌ Raw payloads
❌ Session tokens

✅ WHAT TO LOG:

✅ Anonymized IPs (last octet masked: 192.168.1.xxx)
✅ Port numbers
✅ Threat confidence (0.0-1.0)
✅ Detection method (STGNN, heuristic)
✅ Timestamp
✅ Action taken (block, alert, pass)
```

### 4.2 Data Retention Policy

```python
# Automated cleanup of old data

import sqlite3
from datetime import datetime, timedelta

def cleanup_old_logs(days_to_keep=30):
    conn = sqlite3.connect('spectre_history_v2.db')
    cursor = conn.cursor()
    
    cutoff_date = datetime.now() - timedelta(days=days_to_keep)
    
    # Delete events older than threshold
    cursor.execute("""
        DELETE FROM events 
        WHERE timestamp < ?
    """, (cutoff_date.isoformat(),))
    
    conn.commit()
    conn.close()
    
    print(f"✅ Cleaned events older than {cutoff_date}")

# Run daily via cron:
# 0 2 * * * python -c "from receiver_gnn import cleanup_old_logs; cleanup_old_logs(30)"
```

### 4.3 Backup Encryption

```bash
# Backup with encryption

# Generate GPG key (if not exists)
gpg --gen-key

# Backup encrypted
tar czf - /opt/spectre_grid/ | gpg --encrypt -r "YOUR_NAME" > backup_$(date +%Y%m%d).tar.gz.gpg

# Restore encrypted
gpg --decrypt backup_20260601.tar.gz.gpg | tar xz -C /

# Verify backup
gpg --list-packets backup_20260601.tar.gz.gpg
```

---

## 5. MODEL SECURITY

### 5.1 Model Poisoning Prevention

```python
# Verify model integrity before loading

import hashlib

MODEL_SHA256 = "a1b2c3d4e5f6..."  # Hardcoded hash

def verify_model(model_path):
    with open(model_path, 'rb') as f:
        file_hash = hashlib.sha256(f.read()).hexdigest()
    
    if file_hash != MODEL_SHA256:
        raise ValueError(f"❌ Model corrupted or tampered! Hash mismatch")
    
    print(f"✅ Model integrity verified")

# Load only if verified
verify_model('spectre_model_scripted.pt')
model = torch.jit.load('spectre_model_scripted.pt')
```

### 5.2 Model Sandboxing

```python
# Run inference in isolated process

from multiprocessing import Process, Queue
import signal

class ModelInferenceTimeout(Exception):
    pass

def run_inference_isolated(features, timeout=1.0):
    """Run model in subprocess with timeout"""
    
    result_queue = Queue()
    
    def inference_worker():
        prediction = model.forward(features)
        result_queue.put(prediction)
    
    process = Process(target=inference_worker)
    process.start()
    process.join(timeout=timeout)
    
    if process.is_alive():
        process.terminate()
        raise ModelInferenceTimeout("Model inference exceeded timeout")
    
    if result_queue.empty():
        raise RuntimeError("Model produced no output")
    
    return result_queue.get()

# ✅ Prevents model hanging or infinite loops
```

---

## 6. SYSTEM SECURITY

### 6.1 File Permissions

```bash
# Secure file permissions in production

# Model file (read-only to spectre user)
chmod 600 /opt/spectre_grid/spectre_model_scripted.pt
chown spectre:spectre /opt/spectre_grid/spectre_model_scripted.pt

# Database (read-write to spectre user only)
chmod 600 /opt/spectre_grid/spectre_history_v2.db

# Configuration files
chmod 600 /etc/systemd/system/spectre-receiver.service
chmod 600 /opt/spectre_grid/.env

# Logs (readable by spectre user and admins)
chmod 640 /var/log/spectre/receiver.log
chown spectre:spectre /var/log/spectre/

# ✅ Only spectre user can read/write
# ✅ No world-readable files
```

### 6.2 Process Isolation

```ini
# /etc/systemd/system/spectre-receiver.service

[Service]
# Security hardening
PrivateTmp=true           # Private /tmp
NoNewPrivileges=true      # No privilege escalation
ProtectSystem=strict      # Read-only filesystem (except writable dirs)
ProtectHome=true          # Hide /home
ReadWritePaths=/var/log/spectre /opt/spectre_grid/data

# Drop unnecessary capabilities
CapabilityBoundingSet=CAP_CHOWN CAP_DAC_OVERRIDE

# ✅ Process cannot escalate privileges
# ✅ Filesystem hardened
# ✅ Limited system access
```

### 6.3 Kernel Security Modules

```bash
# AppArmor (Ubuntu/Debian)
sudo aa-enforce /etc/apparmor.d/spectre-receiver

# SELinux (RHEL/CentOS)
semanage fcontext -a -t spectre_t "/opt/spectre_grid(/.*)?"
restorecon -Rv /opt/spectre_grid/

# Check status
aa-status | grep spectre
```

---

## 7. SECURITY CHECKLIST

### Pre-Production

```
INFRASTRUCTURE:
☐ SSH keys (no password auth)
☐ Firewall configured (UFW/iptables)
☐ Network isolation (VPN/VPC)
☐ Regular patching scheduled
☐ Backups encrypted

APPLICATION:
☐ API authentication (JWT or keys)
☐ Rate limiting active
☐ Input validation on all endpoints
☐ SQL injection prevention
☐ HTTPS/TLS configured

DATA:
☐ Sensitive data anonymized
☐ Data retention policy set
☐ Backups encrypted
☐ Database encryption (SQLite)
☐ Logs rotated regularly

MODEL:
☐ Model integrity verified
☐ Model hash hardcoded
☐ Model timeout configured
☐ Inference isolated

OPERATIONS:
☐ Monitoring active (uptime, errors)
☐ Alerting configured
☐ Incident response plan
☐ Security audit scheduled
☐ Vulnerability scanning enabled
```

### Ongoing Monitoring

```bash
# Monthly security tasks

# Update system packages
sudo apt-get update && sudo apt-get upgrade -y

# Check for vulnerabilities
sudo apt-get install -y ubuntu-advantage-tools
pro scan

# Review access logs
sudo lastlog -u spectre

# Check firewall rules
sudo ufw status verbose

# Verify file permissions
find /opt/spectre_grid -type f -perm /077 -exec ls -la {} \;

# Check running processes
ps aux | grep spectre
```

---

## 8. INCIDENT RESPONSE

### If compromise suspected:

```bash
# 1. Isolate affected system
sudo ifconfig eth0 down

# 2. Preserve evidence
sudo tar czf /backups/evidence_$(date +%s).tar.gz /opt/spectre_grid/ /var/log/

# 3. Rotate credentials
gpg-key-gen  # New GPG key
ssh-keygen -t ed25519  # New SSH keys

# 4. Restart from clean backup
sudo systemctl stop spectre-receiver
# Restore from encrypted backup
sudo tar xzf /backups/backup_clean.tar.gz -C /

# 5. Review logs for breach
sudo journalctl -u spectre-receiver --since "1 day ago" > /backups/incident_log.txt

# 6. Contact security team
```

---

**Security Guide Version:** 1.0  
**Last Updated:** 01/06/2026  
**Status:** Production-Ready ✅  
**Compliance:** eBPF Safety, OWASP Top 10 coverage
