# Rust Version Support

## Current Status

- **Minimum Rust Version:** 1.83
- **Current CI Version:** stable (auto-updated)
- **Known Dependency Issue:** redis v0.24.0 will be rejected by future Rust versions

## Migration to Rust 1.85+

When CI/CD is updated to Rust 1.85 or newer, follow these steps:

### 1. Update Redis Dependency

The current version of `redis` (0.24.0) will be rejected by future Rust versions. Update to a compatible version:

**File:** `rust_components/Cargo.toml`

```toml
# Change from:
redis = { version = "0.24", features = ["tokio-comp", "connection-manager"] }

# To:
redis = { version = "0.27", features = ["tokio-comp", "connection-manager"] }
```

### 2. Update Dependencies

Run the following commands to update the dependency tree:

```bash
cd rust_components
cargo update -p redis
cargo clean
cargo build
```

### 3. Run Tests

Ensure all tests pass after the update:

```bash
cargo test
cargo clippy -- -D warnings
```

### 4. Commit Changes

Commit the updated `Cargo.toml` and `Cargo.lock`:

```bash
git add rust_components/Cargo.toml rust_components/Cargo.lock
git commit -m "chore: Update redis to 0.27 for Rust 1.85+ compatibility"
git push
```

## Why This Is Needed

- `redis` v0.24.0 depends on `backon` v1.5.x (compatible with Rust 1.83)
- `redis` v0.27.0+ depends on `backon` v1.6.0+ (requires Rust 1.85+ with edition2024)
- The `backon` crate v1.6.0 uses Rust edition2024 features that are only stable in Rust 1.85+

## Monitoring

To check when Rust 1.85 becomes available in CI:

1. Monitor the CI logs for the Rust version: `rustc --version`
2. Check Rust release notes: https://blog.rust-lang.org/
3. Subscribe to Rust announcements for major version updates

## Testing Locally

To test locally with a specific Rust version:

```bash
# Install Rust 1.85
rustup install 1.85
rustup default 1.85

# Test build
cd rust_components
cargo build

# Revert to 1.83 if needed
rustup default 1.83
```

## Additional Notes

- The project uses `rust-version = "1.83"` in workspace metadata
- CI uses `dtolnay/rust-toolchain@stable` which automatically updates to new stable versions
- All crates inherit `rust-version.workspace = true` for consistency
- No manual intervention is required for minor Rust updates (1.83.x → 1.83.y)
- Only major version updates (1.83 → 1.85+) may require dependency updates
