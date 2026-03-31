import { expect, test } from "@playwright/test";

const backendBaseUrl = "http://127.0.0.1:8000";

const keySections = [
  "Фильтр рынка и допуск инструментов",
  "Пороги сигналов и принятия решений",
  "Базовые лимиты риска",
  "Таймауты состояний системы",
  "Ручное подтверждение действий",
  "Подключение к рынку и переподключение",
] as const;

const backendRoutes = [
  "/dashboard/settings/universe-policy",
  "/dashboard/settings/decision-thresholds",
  "/dashboard/settings/risk-limits",
  "/dashboard/settings/system-state-timeouts",
  "/dashboard/settings/manual-approval-policy",
  "/dashboard/settings/live-feed-policy",
] as const;

test.describe("Terminal settings acceptance", () => {
  test.beforeEach(async ({ request }) => {
    for (const route of backendRoutes) {
      const response = await request.get(`${backendBaseUrl}${route}`);
      expect(
        response.ok(),
        `Expected backend route ${route} to be available for terminal settings acceptance`,
      ).toBeTruthy();
    }
  });

  test("renders key backend-backed sections without load errors", async ({ page }) => {
    await page.goto("/terminal/settings");
    await expect(
      page.getByRole("heading", { name: "Фильтр рынка и допуск инструментов" }),
    ).toBeVisible();

    for (const sectionTitle of keySections) {
      const section = page
        .locator("section")
        .filter({ has: page.getByRole("heading", { name: sectionTitle }) });
      await expect(section).toBeVisible();
      await expect(section.getByText("Ошибка загрузки")).toHaveCount(0);
    }

    await expect(page.getByText("Manual approval")).toHaveCount(0);
    await expect(page.getByText("Decision chain")).toHaveCount(0);
    await expect(page.getByText("Event Bus")).toHaveCount(0);
    await expect(page.getByRole("button", { name: "Сохранить настройки" }).first()).toBeVisible();
  });

  test("can save manual approval setting and keep value after reload", async ({ page }) => {
    await page.goto("/terminal/settings");

    const section = page
      .locator("section")
      .filter({ has: page.getByRole("heading", { name: "Ручное подтверждение действий" }) });
    await expect(section).toBeVisible();

    const input = section.locator('input[type="number"]').first();
    const originalValue = await input.inputValue();
    const updatedValue = originalValue === "5" ? "6" : "5";
    const saveButton = section.getByRole("button", { name: "Сохранить настройки" });
    const badge = section.getByText(/Backend|Сохранено|Сохранение/).first();

    await input.fill(updatedValue);
    await saveButton.click();
    await expect(badge).toContainText("Сохранено");

    await page.reload();
    const reloadedSection = page
      .locator("section")
      .filter({ has: page.getByRole("heading", { name: "Ручное подтверждение действий" }) });
    await expect(reloadedSection.locator('input[type="number"]').first()).toHaveValue(updatedValue);

    const revertInput = reloadedSection.locator('input[type="number"]').first();
    const revertButton = reloadedSection.getByRole("button", { name: "Сохранить настройки" });
    await revertInput.fill(originalValue);
    await revertButton.click();
    await expect(reloadedSection.getByText(/Backend|Сохранено|Сохранение/).first()).toContainText(
      "Сохранено",
    );
  });
});
