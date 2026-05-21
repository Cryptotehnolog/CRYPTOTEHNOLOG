#[cfg(feature = "network-integration")]
use std::process;

#[cfg(feature = "network-integration")]
use cryptotehnolog_ingestion::{
    DeribitLiveIngestionClient, LiveHttpRetryPolicy, PolymarketLiveIngestionClient,
    ReqwestHttpTransport, fetch_live_http_endpoint, probe_reports_to_json,
};

#[cfg(feature = "network-integration")]
fn main() {
    let transport = match ReqwestHttpTransport::new(5_000) {
        Ok(transport) => transport,
        Err(error) => {
            eprintln!("{}", error.message);
            process::exit(1);
        }
    };

    let retry_policy = LiveHttpRetryPolicy::phase0_manual_probe();
    let reports = vec![
        fetch_live_http_endpoint(
            "Deribit instruments",
            DeribitLiveIngestionClient::instruments_url("https://www.deribit.com"),
            &transport,
            retry_policy,
        )
        .1,
        fetch_live_http_endpoint(
            "Polymarket Gamma markets",
            PolymarketLiveIngestionClient::markets_url("https://gamma-api.polymarket.com"),
            &transport,
            retry_policy,
        )
        .1,
    ];
    println!("{}", probe_reports_to_json(&reports));

    if reports.iter().any(|report| !report.is_ok()) {
        process::exit(1);
    }
}

#[cfg(not(feature = "network-integration"))]
fn main() {
    eprintln!(
        "network_connectivity_check requires: cargo run -p cryptotehnolog-ingestion --features network-integration --bin network_connectivity_check"
    );
    std::process::exit(2);
}
