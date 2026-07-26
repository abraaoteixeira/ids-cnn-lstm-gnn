# 🤝 CONTRIBUTING GUIDE

Thank you for your interest in contributing to SPECTRE_GRID!

---

## How to Contribute

### 1. Report Bugs

Found a bug? Open an issue with:

```markdown
**Description:** What's the issue?
**Steps to reproduce:**
1. Step 1
2. Step 2

**Expected behavior:** What should happen?
**Actual behavior:** What actually happens?
**Environment:** OS, Python version, etc.
```

### 2. Suggest Features

Have an idea? Create an issue with `[FEATURE]` label:

```markdown
**Feature:** What's your idea?
**Motivation:** Why is it needed?
**Implementation idea:** How would you do it?
```

### 3. Submit Code

```bash
# 1. Fork the repository
git clone https://github.com/YOUR_USERNAME/ids-cnn-lstm-gnn.git

# 2. Create feature branch
git checkout -b feature/my-feature

# 3. Make changes
# Edit files...

# 4. Run tests
pytest

# 5. Format code
black .
flake8 .

# 6. Commit
git commit -m "Add feature: description"

# 7. Push
git push origin feature/my-feature

# 8. Create pull request on GitHub
```

---

## Code Standards

### Python Style

- **PEP 8:** Use `black` formatter
- **Docstrings:** Google-style for all functions
- **Type hints:** Required for new code

```python
def process_packet(packet: bytes, features: int = 20) -> Dict[str, float]:
    """
    Extract features from network packet.
    
    Args:
        packet: Raw packet bytes
        features: Number of features to extract
    
    Returns:
        Dictionary mapping feature names to values
    
    Raises:
        ValueError: If packet too small
    """
    if len(packet) < 20:
        raise ValueError("Packet too small")
    
    return {}
```

### C/eBPF Style

- **Comments:** Explain non-obvious logic
- **Safety:** Always check bounds
- **Naming:** descriptive (use `_` prefix for static)

```c
// ✅ Good
static inline int extract_src_port(struct ethhdr *eth, void *end) {
    if ((void *)(eth + 1) > end) return -1;
    // ... extract port
    return port;
}

// ❌ Bad
int esp(struct ethhdr *e, void *en) {  // Unclear naming
    return *(int *)e;  // No bounds check
}
```

### Git Commit Messages

```
Format: <type>: <subject>

<body>

<footer>

Types:
  feat:     New feature
  fix:      Bug fix
  docs:     Documentation
  test:     Tests
  refactor: Code refactoring
  perf:     Performance
  chore:    Dependencies, setup

Examples:
  feat: add heuristic SSH detection
  fix: prevent whitelist bypass in ensemble logic
  docs: update deployment guide for HA setup
  test: add E2E test for concept drift validation
```

---

## Testing Requirements

All contributions must include tests:

```python
# tests/test_receiver.py

import pytest
from receiver_gnn import should_block

def test_whitelist_protection():
    """Whitelisted IPs should never be blocked"""
    result, reason = should_block("192.168.1.100", confidence=0.99)
    assert result is False
    assert reason == "WHITELISTED"

def test_high_confidence_threat():
    """Threats above threshold should be blocked"""
    result, reason = should_block("203.0.113.1", confidence=0.95)
    assert result is True
    assert reason == "THREAT_DETECTED"

def test_low_confidence_benign():
    """Low confidence should not trigger block"""
    result, reason = should_block("203.0.113.2", confidence=0.30)
    assert result is False
```

**Run tests:**
```bash
pytest tests/ -v
```

---

## Documentation

### Update Required For:

- **New features** → Update README.md + docs/
- **API changes** → Update docs/API.md
- **Model changes** → Update docs/TRAINING_GUIDE.md
- **Deployment changes** → Update docs/DEPLOYMENT.md

### Documentation Format

```markdown
## Feature Name

**Purpose:** Why this feature exists

**Usage:**
\`\`\`python
# Example code
\`\`\`

**Configuration:**
- `param1`: Description
- `param2`: Description

**Notes:**
- Important implementation detail
- Limitation to be aware of
```

---

## Areas to Contribute

### High Priority 🔴

- [ ] NF-UQ-NIDS-v2 retreinament (TRAINING_GUIDE.md)
- [ ] E2E automated tests (pytest framework)
- [ ] WSL auto-startup (.bat script)
- [ ] Production hardening (log rotation, alerts)

### Medium Priority 🟡

- [ ] XAI visualization (Shapley values)
- [ ] Suricata/Snort comparison
- [ ] High availability setup
- [ ] Docker containerization

### Low Priority 🟢

- [ ] Video tutorials
- [ ] Academic paper
- [ ] Community forum
- [ ] UI improvements (dashboard)

---

## Getting Help

- 📖 **Documentation:** Check docs/INDEX.md
- 🐛 **Bugs:** Search existing issues
- 💬 **Questions:** Open a discussion
- 📧 **Email:** [your-email@example.com]

---

## License

All contributions must be under **MIT License**.

```
MIT License

Copyright (c) 2026 Abraã Oteixeira

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files...
```

---

**Contributing Guidelines Version:** 1.0  
**Last Updated:** 01/06/2026  
**Thank you for contributing! 🙏**
