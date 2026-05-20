#[cfg(feature = "network-integration")]
use std::process;

#[cfg(feature = "network-integration")]
use cryptotehnolog_ingestion::{
    DeribitLiveIngestionClient, PolymarketLiveIngestionClient, ReqwestHttpTransport,
    probe_live_http_endpoint, probe_reports_to_json,
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

    let polymarket_client = PolymarketLiveIngestionClient::new(
        "https://gamma-api.polymarket.com",
        "eth-above-3000-june-1",
        "Yes",
    );

    let reports = vec![
        probe_live_http_endpoint(
            "Deribit instruments",
            DeribitLiveIngestionClient::instruments_url("https://www.deribit.com"),
            &transport,
        ),
        probe_live_http_endpoint(
            "Polymarket Gamma",
            polymarket_client.gamma_market_url(),
            &transport,
        ),
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
