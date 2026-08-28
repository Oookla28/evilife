import { expect, test } from "@playwright/test";

test.describe.configure({ mode: "serial" });

test("chat invokes profile analysis as one comprehensive card", async ({ page }, testInfo) => {
  test.setTimeout(120_000);
  await page.goto("/");
  await page.getByLabel("健康问题").fill("请综合分析一下我的身体状况");
  await page.locator('button[title="发送"]').click();
  await expect(page.getByRole("heading", { name: "综合健康分析" })).toBeVisible({ timeout: 90_000 });
  await expect(page.getByText("需关注信号", { exact: true })).toBeVisible();
  await expect(page.getByText("生活建议", { exact: true })).toBeVisible();
  const screenshot = process.env.QA_CHAT_FEATURE_SCREENSHOT_PATH;
  if (screenshot) await page.screenshot({ path: screenshot.replace(/\.png$/i, `-profile-${testInfo.project.name}.png`), fullPage: false });
});

test("chat invokes multiple implemented tools in the answer window", async ({ page }) => {
  await page.goto("/");
  await page.getByLabel("健康问题").fill("显示今日记录，再打开16:8计时");
  await page.locator('button[title="发送"]').click();
  await expect(page.getByRole("heading", { name: "今日记录" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "进食间隔计时" })).toBeVisible();
});

test("medical answer includes a bounded TCM database perspective", async ({ page }, testInfo) => {
  test.setTimeout(120_000);
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/");
  await page.getByLabel("健康问题").fill("地中海饮食对心血管风险有什么证据？");
  await page.locator('button[title="发送"]').click();
  const flow = page.getByTestId("medical-card-flow");
  await expect(flow).toHaveAttribute("data-phase", "idle", { timeout: 90_000 });
  const count = Number(await flow.getAttribute("data-card-count"));
  for (let index = 2; index <= count; index += 1) {
    await flow.getByRole("button", { name: "下一张证据卡" }).click();
    await expect(flow.getByText(`${index}/${count}`, { exact: true })).toBeVisible();
  }
  await expect(flow.locator('[data-card-id="tcm-perspective"]')).toBeAttached();
  await expect(flow.getByText("中医视角", { exact: true }).first()).toBeVisible();
  const screenshot = process.env.QA_CHAT_FEATURE_SCREENSHOT_PATH;
  if (screenshot) await flow.screenshot({ path: screenshot.replace(/\.png$/i, `-flow-${testInfo.project.name}.png`) });
  const card = flow.locator('[data-card-id="tcm-perspective"]');
  await card.click();
  await expect(card).toHaveAttribute("data-flipped", "true");
  await expect(card.getByText("与当前问题的关系", { exact: true })).toBeVisible();
  await expect(card.getByText("证据策略", { exact: true })).toBeVisible();
  await flow.getByRole("button", { name: "放大当前证据卡" }).click();
  const dialog = page.getByRole("dialog");
  await expect(dialog.getByRole("heading", { name: "中医视角" })).toBeVisible();
  await expect(dialog.getByText("AI 综合总结", { exact: true })).toBeVisible();
  await expect(dialog.getByText("参考文献 1", { exact: true })).toBeVisible();
  await expect(dialog.getByText(/中国生物医学文献服务系统 SinoMed/)).toBeVisible();
  if (screenshot) await page.screenshot({ path: screenshot.replace(/\.png$/i, `-expanded-${testInfo.project.name}.png`), fullPage: false });
});
