use std::env;
use std::path::PathBuf;

use cryptotehnolog_replay::{
    DEFAULT_FIXTURE_PATH, run_probability_basis_replay_report,
    run_probability_basis_replay_report_json,
};

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum OutputFormat {
    Text,
    Json,
}

fn main() {
    let (format, fixture_path) = parse_args(env::args().skip(1).collect());

    match run_report(format, &fixture_path) {
        Ok(report) => print!("{report}"),
        Err(error) => {
            eprintln!("replay failed: {error}");
            std::process::exit(1);
        }
    }
}

fn parse_args(args: Vec<String>) -> (OutputFormat, PathBuf) {
    let mut format = OutputFormat::Text;
    let mut fixture_path = PathBuf::from(DEFAULT_FIXTURE_PATH);
    let mut index = 0;

    while index < args.len() {
        match args[index].as_str() {
            "--format" => {
                let Some(raw_format) = args.get(index + 1) else {
                    eprintln!("replay failed: --format requires `text` or `json`");
                    std::process::exit(1);
                };
                format = match raw_format.as_str() {
                    "text" => OutputFormat::Text,
                    "json" => OutputFormat::Json,
                    other => {
                        eprintln!("replay failed: unsupported format `{other}`");
                        std::process::exit(1);
                    }
                };
                index += 2;
            }
            raw_path => {
                fixture_path = PathBuf::from(raw_path);
                index += 1;
            }
        }
    }

    (format, fixture_path)
}

fn run_report(format: OutputFormat, fixture_path: &PathBuf) -> Result<String, String> {
    match format {
        OutputFormat::Text => {
            Ok(run_probability_basis_replay_report(fixture_path)?.join("\n") + "\n")
        }
        OutputFormat::Json => run_probability_basis_replay_report_json(fixture_path),
    }
}
