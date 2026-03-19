# CRYPTOTEHNOLOG v1.5.1

## Institutional-Grade Crypto Trading Platform

Multi-exchange algorithmic trading platform designed for small prop firm / crypto fund operations with $100M+ capital capacity.

---

## 🎯 Project Overview

CRYPTOTEHNOLOG is an autonomous, self-healing trading platform that provides:

- **Multi-exchange execution** across major crypto exchanges (Bybit, OKX, Binance)
- **Institutional-grade risk management** with Phase 5 Risk Engine foundation
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
│   ├── Risk Engine (Phase 5 orchestration)
│   ├── Portfolio Governor
│   └── Kill Switch
│
├── Data Plane
│   ├── Event Bus (Rust) ← high-performance messaging
│   ├── Rust Risk Ledger (legacy/high-performance path)
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
    └── Infisical (secrets management)
```

### Technology Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **Languages** | Python 3.11+, Rust 1.75+, TypeScript | Multi-language architecture |
| **Databases** | PostgreSQL 15, TimescaleDB, Redis 7 | Persistent storage & caching |
| **Secrets** | Infisical, .env files | Secure secrets management |
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
| 3 | Event Bus (Enhanced) | ✅ Done | v1.3.0 |
| 4 | Config Manager | ✅ Done | v1.4.0 |
| 5 | Risk Engine | ✅ Done | v1.5.0 |
| 5.1 | Production Alignment | ✅ Done | v1.5.1 |
| 6 | Market Data Layer + Universe Engine | ⏳ Planned | v1.6.0 |
| 7-11 | Intelligence / Strategy / Execution Expansion | ⏳ Planned | v1.7.0-v2.0.0 |
| 12-18 | Protection & Testing | ⏳ Planned | v2.1.0-v2.3.0 |
| 19 | Deployment | ⏳ Planned | v3.0.0 |

---

## Phase 5 Risk Engine + v1.5.1 Production Alignment

Phase 5 introduces a new Python-based Risk Engine contour built as a modern,
typed domain layer and integrated into the event-driven runtime without
reusing the legacy listener-based risk path as its implementation base.

Implemented in v1.5.0:

- Domain models for orders, positions, risk records, trailing updates and funding snapshots
- `PositionSizer` with Decimal-only R-unit sizing and hard invariants
- Position-oriented `RiskLedger` as the source of truth for open-position risk
- `TrailingPolicy` with tiered trailing, emergency mode and mandatory ledger sync
- `PortfolioState`, `DrawdownMonitor`, `CorrelationEvaluator` and `FundingManager`
- `RiskEngine` pre-trade orchestration and event-driven handlers for:
  - `ORDER_FILLED`
  - `POSITION_CLOSED`
  - `BAR_COMPLETED`
  - `STATE_TRANSITION`
- Optional persistence foundation for:
  - `risk_checks`
  - `position_risk_ledger`
  - `position_risk_ledger_audit`
  - `trailing_stops`
  - `trailing_stop_movements`
- Runtime composition via `create_risk_runtime(...)` with explicit listener registration

Production alignment completed in `v1.5.1`:

- Official production bootstrap via `src/cryptotechnolog/bootstrap.py`
- One authoritative runtime identity for version, bootstrap mode, active risk path and config truth
- Production runtime enforces a single active risk path: `phase5_risk_engine`
- Startup, readiness, health, shutdown and fail-fast semantics are centralized and operator-visible
- Risk event vocabulary is aligned across runtime publication, audit and metrics listeners
- Integration/bootstrap tests cover the real production composition root

Controlled coexistence after `v1.5.1`:

- The new Phase 5 risk contour is the only production risk path
- Legacy `core.listeners.risk` remains in the repository only as non-production compatibility / test-only path
- Full physical removal of legacy code is not part of `v1.5.1`; production bootstrap excludes it explicitly

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

# Start development runtime (when ready)
python -m cryptotechnolog.main
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

- **Secrets Management**: Infisical or .env files for sensitive data
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

**Version**: 1.5.1
**Last Updated**: 2026-03-19
