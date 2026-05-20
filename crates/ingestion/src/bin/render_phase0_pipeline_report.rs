use std::env;
use std::path::PathBuf;
use std::process;

use cryptotehnolog_ingestion::{
    load_ingestion_scenario, phase0_pipeline_report_from_scenario_steps,
};

fn main() {
    let args: Vec<String> = env::args().collect();
    if args.len() != 2 {
        eprintln!("usage: render_phase0_pipeline_report <fixture.psv>");
        process::exit(2);
    }

    let path = PathBuf::from(&args[1]);
    let steps = match load_ingestion_scenario(&path) {
        Ok(steps) => steps,
        Err(error) => {
            eprintln!("{error}");
            process::exit(1);
        }
    };
    let report = match phase0_pipeline_report_from_scenario_steps(&steps) {
        Ok(report) => report,
        Err(error) => {
            eprintln!("{error}");
            process::exit(1);
        }
    };
    let json = match report.to_json() {
        Ok(json) => json,
        Err(error) => {
            eprintln!("failed to serialize phase0 pipeline report: {error}");
            process::exit(1);
        }
    };

    println!("{json}");
}
