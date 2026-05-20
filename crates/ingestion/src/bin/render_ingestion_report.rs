use std::env;
use std::path::PathBuf;
use std::process;

use cryptotehnolog_ingestion::{ingestion_report_from_scenario_steps, load_ingestion_scenario};

fn main() {
    let args: Vec<String> = env::args().collect();
    if args.len() != 2 {
        eprintln!("usage: render_ingestion_report <fixture.psv>");
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
    let report = match ingestion_report_from_scenario_steps(&steps) {
        Ok(report) => report,
        Err(error) => {
            eprintln!("{error}");
            process::exit(1);
        }
    };

    println!("{}", report.to_json());
}
