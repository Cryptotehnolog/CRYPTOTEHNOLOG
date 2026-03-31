import { expect, test } from "@playwright/test";

const backendBaseUrl = "http://127.0.0.1:8000";

const openHomeColumns = ["instrument", "current_price", "pnl_usd", "pnl_percent"];
const historyHomeColumns = [
  "instrument",
  "exit",
  "result_usd",
  "result_percent",
  "exit_reason",
];

test.describe("Terminal home acceptance", () => {
  test.beforeEach(async ({ request, page }) => {
    const openPositionsResponse = await request.get(`${backendBaseUrl}/dashboard/open-positions`);
    expect(
      openPositionsResponse.ok(),
      "Expected /dashboard/open-positions to be available for terminal home acceptance",
    ).toBeTruthy();

    const positionHistoryResponse = await request.get(
      `${backendBaseUrl}/dashboard/position-history`,
    );
    expect(
      positionHistoryResponse.ok(),
      "Expected /dashboard/position-history to be available for terminal home acceptance",
    ).toBeTruthy();

    await page.addInitScript(
      ({ nextOpenColumns, nextHistoryColumns }) => {
        window.localStorage.removeItem("cryptotechnolog.terminal.widgets");
        window.localStorage.setItem(
          "cryptotechnolog.terminal.open-positions.home-columns",
          JSON.stringify(nextOpenColumns),
        );
        window.localStorage.setItem(
          "cryptotechnolog.terminal.position-history.home-columns",
          JSON.stringify(nextHistoryColumns),
        );
      },
      {
        nextOpenColumns: openHomeColumns,
        nextHistoryColumns: historyHomeColumns,
      },
    );
  });

  test("renders positions widget, switches tabs, shows surfaced fields, and opens actions", async ({
    page,
    request,
  }) => {
    const historyResponse = await request.get(`${backendBaseUrl}/dashboard/position-history`);
    const historyPayload = (await historyResponse.json()) as {
      positions: Array<{
        strategy: string | null;
        exit_price: string | null;
        exit_reason: string | null;
      }>;
    };

    const historyStrategy =
      historyPayload.positions.find((item) => item.strategy && item.strategy.trim())?.strategy ??
      null;
    const hasExitPrice = historyPayload.positions.some((item) => item.exit_price !== null);
    const hasExitReason = historyPayload.positions.some((item) => item.exit_reason !== null);

    await page.goto("/terminal");

    const openTab = page.getByRole("button", { name: "Открытые позиции" });
    const historyTab = page.getByRole("button", { name: "История позиций" });

    await expect(openTab).toBeVisible();
    await expect(historyTab).toBeVisible();
    await expect(page.getByText("Ошибка: открытые позиции недоступны")).toHaveCount(0);
    await expect(page.getByText("Ошибка: история позиций недоступна")).toHaveCount(0);
    await expect(page.getByText("undefined")).toHaveCount(0);

    await expect(page.getByText("Текущая цена", { exact: true })).toBeVisible();
    await expect(page.getByText("PnL USD", { exact: true })).toBeVisible();
    await expect(page.getByText("PnL %", { exact: true })).toBeVisible();

    const actionsButton = page.locator('[aria-label^="Действия пока недоступны для "]').first();
    await expect(actionsButton).toBeVisible();
    await actionsButton.click();
    await expect(page.getByRole("menu")).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(page.getByRole("menu")).toHaveCount(0);

    await historyTab.click();
    await expect(page.getByText("Результат USD", { exact: true })).toBeVisible();
    await expect(page.getByText("Результат %", { exact: true })).toBeVisible();
    if (hasExitPrice) {
      await expect(page.getByText("Выход", { exact: true })).toBeVisible();
    }
    if (hasExitReason) {
      await expect(page.getByText("Причина выхода", { exact: true })).toBeVisible();
    }
    if (historyStrategy) {
      await expect(page.locator("span").filter({ hasText: historyStrategy }).first()).toBeVisible();
    }
    await expect(page.getByText("Ошибка: история позиций недоступна")).toHaveCount(0);
    await expect(page.getByText("undefined")).toHaveCount(0);
  });
});
