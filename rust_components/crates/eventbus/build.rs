// Build script for cryptotechnolog-eventbus
// This ensures proper linking of zmq library

fn main() {
    // Link zmq library
    // On Linux/Mac, pkg-config will find it
    // On Windows, it's handled by the zmq crate
    #[cfg(not(windows))]
    {
        // Try to use pkg-config to find zmq
        if let Ok(lib) = pkg_config::probe_library("zmq") {
            for path in lib.include_paths {
                println!("cargo:include={}", path.display());
            }
        }
        // If pkg-config fails, the zmq crate will handle it
        // via its own build scripts
    }
}
