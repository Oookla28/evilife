import { expect, test } from "@playwright/test";

test("fasting timer completes start and explicit end-confirm flow", async ({ page }) => {
  let active: Record<string, unknown> | null = null;

  await page.route(/\/api\/v1\/today\?/, async (route) => {
    await route.fulfill({ json: { date: "2026-08-11", fasts: [], meals: [] } });
  });
  await page.route("**/api/v1/fasts/active", async (route) => {
    await route.fulfill({ json: active });
  });
  await page.route(/\/api\/v1\/fasts\?/, async (route) => {
    await route.fulfill({ json: [] });
  });
  await page.route("**/api/v1/fasts/start", async (route) => {
    active = {
      id: "fast-e2e",
      start_at: new Date().toISOString(),
      end_at: null,
      goal_hours: 16,
      status: "active",
    };
    await route.fulfill({ json: active });
  });
  await page.route("**/api/v1/fasts/fast-e2e/end", async (route) => {
    const completed = {
      ...active,
      end_at: new Date().toISOString(),
      status: "completed",
    };
    active = null;
    await route.fulfill({ json: completed });
  });

  await page.goto("/today");
  await expect(page.getByText("进食间隔计时")).toBeVisible();
  await expect(page.getByRole("button", { name: "开始记录" })).toBeEnabled();
  await page.getByRole("button", { name: "开始记录" }).click();
  await expect(page.getByRole("button", { name: "结束计时" })).toBeVisible();
  await page.getByRole("button", { name: "结束计时" }).click();
  await expect(page.getByText("结束并保存这段客观记录？")).toBeVisible();
  await page.getByRole("button", { name: "结束并保存" }).click();
  await expect(page.getByRole("button", { name: "开始记录" })).toBeVisible();
});
