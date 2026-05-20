#[cfg(feature = "network-integration")]
use std::process;

#[cfg(feature = "network-integration")]
use cryptotehnolog_ingestion::{
    DeribitLiveIngestionClient, LiveHttpTransport, PolymarketLiveIngestionClient,
    ReqwestHttpTransport,
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

    let deribit_client =
        DeribitLiveIngestionClient::new("https://www.deribit.com", "ETH-20260601-3000-C");
    let polymarket_client = PolymarketLiveIngestionClient::new(
        "https://gamma-api.polymarket.com",
        "eth-above-3000-june-1",
        "Yes",
    );

    check_url("Deribit", &transport, &deribit_client.ticker_url());
    check_url(
        "Polymarket Gamma",
        &transport,
        &polymarket_client.gamma_market_url(),
    );
}

#[cfg(feature = "network-integration")]
fn check_url(label: &str, transport: &ReqwestHttpTransport, url: &str) {
    match transport.get(url) {
        Ok(payload) => {
            println!("{label}: ok ({} bytes)", payload.len());
        }
        Err(error) => {
            eprintln!("{label}: {}", error.message);
            process::exit(1);
        }
    }
}

#[cfg(not(feature = "network-integration"))]
fn main() {
    eprintln!(
        "network_connectivity_check requires: cargo run -p cryptotehnolog-ingestion --features network-integration --bin network_connectivity_check"
    );
    std::process::exit(2);
}
