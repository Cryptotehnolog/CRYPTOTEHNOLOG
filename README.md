# CRYPTOTEHNOLOG v1.2.0

## Institutional-Grade Crypto Trading Platform

Multi-exchange algorithmic trading platform designed for small prop firm / crypto fund operations with $100M+ capital capacity.

---

## 🎯 Project Overview

CRYPTOTEHNOLOG is an autonomous, self-healing trading platform that provides:

- **Multi-exchange execution** across major crypto exchanges (Bybit, OKX, Binance)
- **Institutional-grade risk management** with double-entry risk ledger
- **Autonomous operation** for weeks without human intervention
- **Self-healing architecture** with multi-level degradation modes
- **Cryptographic audit trail** for full compliance
- **Sub-millisecond execution** for critical trading paths

---

## 🏗️ Architecture

### Multi-Language Architecture

```
CRYPTOTEHNOLOG Platform
│
├── Control Plane (Python)
│   ├── State Machine
│   ├── Config Manager
│   ├── Risk Engine (orchestration)
│   ├── Portfolio Governor
│   └── Kill Switch
│
├── Data Plane
│   ├── Event Bus (Rust) ← high-performance messaging
│   ├── Risk Ledger (Rust) ← atomic operations
│   ├── Audit Chain (Rust) ← cryptographic hashing
│   ├── Market Data Layer (Python)
│   ├── Intelligence Layer (Python)
│   └── Strategy Layer (Python)
│
├── Execution Layer (Rust + Python)
│   ├── Order Execution Core (Rust) ← low-latency
│   ├── Smart Order Router (Python)
│   └── Exchange Adapters (Python)
│
├── Observability (Python + Web)
│   ├── Metrics Collector (Python)
│   ├── Web Dashboard (React + TypeScript)
│   └── Grafana/Prometheus Integration
│
└── Storage
    ├── PostgreSQL + TimescaleDB (states, audit, time-series)
    ├── Redis (cache, state machine, pub/sub)
    └── HashiCorp Vault (secrets management, optional)
```

### Technology Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **Languages** | Python 3.11+, Rust 1.75+, TypeScript | Multi-language architecture |
| **Databases** | PostgreSQL 15, TimescaleDB, Redis 7 | Persistent storage & caching |
| **Secrets** | HashiCorp Vault (optional), .env files | Secure secrets management |
| **Observability** | Grafana, Prometheus | Metrics & monitoring |
| **Containerization** | Docker, Docker Compose | Development environment |
| **Orchestration** | Kubernetes | Production deployment (Phase 19) |
| **CI/CD** | GitHub Actions | Automated testing & deployment |

---

## 📊 Development Status

| Phase | Name | Status | Version |
|-------|------|--------|---------|
| 0 | Environment Setup | ✅ Done | v1.0.0 |
| 1 | Infrastructure Core | ✅ Done | v1.1.0 |
| 2 | Control Plane | ✅ Done | v1.2.0 |
| 3 | Event Bus | ⏳ Planned | v1.3.0 |
| 4 | Config Manager | ⏳ Planned | v1.4.0 |
| 5 | Risk Engine | ⏳ Planned | v1.5.0 |
| 6-11 | Trading Layers | ⏳ Planned | v1.6.0-v2.0.0 |
| 12-18 | Protection & Testing | ⏳ Planned | v2.1.0-v2.3.0 |
| 19 | Deployment | ⏳ Planned | v3.0.0 |

---

## 🚀 Quick Start

### Prerequisites

- **Windows 10/11** or **Linux** (WSL 2 on Windows)
- **Python 3.11+**
- **Rust 1.75+**
- **Docker Desktop** with WSL 2
- **Visual Studio Code**
- **Git**

### Installation

```bash
# Clone repository
git clone <repository-url>
cd CRYPTOTEHNOLOG

# Create Python virtual environment
python -m venv venv

# Activate virtual environment
# Windows:
.\venv\Scripts\Activate.ps1
# Linux/Mac:
source venv/bin/activate

# Install Python dependencies
pip install -r requirements.txt

# Start infrastructure services
docker-compose up -d

# Run tests
pytest tests/

# Start development server (when ready)
python -m src.main
```

### Development

```bash
# Run linter
ruff check src/
black src/

# Run type checker
mypy src/

# Run tests with coverage
pytest --cov=src --cov-report=html

# Build Rust components
cargo build
cargo test
```

---

## 📁 Project Structure

```
CRYPTOTEHNOLOG/
├── src/                      # Python source code
│   ├── config/              # Configuration management
│   ├── core/                # Core utilities and helpers
│   ├── risk/                # Risk engine
│   ├── analysis/            # Market analysis
│   ├── execution/           # Order execution
│   ├── models/              # Data models
│   ├── intelligence/        # Intelligence layer
│   ├── strategy/            # Trading strategies
│   └── observability/       # Monitoring & metrics
├── crates/                  # Rust workspace crates
│   ├── eventbus/            # High-performance event bus
│   ├── risk-ledger/         # Double-entry risk ledger
│   ├── audit-chain/         # Cryptographic audit chain
│   ├── execution-core/      # Low-latency execution
│   ├── ffi/                 # Python FFI bindings
│   └── common/              # Shared types and utilities
├── tests/                   # Test suite
│   ├── unit/               # Unit tests
│   ├── integration/        # Integration tests
│   ├── e2e/                # End-to-end tests
│   └── fixtures/           # Test data
├── docs/                    # Documentation
│   ├── architecture/       # Architecture docs
│   ├── runbooks/           # Operational procedures
│   └── api/                # API documentation
├── config/                  # Configuration files
│   ├── dev/                # Development config
│   └── prod/               # Production config
├── scripts/                 # Automation scripts
│   ├── deployment/         # Deployment scripts
│   └── testing/            # Testing scripts
├── .github/                 # GitHub configuration
│   ├── workflows/          # CI/CD workflows
│   └── pull_request_template/
├── docker-compose.yml       # Docker services
├── Dockerfile              # Python service container
├── Makefile                # Common commands
├── pyproject.toml          # Python project config
├── requirements.txt        # Python dependencies
└── README.md               # This file
```

---

## 🧪 Testing

### Test Coverage Requirements

- **Critical Path** (Risk Engine, Execution): >95%
- **Business Logic** (Strategies, Intelligence): >90%
- **Infrastructure** (Event Bus, Config): >85%
- **UI/Dashboard**: >70%

### Running Tests

```bash
# All tests
pytest

# Unit tests only
pytest tests/unit/

# Integration tests only
pytest tests/integration/

# With coverage
pytest --cov=src --cov-report=html

# Specific test file
pytest tests/unit/test_settings.py
```

---

## 🔒 Security

- **Secrets Management**: HashiCorp Vault (optional) or .env files for sensitive data
- **Configuration Integrity**: Cryptographic signatures for all configs
- **Audit Trail**: Immutable cryptographic audit chain
- **Network Security**: TLS for all external connections
- **API Permissions**: Read/Trade only, no withdrawal permissions

---

## 📈 CI/CD

### GitHub Actions Workflow

- **On Push**: Run all tests, linting, type checking
- **On PR**: Additional security scanning, code review checks
- **On Merge to Main**: Tag release, prepare deployment

### Branch Protection

- **main**: Protected, requires PR + approval + passing CI
- **develop**: Integration branch, requires passing CI
- **feature/***: Feature branches

---

## 🤝 Contributing

1. Create feature branch from `develop`
2. Make changes with tests
3. Ensure all tests pass and coverage maintained
4. Submit PR with description
5. Wait for approval and CI checks
6. Merge to `develop`

---

## 📄 License

Proprietary - All Rights Reserved

---

## 📞 Support

For issues and questions, see [docs/runbooks/](docs/runbooks/) or create an issue in the repository.

---

**Version**: 1.2.0
**Last Updated**: 2026-02-22
