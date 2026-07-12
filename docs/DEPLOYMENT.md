# 🚀 DEPLOYMENT GUIDE — Production Deployment

Complete guide to deploying SPECTRE_GRID in production environment.

---

## 1. PRE-DEPLOYMENT CHECKLIST

Before deploying to production, verify:

```
INFRASTRUCTURE:
☐ VPS GCP/AWS provisioned (2vCPU, 2GB RAM minimum)
☐ WSL2 on Windows with GPU support (optional but recommended)
☐ Network: Public IP + firewall rules configured
☐ Storage: 100GB SSD available for logs + data

SYSTEM:
☐ Linux kernel ≥5.8 (for eBPF/XDP support)
☐ Python 3.9+ installed and working
☐ Git installed and repository cloned
☐ Required Python packages: pip install -r requirements.txt

CERTIFICATES:
☐ WireGuard keys generated
☐ SSL/TLS certificates ready (if using HTTPS)
☐ Firewall rules allow ports: 22 (SSH), 51820 (WireGuard), 8000 (API)

BACKUPS:
☐ Database backup strategy in place
☐ Configuration files backed up
☐ Model weights (spectre_model_scripted.pt) backed up
```

---

## 2. DEPLOYMENT STEPS

### Step 1: Clone Repository

```bash
git clone https://github.com/abraaoteixeira/ids-cnn-lstm-gnn.git
cd ids-cnn-lstm-gnn
```

### Step 2: Setup Python Environment

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Verify installation
python -c "import torch; print(f'PyTorch: {torch.__version__}')"
```

### Step 3: Configure eBPF Kernel Module

```bash
# Check kernel version (must be ≥5.8)
uname -r

# Check eBPF support
cat /boot/config-$(uname -r) | grep CONFIG_BPF

# Compile eBPF program
cd ebpf/
clang -O2 -target bpf -c spectre_xdp.c -o spectre_xdp.o

# Verify bytecode
llvm-objdump -S spectre_xdp.o | head -20
cd ..
```

### Step 4: Load Model

```bash
# Download pre-trained model (if not in repo)
# wget https://your-repo/models/spectre_model_scripted.pt

# Verify model loads
python3 -c "import torch; m = torch.jit.load('spectre_model_scripted.pt'); print('✅ Model loaded')"
```

### Step 5: Setup WireGuard VPN (if using remote deployment)

```bash
# Generate keys
wg genkey | tee privatekey | wg pubkey > publickey

# Configure WireGuard interface
sudo vim /etc/wireguard/wg0.conf
```

**wg0.conf template:**
```
[Interface]
PrivateKey = <your-private-key>
Address = 10.0.0.1/24
ListenPort = 51820

[Peer]
PublicKey = <receiver-public-key>
AllowedIPs = 10.0.0.2/32
PersistentKeepalive = 25
```

```bash
# Start WireGuard
sudo wg-quick up wg0
sudo systemctl enable wg-quick@wg0
```

### Step 6: Configure Systemd Service

Create `/etc/systemd/system/spectre-receiver.service`:

```ini
[Unit]
Description=SPECTRE_GRID Receiver (STGNN + Ensemble)
After=network.target

[Service]
Type=simple
User=spectre
WorkingDirectory=/opt/spectre_grid
ExecStart=/opt/spectre_grid/venv/bin/python receiver_gnn.py

# Restart policy
Restart=always
RestartSec=10

# Logging
StandardOutput=journal
StandardError=journal
SyslogIdentifier=spectre-receiver

# Security
NoNewPrivileges=true
PrivateTmp=true

# Resource limits
LimitNOFILE=65536
LimitNPROC=4096

[Install]
WantedBy=multi-user.target
```

### Step 7: Create Spectre User (security best practice)

```bash
# Create non-root user
sudo useradd -m -s /bin/bash spectre
sudo usermod -a -G docker spectre  # If using Docker

# Setup permissions
sudo chown -R spectre:spectre /opt/spectre_grid
sudo chmod 755 /opt/spectre_grid
```

### Step 8: Start Services

```bash
# Reload systemd
sudo systemctl daemon-reload

# Start receiver
sudo systemctl start spectre-receiver

# Enable on boot
sudo systemctl enable spectre-receiver

# Check status
sudo systemctl status spectre-receiver

# View logs
journalctl -u spectre-receiver -f
```

### Step 9: Load eBPF Program

```bash
# As root, load XDP program on NIC
sudo ip link set dev eth0 xdp obj spectre_xdp.o sec xdp

# Verify
ip link show eth0

# Unload (if needed)
sudo ip link set dev eth0 xdp off
```

### Step 10: Verify Deployment

```bash
# Test API health
curl http://localhost:8000/health

# Expected response:
# {"status":"ok","uptime_seconds":45,"threats_detected":0}

# Test WebSocket
wscat -c ws://localhost:8000/ws/threats
# Should see connection established

# Check logs
tail -f /var/log/spectre/receiver.log

# Monitor system
htop  # Should show receiver_gnn.py process
```

---

## 3. PRODUCTION CHECKLIST

After deployment, verify:

```
SYSTEM HEALTH:
☐ API responds to /health endpoint
☐ WebSocket connection works
☐ Database (SQLite) accessible
☐ eBPF module loaded and capturing packets
☐ CPU usage <30%, Memory usage <50%
☐ No error logs in journalctl

FUNCTIONALITY:
☐ Model inference working (<200ms latency)
☐ Ensemble logic active
☐ Threat detection firing (test with port scan)
☐ Block list updating correctly
☐ Whitelist protecting management IPs
☐ GeoIP enrichment working

MONITORING:
☐ Uptime tracking (target: >99%)
☐ Alert system configured
☐ Log rotation setup
☐ Backup schedule active
☐ Dashboard accessible

SECURITY:
☐ Firewall rules restrictive (only needed ports)
☐ SSH key-based auth only (no password)
☐ WireGuard tunnel encrypted
☐ Model file permissions: 600 (read-only to spectre user)
☐ Database file permissions: 600
☐ No sensitive data in logs
```

---

## 4. MONITORING & MAINTENANCE

### Uptime Monitoring

```bash
# Install monitoring tool
sudo apt-get install -y monit

# Configure monit to restart spectre-receiver if it crashes
cat > /etc/monit/monitrc << 'EOF'
check process spectre with pidfile /run/spectre.pid
  start program = "/bin/systemctl start spectre-receiver"
  stop program = "/bin/systemctl stop spectre-receiver"
  if failed port 8000 type TCP then restart
  if 5 restarts within 5 cycles then alert
EOF

sudo service monit restart
```

### Log Rotation

Create `/etc/logrotate.d/spectre`:

```
/var/log/spectre/*.log {
    daily
    rotate 14
    compress
    delaycompress
    notifempty
    create 0600 spectre spectre
    postrotate
        systemctl reload spectre-receiver > /dev/null 2>&1 || true
    endscript
}
```

### Database Backups

```bash
#!/bin/bash
# backup_spectre.sh

BACKUP_DIR=/backups/spectre
DATE=$(date +%Y%m%d_%H%M%S)

# Backup SQLite database
cp /opt/spectre_grid/spectre_history_v2.db $BACKUP_DIR/db_$DATE.db

# Backup JSONL logs
cp /opt/spectre_grid/data/logs/*.jsonl $BACKUP_DIR/logs_$DATE.tar.gz

# Keep only last 30 days
find $BACKUP_DIR -mtime +30 -delete

echo "✅ Backup completed: $DATE"
```

### Performance Monitoring

```bash
# Monitor key metrics
watch -n 5 '
  echo "=== SPECTRE_GRID Metrics ===";
  echo "Uptime: $(systemctl is-active spectre-receiver)";
  echo "Memory: $(ps aux | grep receiver_gnn | grep -v grep | awk "{print \$6}")MB";
  echo "CPU: $(ps aux | grep receiver_gnn | grep -v grep | awk "{print \$3}")%";
  echo "Recent events: $(tail -c 100 /var/log/spectre/receiver.log)";
'
```

---

## 5. SCALING & HIGH AVAILABILITY

### Multi-Node Deployment

For HA setup with multiple receivers:

```
                ┌──────────────────┐
                │   Load Balancer  │
                │   (HAProxy)      │
                └────────┬─────────┘
                         │
         ┌───────────────┼───────────────┐
         │               │               │
      ┌──▼──┐         ┌──▼──┐        ┌──▼──┐
      │ REC │         │ REC │        │ REC │
      │ VR1 │         │ VR2 │        │ VR3 │
      └─────┘         └─────┘        └─────┘
         │               │               │
         └───────────────┼───────────────┘
                         │
                  ┌──────▼──────┐
                  │ Shared DB   │
                  │ (PostgreSQL)│
                  └─────────────┘
```

**HAProxy configuration** (`/etc/haproxy/haproxy.cfg`):

```
global
    log /dev/log local0
    stats socket /run/haproxy/admin.sock mode 660 level admin

defaults
    mode http
    timeout connect 5000ms
    timeout client 50000ms
    timeout server 50000ms

frontend spectre_frontend
    bind *:8000
    default_backend spectre_receivers

backend spectre_receivers
    balance roundrobin
    server recv1 10.0.0.101:8000 check
    server recv2 10.0.0.102:8000 check
    server recv3 10.0.0.103:8000 check
```

---

## 6. DISASTER RECOVERY

### Backup & Restore Procedure

```bash
# Full system backup
tar -czf /backups/spectre_full_$(date +%Y%m%d).tar.gz \
    /opt/spectre_grid/ \
    /etc/systemd/system/spectre-*.service \
    /etc/wireguard/

# Restore from backup
tar -xzf /backups/spectre_full_20260601.tar.gz -C /

# Restore database from snapshot
cp /backups/db_20260601.db /opt/spectre_grid/spectre_history_v2.db
```

### Rollback Procedure

If new model causes issues:

```bash
# Stop current version
sudo systemctl stop spectre-receiver

# Restore previous model
cp /backups/model_v1.pt /opt/spectre_grid/spectre_model_scripted.pt

# Restart
sudo systemctl start spectre-receiver

# Verify
curl http://localhost:8000/health
```

---

## 7. TROUBLESHOOTING DEPLOYMENT

| Issue | Cause | Solution |
|-------|-------|----------|
| Port 8000 already in use | Another process | `sudo lsof -i :8000` then kill |
| eBPF load fails | Kernel <5.8 | Upgrade kernel or use older version |
| Model inference slow | GPU not available | Check CUDA, fallback to CPU |
| Database locked | Concurrent access | Restart service, check file permissions |
| High memory usage | Memory leak | Monitor with `top`, restart if >1GB |
| Threats not detected | Model issue | Verify model weights, check logs |

---

## 8. PRODUCTION ENVIRONMENT VARIABLES

Create `.env` file:

```bash
# API Configuration
API_HOST=0.0.0.0
API_PORT=8000
API_DEBUG=False

# Model Configuration
MODEL_PATH=/opt/spectre_grid/spectre_model_scripted.pt
CONFIDENCE_THRESHOLD=0.70
ENSEMBLE_ENABLED=True

# Database
DB_PATH=/opt/spectre_grid/spectre_history_v2.db

# Logging
LOG_LEVEL=INFO
LOG_FILE=/var/log/spectre/receiver.log

# eBPF
EBPF_XDP_PROGRAM=spectre_xdp.o
EBPF_INTERFACE=eth0

# WireGuard
WG_INTERFACE=wg0
WG_LISTEN_PORT=51820

# Monitoring
HEALTHCHECK_INTERVAL=300  # seconds
METRICS_EXPORT_PATH=/var/metrics/spectre.prom
```

---

## 9. POST-DEPLOYMENT MONITORING

### Prometheus Metrics (Optional)

```python
# In receiver_gnn.py, add Prometheus instrumentation

from prometheus_client import Counter, Histogram, start_http_server

# Metrics
threat_counter = Counter('spectre_threats_total', 'Total threats detected')
latency_histogram = Histogram('spectre_inference_ms', 'Inference latency in ms')
block_counter = Counter('spectre_blocks_total', 'Total IP blocks')

# In main loop:
with latency_histogram.time():
    prediction = model.forward(features)

if prediction > threshold:
    threat_counter.inc()
    block_counter.inc()
```

### Grafana Dashboard

Create dashboard to visualize:
- Threats per hour
- Top attacked ports
- Geographic distribution
- Detection latency
- System resource usage
- Uptime percentage

---

## 10. COMPLIANCE & SECURITY

### Data Privacy

```
☐ Personal data anonymization (IP last octet)
☐ GDPR compliance (right to be forgotten)
☐ Data retention policy (delete old logs)
☐ Access logs encrypted
☐ Sensitive data never logged in plaintext
```

### Security Hardening

```bash
# Disable SSH password auth
sudo sed -i 's/#PasswordAuthentication yes/PasswordAuthentication no/' /etc/ssh/sshd_config

# Enable firewall
sudo ufw enable
sudo ufw default deny incoming
sudo ufw allow 22/tcp
sudo ufw allow 51820/udp
sudo ufw allow 8000/tcp

# Keep system updated
sudo apt-get update && sudo apt-get upgrade -y

# Install fail2ban (brute force protection)
sudo apt-get install -y fail2ban
```

---

**Deployment Guide Version:** 1.0  
**Last Updated:** 01/06/2026  
**Status:** Production Ready ✅
