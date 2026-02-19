# CRYPTOTEHNOLOG Rust Components

High-performance Rust components for the CRYPTOTEHNOLOG trading platform.

## Workspace Structure

This is a Cargo workspace containing multiple crates for different components:

```
rust_components/
├── Cargo.toml              # Workspace configuration
├── crates/
│   ├── common/             # Shared types, errors, utilities
│   ├── eventbus/           # Event bus for inter-component communication
│   ├── risk-ledger/        # Risk calculations and position tracking (Phase 5-6)
│   ├── audit-chain/        # Immutable audit chain (Phase 8-9)
│   ├── execution-core/     # Order execution engine (Phase 7)
│   └── ffi/                # Python bindings via PyO3 (Phase 6-7)
```

## Crates

### `cryptotechnolog-common`

Shared types, errors, and utilities used across all crates.

**Features:**
- Comprehensive error types
- Utility functions (hash, validation, clamping)
- Common data structures

**Status:** ✅ Implemented (Phase 0)

### `cryptotechnolog-eventbus`

High-performance event bus for inter-component communication.

**Features:**
- Event types and serialization
- Redis pub/sub support
- ZeroMQ support (alternative)
- Event correlation and tracking

**Status:** ✅ Implemented (Phase 0) - Basic event types

### `cryptotechnolog-risk-ledger`

Risk calculations and position tracking.

**Features:**
- Position tracking
- Risk calculations (R-multiple, portfolio risk)
- Position size calculations
- Real-time risk monitoring

**Status:** 🚧 Placeholder (Phase 5-6)

### `cryptotechnolog-audit-chain`

Immutable audit chain for regulatory compliance.

**Features:**
- Cryptographic audit chain
- Immutable audit records
- Chain integrity verification
- Regulatory compliance logging

**Status:** 🚧 Placeholder (Phase 8-9)

### `cryptotechnolog-execution-core`

High-performance order execution engine.

**Features:**
- Order routing
- Order matching
- Slippage management
- Exchange API integration

**Status:** 🚧 Placeholder (Phase 7)

### `cryptotechnolog-ffi`

Python bindings using PyO3 for high-performance interop.

**Features:**
- PyO3 bindings
- Zero-copy data transfer
- Async function support
- Seamless Python integration

**Status:** 🚧 Placeholder (Phase 6-7)

## Building

### Build all crates:

```bash
cd rust_components
cargo build --release
```

### Build specific crate:

```bash
cargo build -p cryptotechnolog-common --release
```

### Run tests:

```bash
cargo test
```

## Python Integration (Phase 6-7)

**Requirements:**
- Python 3.11, 3.12, 3.13, or 3.14
- Rust 1.83+ (for PyO3 0.28)
- maturin (Python package)

### Python Support

| Python Version | PyO3 Support | Status |
|----------------|--------------|--------|
| 3.11 | ✅ PyO3 0.28+ | Supported |
| 3.12 | ✅ PyO3 0.28+ | Supported |
| 3.13 | ✅ PyO3 0.28+ | Supported |
| 3.14 | ✅ PyO3 0.28+ | Supported |

### Building FFI

```bash
cd rust_components
pip install maturin
maturin develop --release
```

### Using in Python

```python
from cryptotechnolog_rust import calculate_position_size

position_size = calculate_position_size(100000.0, 0.01, 50000.0, 49500.0)
print(position_size)
```

### Note

pyo3-asyncio is not yet available for PyO3 0.28. Currently using sync functions only. Async support will be added when pyo3-asyncio is updated.

## Performance Targets

| Component | Target | Status |
|-----------|--------|--------|
| Risk calculations | 100,000+ ops/sec | 🚧 Phase 5-6 |
| Order execution | 10,000+ orders/sec | 🚧 Phase 7 |
| Event bus | 1,000,000+ events/sec | 🚧 Phase 3 |
| Audit chain | 10,000+ records/sec | 🚧 Phase 8-9 |

## Development

### Add new dependency to workspace:

Edit `Cargo.toml` in workspace root:

```toml
[workspace.dependencies]
new-crate = "1.0"
```

Then use in individual crate:

```toml
[dependencies]
new-crate = { workspace = true }
```

### Add new crate:

1. Create new directory: `crates/new-crate/`
2. Create `Cargo.toml` with package definition
3. Add to workspace members in root `Cargo.toml`
4. Create `src/lib.rs`

## Documentation

- [Python ↔ Rust Interop Guide](../docs/PYTHON_RUST_INTEROP_GUIDE.md)
- [Rust Book](https://doc.rust-lang.org/book/)
- [PyO3 Guide](https://pyo3.rs/)

## License

Proprietary - All Rights Reserved

## Authors

CRYPTOTEHNOLOG Team
