use std::env;
use std::path::PathBuf;

use cryptotehnolog_replay::{DEFAULT_FIXTURE_PATH, run_probability_basis_replay_report};

fn main() {
    let fixture_path = env::args()
        .nth(1)
        .map(PathBuf::from)
        .unwrap_or_else(|| PathBuf::from(DEFAULT_FIXTURE_PATH));

    match run_probability_basis_replay_report(&fixture_path) {
        Ok(report) => {
            for line in report {
                println!("{line}");
            }
        }
        Err(error) => {
            eprintln!("replay failed: {error}");
            std::process::exit(1);
        }
    }
}
