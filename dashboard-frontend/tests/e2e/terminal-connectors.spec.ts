import { expect, test } from "@playwright/test";

const backendBaseUrl = "http://127.0.0.1:8000";

const backendRoutes = [
  "/dashboard/settings/live-feed-policy",
  "/dashboard/settings/bybit-connector-diagnostics",
  "/dashboard/settings/bybit-spot-connector-diagnostics",
  "/dashboard/settings/bybit-spot-runtime-status",
  "/dashboard/settings/bybit-spot-product-snapshot",
  "/dashboard/settings/bybit-spot-v2-diagnostics",
] as const;

async function mockSpotProductSnapshot(
  page: import("@playwright/test").Page,
  payload: Record<string, unknown>,
) {
  await page.route(
    `${backendBaseUrl}/dashboard/settings/bybit-spot-product-snapshot`,
    async (interceptedRoute) => {
      await interceptedRoute.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(payload),
      });
    },
  );
}

test.describe("Terminal connectors semantics", () => {
  test.beforeEach(async ({ request }) => {
    for (const route of backendRoutes) {
      const response = await request.get(`${backendBaseUrl}${route}`);
      expect(
        response.ok(),
        `Expected backend route ${route} to be available for terminal connectors acceptance`,
      ).toBeTruthy();
    }
  });

  test("surfaces split product truth and admission semantics on each connector panel", async ({
    page,
  }) => {
    await page.goto("/terminal/connectors");

    await expect(page.getByRole("heading", { name: "Коннекторы" })).toBeVisible();

    for (const panelId of ["futures"] as const) {
      const panel = page.getByTestId(`connector-panel-${panelId}`);
      const productTruthCard = page.getByTestId(`connector-product-truth-${panelId}`);
      const admissionBasisCard = page.getByTestId(`connector-admission-basis-${panelId}`);
      const semanticNote = page.getByTestId(`connector-semantic-note-${panelId}`);

      await expect(panel).toBeVisible();
      await expect(productTruthCard).toBeVisible();
      await expect(admissionBasisCard).toBeVisible();
      await expect(semanticNote).toBeVisible();

      await expect(panel.getByRole("columnheader", { name: /Сделок за 24ч/i })).toBeVisible();
      await expect(productTruthCard).toHaveAttribute("data-truth-surface", "product");
      await expect(productTruthCard).toHaveAttribute("data-truth-basis", "ledger");
      await expect(admissionBasisCard).toHaveAttribute("data-truth-surface", "admission");
      await expect(admissionBasisCard).toHaveAttribute(
        "data-truth-basis",
        /(derived-operational|inactive)/,
      );
      await expect(semanticNote).toHaveAttribute("data-truth-split-visible", "true");
      await expect(semanticNote).toContainText(/Сделок за 24ч/i);
      await expect(semanticNote).toContainText(/minTradeCount/i);
    }
  });

  test("falls back to flat operator state fields when compact operator_state_surface is absent", async ({
    page,
  }) => {
    for (const route of [
      `${backendBaseUrl}/dashboard/settings/bybit-connector-diagnostics`,
      `${backendBaseUrl}/dashboard/settings/bybit-spot-connector-diagnostics`,
    ]) {
      await page.route(route, async (interceptedRoute) => {
        const response = await interceptedRoute.fetch();
        const payload = (await response.json()) as Record<string, unknown>;
        delete payload.operator_state_surface;
        payload.operational_recovery_state = "ready_for_operation";
        payload.operational_recovery_reason = "Operational recovery truth is ready.";
        payload.canonical_ledger_sync_state = "ledger_sync_completed";
        payload.canonical_ledger_sync_reason = "Canonical ledger synchronization is up to date.";
        await interceptedRoute.fulfill({ response, json: payload });
      });
    }

    await page.goto("/terminal/connectors");

    for (const panelId of ["futures"] as const) {
      const operatorStateCard = page.getByTestId(`connector-operator-state-${panelId}`);

      await expect(operatorStateCard).toBeVisible();
      await expect(operatorStateCard).toContainText("Готов к работе");
      await expect(operatorStateCard).toContainText("Ledger sync завершён");
      await expect(operatorStateCard).toContainText("Operational recovery truth is ready.");
      await expect(operatorStateCard).toContainText(
        "Canonical ledger synchronization is up to date.",
      );
    }
  });

  test("shows current spot primary panel from product snapshot surface", async ({ page }) => {
    await mockSpotProductSnapshot(page, {
      generation: "v2",
      desired_running: true,
      transport_status: "connected",
      subscription_alive: true,
      transport_rtt_ms: 415,
      last_message_at: "2026-04-15T00:00:01+00:00",
      messages_received_count: 47,
      retry_count: 0,
      trade_ingest_count: 5,
      orderbook_ingest_count: 51,
      trade_seen: true,
      orderbook_seen: true,
      best_bid: "74140.2",
      best_ask: "74140.3",
      persisted_trade_count: 492560,
      last_persisted_trade_at: "2026-04-14T21:08:10+00:00",
      last_persisted_trade_symbol: "ETH/USDT",
      recovery_status: "running",
      recovery_stage: "archive_load_started",
      recovery_reason: null,
      scope_mode: "universe",
      total_instruments_discovered: 633,
      volume_filtered_symbols_count: 306,
      filtered_symbols_count: 2,
      selected_symbols_count: 2,
      lifecycle_state: "connected_live",
      symbols: ["BTC/USDT", "ETH/USDT"],
      observed_at: "2026-04-15T00:00:00+00:00",
      persistence_24h: {
        live_trade_count_24h: 28,
        archive_trade_count_24h: 492532,
        persisted_trade_count_24h: 492560,
        first_persisted_trade_at: "2026-04-13T21:30:00+00:00",
        last_persisted_trade_at: "2026-04-14T21:08:10+00:00",
        coverage_status: "hybrid",
      },
      instrument_rows: [
        { symbol: "BTC/USDT", volume_24h_usd: "1", trade_count_24h: 231058 },
        { symbol: "ETH/USDT", volume_24h_usd: "2", trade_count_24h: 261502 },
      ],
      screen_scope_reason: "strict_published_scope",
      contract_flags: {
        row_count_matches_selected_symbols_count: true,
        row_symbols_match_symbols: true,
        pending_archive_rows_masked: true,
        numeric_rows_respect_min_trade_count: true,
        runtime_scope_diverges_from_snapshot: false,
      },
    });

    await page.goto("/terminal/connectors");

    const panel = page.getByTestId("connector-panel-spot-primary");

    await expect(panel).toBeVisible();
    await expect(panel).toContainText("Спотовый рынок");
    await expect(panel).toContainText("Подключено");
    await expect(panel).toContainText(/28 \/ 492\s?532 \/ 492\s?560/);
    await expect(panel).toContainText("BTC/USDT");
    await expect(panel).toContainText("ETH/USDT");
  });

  test("renders real spot primary panel without hanging", async ({ page }) => {
    await page.goto("/terminal/connectors");

    const panel = page.getByTestId("connector-panel-spot-primary");

    await expect(panel).toBeVisible();
    await expect(panel).toContainText("Спотовый рынок");
    await expect(
      panel.getByRole("button", { name: /Подключить|Отключить|Переключаю/ }),
    ).toBeVisible();
    await expect(panel).toContainText(
      /Спотовый коннектор остановлен|Коннектор ещё не вышел в рабочее состояние|Подключение|Persistence 24ч/i,
    );
  });

  test("renders spot primary table from non-empty frozen product snapshot payload", async ({
    page,
  }) => {
    await mockSpotProductSnapshot(page, {
      generation: "v2",
      desired_running: true,
      transport_status: "connected",
      subscription_alive: true,
      transport_rtt_ms: 1,
      last_message_at: "2026-04-25T21:00:00+00:00",
      messages_received_count: 100,
      retry_count: 0,
      trade_ingest_count: 167,
      orderbook_ingest_count: 933,
      trade_seen: true,
      orderbook_seen: true,
      best_bid: "74140.2",
      best_ask: "74140.3",
      persisted_trade_count: 1712191,
      last_persisted_trade_at: "2026-04-25T20:59:59+00:00",
      last_persisted_trade_symbol: "BTC/USDT",
      recovery_status: "running",
      recovery_stage: "archive_load_started",
      recovery_reason: null,
      scope_mode: "universe",
      total_instruments_discovered: 633,
      volume_filtered_symbols_count: 306,
      filtered_symbols_count: 2,
      selected_symbols_count: 2,
      lifecycle_state: "connected_live",
      symbols: ["BTC/USDT", "ETH/USDT"],
      observed_at: "2026-04-25T21:00:00+00:00",
      persistence_24h: {
        live_trade_count_24h: 143686,
        archive_trade_count_24h: 1568505,
        persisted_trade_count_24h: 1712191,
        first_persisted_trade_at: "2026-04-24T21:00:00+00:00",
        last_persisted_trade_at: "2026-04-25T20:59:59+00:00",
        coverage_status: "hybrid",
      },
      instrument_rows: [
        { symbol: "BTC/USDT", volume_24h_usd: "1000.0", trade_count_24h: 105730 },
        { symbol: "ETH/USDT", volume_24h_usd: "2000.0", trade_count_24h: 67009 },
      ],
      screen_scope_reason: "strict_published_scope",
      contract_flags: {
        row_count_matches_selected_symbols_count: true,
        row_symbols_match_symbols: true,
        pending_archive_rows_masked: true,
        numeric_rows_respect_min_trade_count: true,
        runtime_scope_diverges_from_snapshot: false,
      },
    });

    await page.goto("/terminal/connectors");

    const panel = page.getByTestId("connector-panel-spot-primary");
    await expect(panel).toBeVisible();
    await expect(panel).toContainText("Подключено");
    await expect(panel).toContainText("Данные поступают");
    await expect(panel).toContainText("Инструментов в работе: 2");
    await expect(panel).toContainText("Найдено всего: 633 · После объёма: 306 · После сделок: 2");
    await expect(panel).toContainText("143 686 / 1 568 505 / 1 712 191");
    await expect(panel).toContainText("BTC/USDT");
    await expect(panel).toContainText("ETH/USDT");
    await expect(panel).not.toContainText("Canonical product snapshot уже подтвердил пустой рабочий список");
  });

  test("renders stopped state for spot primary panel", async ({ page }) => {
    await mockSpotProductSnapshot(page, {
      generation: "v2",
      desired_running: false,
      transport_status: "disabled",
      subscription_alive: false,
      transport_rtt_ms: null,
      last_message_at: null,
      messages_received_count: 0,
      retry_count: 0,
      trade_ingest_count: 0,
      orderbook_ingest_count: 0,
      trade_seen: false,
      orderbook_seen: false,
      best_bid: null,
      best_ask: null,
      persisted_trade_count: 0,
      last_persisted_trade_at: null,
      last_persisted_trade_symbol: null,
      recovery_status: "idle",
      recovery_stage: "idle",
      recovery_reason: null,
      scope_mode: "universe",
      total_instruments_discovered: 633,
      volume_filtered_symbols_count: 0,
      filtered_symbols_count: 0,
      selected_symbols_count: 0,
      lifecycle_state: "stopped",
      symbols: [],
      observed_at: null,
      persistence_24h: {
        live_trade_count_24h: 0,
        archive_trade_count_24h: 0,
        persisted_trade_count_24h: 0,
        first_persisted_trade_at: null,
        last_persisted_trade_at: null,
        coverage_status: "unavailable",
      },
      instrument_rows: [],
      screen_scope_reason: "empty_scope",
      contract_flags: {
        row_count_matches_selected_symbols_count: true,
        row_symbols_match_symbols: true,
        pending_archive_rows_masked: true,
        numeric_rows_respect_min_trade_count: true,
        runtime_scope_diverges_from_snapshot: false,
      },
    });

    await page.goto("/terminal/connectors");

    const panel = page.getByTestId("connector-panel-spot-primary");
    await expect(panel).toBeVisible();
    await expect(panel).toContainText("Спотовый коннектор остановлен");
    await expect(panel).toContainText("Подключить");
    await expect(panel).not.toContainText("Инструменты в работе");
  });

  test("renders honest empty snapshot state without false rows", async ({ page }) => {
    await mockSpotProductSnapshot(page, {
      generation: "v2",
      desired_running: true,
      transport_status: "connected",
      subscription_alive: true,
      transport_rtt_ms: 1,
      last_message_at: "2026-04-25T21:00:00+00:00",
      messages_received_count: 100,
      retry_count: 0,
      trade_ingest_count: 167,
      orderbook_ingest_count: 933,
      trade_seen: true,
      orderbook_seen: true,
      best_bid: "74140.2",
      best_ask: "74140.3",
      persisted_trade_count: 0,
      last_persisted_trade_at: null,
      last_persisted_trade_symbol: null,
      recovery_status: "running",
      recovery_stage: "archive_load_started",
      recovery_reason: null,
      scope_mode: "universe",
      total_instruments_discovered: 633,
      volume_filtered_symbols_count: 0,
      filtered_symbols_count: 0,
      selected_symbols_count: 0,
      lifecycle_state: "connected_live",
      symbols: [],
      observed_at: "2026-04-25T21:00:00+00:00",
      persistence_24h: {
        live_trade_count_24h: 0,
        archive_trade_count_24h: 0,
        persisted_trade_count_24h: 0,
        first_persisted_trade_at: null,
        last_persisted_trade_at: null,
        coverage_status: "pending_live",
      },
      instrument_rows: [],
      screen_scope_reason: "empty_scope",
      contract_flags: {
        row_count_matches_selected_symbols_count: true,
        row_symbols_match_symbols: true,
        pending_archive_rows_masked: true,
        numeric_rows_respect_min_trade_count: true,
        runtime_scope_diverges_from_snapshot: false,
      },
    });

    await page.goto("/terminal/connectors");

    const panel = page.getByTestId("connector-panel-spot-primary");
    await expect(panel).toBeVisible();
    await expect(panel).toContainText("По текущим фильтрам инструменты не прошли");
    await expect(panel).toContainText(
      "Canonical product snapshot уже подтвердил пустой рабочий список",
    );
    await expect(panel).not.toContainText("BTC/USDT");
  });

  test("keeps snapshot rows when runtime scope is wider than product snapshot scope", async ({
    page,
  }) => {
    await mockSpotProductSnapshot(page, {
      generation: "v2",
      desired_running: true,
      transport_status: "connected",
      subscription_alive: true,
      transport_rtt_ms: 1,
      last_message_at: "2026-04-25T21:00:00+00:00",
      messages_received_count: 100,
      retry_count: 0,
      trade_ingest_count: 167,
      orderbook_ingest_count: 933,
      trade_seen: true,
      orderbook_seen: true,
      best_bid: "74140.2",
      best_ask: "74140.3",
      persisted_trade_count: 514073,
      last_persisted_trade_at: "2026-04-25T20:59:59+00:00",
      last_persisted_trade_symbol: "BTC/USDT",
      recovery_status: "running",
      recovery_stage: "archive_load_started",
      recovery_reason: null,
      scope_mode: "universe",
      total_instruments_discovered: 633,
      volume_filtered_symbols_count: 306,
      filtered_symbols_count: 44,
      selected_symbols_count: 2,
      lifecycle_state: "connected_live",
      symbols: ["BTC/USDT", "ETH/USDT"],
      observed_at: "2026-04-25T21:00:00+00:00",
      persistence_24h: {
        live_trade_count_24h: 244964,
        archive_trade_count_24h: 269109,
        persisted_trade_count_24h: 514073,
        first_persisted_trade_at: "2026-04-24T21:00:00+00:00",
        last_persisted_trade_at: "2026-04-25T20:59:59+00:00",
        coverage_status: "hybrid",
      },
      instrument_rows: [
        { symbol: "BTC/USDT", volume_24h_usd: "1000.0", trade_count_24h: 23099 },
        { symbol: "ETH/USDT", volume_24h_usd: "2000.0", trade_count_24h: 13590 },
      ],
      screen_scope_reason: "strict_published_scope",
      contract_flags: {
        row_count_matches_selected_symbols_count: true,
        row_symbols_match_symbols: true,
        pending_archive_rows_masked: true,
        numeric_rows_respect_min_trade_count: true,
        runtime_scope_diverges_from_snapshot: false,
      },
    });

    await page.goto("/terminal/connectors");

    const panel = page.getByTestId("connector-panel-spot-primary");
    await expect(panel).toBeVisible();
    await expect(panel).toContainText("Инструментов в работе: 2");
    await expect(panel).toContainText("Найдено всего: 633 · После объёма: 306 · После сделок: 44");
    await expect(panel).toContainText("BTC/USDT");
    await expect(panel).toContainText("ETH/USDT");
    await expect(panel).not.toContainText("По текущим фильтрам инструменты не прошли");
  });
});
