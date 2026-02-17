# CRYPTOTEHNOLOG Rust Core

High-performance Rust components for the CRYPTOTEHNOLOG trading platform.

## Overview

This library provides critical performance-sensitive components:

- **Event Bus**: High-performance event messaging (Redis/ZeroMQ)
- **Risk Ledger**: Double-entry accounting system
- **Audit Chain**: Cryptographic audit trail
- **Execution Core**: Low-latency order execution

## Building

```bash
# Build debug version
cargo build

# Build release version
cargo build --release
```

## Testing

```bash
# Run all tests
cargo test

# Run tests with output
cargo test -- --nocapture

# Run specific test
cargo test test_event_creation
```

## Code Quality

```bash
# Format code
cargo fmt

# Check formatting
cargo fmt -- --check

# Run linter
cargo clippy

# Run clippy with strict checks
cargo clippy -- -D warnings
```

## Examples

See the `examples/` directory for usage examples:

```bash
# Run event bus example
cargo run --bin event_bus_example

# Run audit chain example
cargo run --bin audit_chain_example
```

## Development

### Project Structure

```
rust_components/
├── src/
│   ├── lib.rs              # Main library entry point
│   ├── error.rs            # Error types
│   ├── event.rs            # Event types
│   ├── utils.rs            # Utilities
│   ├── event_bus/          # Event bus implementation
│   ├── risk_ledger/        # Risk ledger implementation
│   ├── audit_chain/        # Audit chain implementation
│   └── execution_core/     # Execution core implementation
├── examples/               # Example programs
├── tests/                  # Integration tests
└── Cargo.toml             # Project configuration
```

### Adding New Components

1. Create a new module in `src/`
2. Add public functions/types to `src/lib.rs`
3. Write unit tests in the module
4. Add integration tests in `tests/`
5. Update documentation

## Performance Considerations

- Use `--release` builds for production
- Enable LTO (Link Time Optimization) in release profile
- Use `#[inline]` for small, frequently called functions
- Prefer stack allocation over heap allocation where possible
- Use `#[cold]` for error paths
- Use `#[must_use]` for functions with important return values

## License

Proprietary - All Rights Reserved
