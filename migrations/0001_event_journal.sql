create table if not exists event_journal (
    id bigserial primary key,
    event_id text not null unique,
    event_type text not null,
    source text not null,
    exchange_ts timestamptz,
    received_ts timestamptz not null default now(),
    instrument_id text,
    schema_version integer not null,
    config_version text not null,
    payload jsonb not null
);

create index if not exists idx_event_journal_type_received
    on event_journal (event_type, received_ts);

create index if not exists idx_event_journal_instrument_received
    on event_journal (instrument_id, received_ts);

create table if not exists replay_runs (
    id bigserial primary key,
    run_id text not null unique,
    started_at timestamptz not null default now(),
    finished_at timestamptz,
    config_version text not null,
    input_event_count integer not null default 0,
    output_event_count integer not null default 0,
    notes text
);

create table if not exists basis_observations (
    id bigserial primary key,
    event_id text not null unique,
    observed_at timestamptz not null,
    deribit_instrument_id text not null,
    polymarket_market_slug text not null,
    model_probability numeric not null,
    polymarket_mid_probability numeric not null,
    gross_edge_probability numeric not null,
    estimated_cost_probability numeric not null,
    net_edge_probability numeric not null,
    survives_costs boolean not null
);

