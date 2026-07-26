# 📡 API DOCUMENTATION — SPECTRE_GRID

FastAPI REST/WebSocket API for real-time threat monitoring and control.

**Base URL:** `http://localhost:8000`  
**WebSocket:** `ws://localhost:8000/ws/threats`

---

## 1. REST ENDPOINTS

### Health & Status

#### `GET /health`
System health check.

**Response (200):**
```json
{
  "status": "ok",
  "uptime_seconds": 86400,
  "threats_detected": 2939,
  "avg_latency_ms": 125.5
}
```

---

#### `GET /status`
Current system status with detailed metrics.

**Response (200):**
```json
{
  "system": {
    "uptime": "23h 45m 12s",
    "cpu_usage": 15.2,
    "memory_usage": 45.8
  },
  "model": {
    "name": "STGNN-v1.0",
    "f1_score_lab": 0.9856,
    "status": "inference",
    "last_updated": "2026-05-31T15:30:00Z"
  },
  "detector": {
    "threats_today": 2939,
    "unique_ips": 39,
    "unique_ports": 1,
    "avg_confidence": 0.253
  }
}
```

---

### History & Analytics

#### `GET /api/history`
Get historical threat events with filtering.

**Query Parameters:**
- `limit` (int, default=100): Max results to return
- `offset` (int, default=0): Pagination offset
- `src_ip` (str, optional): Filter by source IP
- `country` (str, optional): Filter by country
- `min_confidence` (float, default=0.0): Min STGNN confidence
- `start_time` (ISO8601, optional): Start timestamp filter
- `end_time` (ISO8601, optional): End timestamp filter

**Example:**
```
GET /api/history?limit=50&offset=0&min_confidence=0.7&country=BR
```

**Response (200):**
```json
{
  "total": 458,
  "returned": 50,
  "offset": 0,
  "events": [
    {
      "id": "evt_001",
      "timestamp": "2026-05-31T14:23:45Z",
      "src_ip": "177.5.130.126",
      "dst_port": 22,
      "protocol": "TCP",
      "probability": 0.99,
      "is_threat": true,
      "country": "BR",
      "city": "Palhoça",
      "detection_method": "STGNN",
      "action": "BAN"
    },
    ...
  ]
}
```

---

#### `GET /api/statistics`
Aggregated statistics for dashboard.

**Response (200):**
```json
{
  "summary": {
    "total_events": 2939,
    "unique_sources": 39,
    "detection_rate": 55.2,
    "false_positive_rate": 1.2
  },
  "by_country": {
    "USA": 1234,
    "BR": 420,
    "CN": 350,
    "RU": 280,
    "DE": 220,
    "Others": 435
  },
  "by_port": {
    "22": 2851,
    "3389": 80,
    "23": 8
  },
  "by_hour": {
    "00": 120,
    "01": 145,
    "02": 98,
    ...
  },
  "confidence_distribution": {
    "high": 150,
    "medium": 250,
    "low": 2539
  }
}
```

---

#### `GET /api/top-attackers`
Top 10 attacking IP addresses.

**Query Parameters:**
- `limit` (int, default=10): Number of top attackers

**Response (200):**
```json
{
  "attackers": [
    {
      "rank": 1,
      "src_ip": "177.5.130.126",
      "country": "BR",
      "city": "Palhoça",
      "events": 419,
      "confidence_avg": 0.92,
      "ports": [22],
      "last_seen": "2026-05-31T23:59:45Z"
    },
    {
      "rank": 2,
      "src_ip": "45.33.32.157",
      "country": "USA",
      "city": "Newark",
      "events": 145,
      "confidence_avg": 0.45,
      "ports": [22, 3389],
      "last_seen": "2026-05-31T23:58:12Z"
    },
    ...
  ]
}
```

---

### Threat Management

#### `GET /api/threat/{threat_id}`
Get details of specific threat event.

**Parameters:**
- `threat_id` (str, path): Threat event ID (e.g., "evt_001")

**Response (200):**
```json
{
  "id": "evt_001",
  "timestamp": "2026-05-31T14:23:45Z",
  "src_ip": "177.5.130.126",
  "dst_ip": "203.0.113.42",
  "dst_port": 22,
  "protocol": "TCP",
  "probability": 0.99,
  "is_threat": true,
  "country": "BR",
  "city": "Palhoça",
  "latitude": -27.6431,
  "longitude": -48.6596,
  "detection_method": "STGNN",
  "stgnn_confidence": 0.99,
  "heuristic_score": 0.95,
  "whitelisted": false,
  "action": "BAN",
  "blocked_until": "2026-06-01T14:23:45Z",
  "raw_features": {
    "packet_count": 142,
    "pps": 23.5,
    "entropy": 7.2,
    "is_ssh": true,
    "inter_arrival_avg": 0.043
  }
}
```

---

#### `POST /api/threat/whitelist`
Add IP to whitelist (prevent blocking).

**Request Body:**
```json
{
  "src_ip": "192.168.1.100",
  "reason": "Internal management IP",
  "expires_in_hours": null
}
```

**Response (201):**
```json
{
  "status": "added",
  "src_ip": "192.168.1.100",
  "whitelisted_at": "2026-05-31T14:30:00Z",
  "expires_at": null,
  "reason": "Internal management IP"
}
```

**Errors:**
- `400`: Invalid IP format
- `409`: IP already whitelisted

---

#### `DELETE /api/threat/whitelist/{src_ip}`
Remove IP from whitelist.

**Response (200):**
```json
{
  "status": "removed",
  "src_ip": "192.168.1.100"
}
```

---

#### `GET /api/threat/whitelist`
List all whitelisted IPs.

**Response (200):**
```json
{
  "total": 5,
  "whitelist": [
    {
      "src_ip": "192.168.1.100",
      "reason": "Internal management IP",
      "whitelisted_at": "2026-05-20T10:00:00Z",
      "expires_at": null
    },
    {
      "src_ip": "10.0.0.5",
      "reason": "Monitoring service",
      "whitelisted_at": "2026-05-15T08:00:00Z",
      "expires_at": "2026-06-15T08:00:00Z"
    }
  ]
}
```

---

#### `POST /api/threat/unblock/{src_ip}`
Immediately unblock an IP from the kernel block_map.

**Response (200):**
```json
{
  "status": "unblocked",
  "src_ip": "177.5.130.126",
  "was_blocked_for": "2h 15m 30s",
  "unblocked_at": "2026-05-31T16:45:00Z"
}
```

---

### Configuration

#### `GET /api/config`
Get current system configuration.

**Response (200):**
```json
{
  "model": {
    "confidence_threshold": 0.70,
    "ensemble_enabled": true,
    "heuristic_weight": 0.5
  },
  "ebpf": {
    "block_timeout_seconds": 3600,
    "max_blocked_ips": 10000,
    "sampling_rate": 1.0
  },
  "api": {
    "rate_limit_requests": 1000,
    "rate_limit_window_seconds": 60,
    "cors_origins": ["*"]
  }
}
```

---

#### `PUT /api/config`
Update system configuration.

**Request Body:**
```json
{
  "model": {
    "confidence_threshold": 0.75
  },
  "ebpf": {
    "block_timeout_seconds": 7200
  }
}
```

**Response (200):**
```json
{
  "status": "updated",
  "changes": {
    "model.confidence_threshold": "0.70 → 0.75",
    "ebpf.block_timeout_seconds": "3600 → 7200"
  }
}
```

---

## 2. WEBSOCKET ENDPOINT

### `WS /ws/threats`
Real-time threat feed via WebSocket.

**Connection:**
```javascript
const ws = new WebSocket('ws://localhost:8000/ws/threats');
```

**Messages Received (Server → Client):**

#### New Threat Detected
```json
{
  "type": "threat_detected",
  "event": {
    "id": "evt_2939",
    "timestamp": "2026-05-31T23:59:45Z",
    "src_ip": "203.155.210.98",
    "dst_port": 22,
    "probability": 0.87,
    "country": "RU",
    "action": "BAN"
  }
}
```

#### IP Blocked
```json
{
  "type": "ip_blocked",
  "src_ip": "177.5.130.126",
  "blocked_until": "2026-06-01T14:23:45Z",
  "reason": "High confidence threat detection"
}
```

#### Connection Status
```json
{
  "type": "status",
  "uptime_seconds": 86400,
  "threats_detected_today": 2939,
  "active_blocks": 23,
  "model_latency_ms": 145
}
```

---

**Messages Sent (Client → Server):**

#### Subscribe to Specific Country
```json
{
  "action": "filter_country",
  "value": "BR"
}
```

#### Subscribe to High Confidence Only
```json
{
  "action": "filter_confidence",
  "min_value": 0.8
}
```

#### Get Live Statistics
```json
{
  "action": "request_stats"
}
```

---

## 3. ERROR HANDLING

All errors follow standard HTTP status codes:

```json
{
  "error": "conflict",
  "message": "IP already whitelisted",
  "code": "IP_ALREADY_WHITELISTED",
  "timestamp": "2026-05-31T14:30:00Z"
}
```

**Common Status Codes:**
- `200`: Success
- `201`: Created
- `400`: Bad request (validation error)
- `401`: Unauthorized
- `404`: Resource not found
- `409`: Conflict (e.g., IP already whitelisted)
- `429`: Rate limited
- `500`: Server error
- `503`: Service unavailable

---

## 4. AUTHENTICATION (Future)

**Current:** No authentication (localhost only)

**Future Implementation:**
```
Authorization: Bearer <JWT_TOKEN>
```

---

## 5. RATE LIMITING

- **Limit:** 1000 requests per minute
- **Headers:**
  - `X-RateLimit-Limit: 1000`
  - `X-RateLimit-Remaining: 999`
  - `X-RateLimit-Reset: 1685000000`

---

## 6. EXAMPLE CURL REQUESTS

### Get Recent History
```bash
curl http://localhost:8000/api/history?limit=10&min_confidence=0.7
```

### Add to Whitelist
```bash
curl -X POST http://localhost:8000/api/threat/whitelist \
  -H "Content-Type: application/json" \
  -d '{
    "src_ip": "192.168.1.100",
    "reason": "Internal IP"
  }'
```

### Get Top Attackers
```bash
curl http://localhost:8000/api/top-attackers?limit=5
```

### Update Config
```bash
curl -X PUT http://localhost:8000/api/config \
  -H "Content-Type: application/json" \
  -d '{
    "model": {
      "confidence_threshold": 0.75
    }
  }'
```

---

## 7. RESPONSE TIMES (SLA)

- `GET /health`: <10ms
- `GET /api/history`: <100ms
- `GET /api/statistics`: <200ms
- `POST /api/threat/whitelist`: <50ms
- `WS /ws/threats`: <10ms (per message)

---

**API Version:** 2.0  
**Last Updated:** 01/06/2026  
**Status:** Production Ready ✅
