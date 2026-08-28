import { expect, test } from "@playwright/test";

test("chat turns multiple explicit observations into one confirmed add flow", async ({ page, request }, testInfo) => {
  const consoleProblems: string[] = [];
  page.on("console", (message) => { if (["error", "warning"].includes(message.type())) consoleProblems.push(message.text()); });
  page.on("pageerror", (error) => consoleProblems.push(error.message));

  await page.goto("/");
  await page.getByLabel("健康问题").fill("帮我记一下：今天喝水1.5升，走了6200步，昨晚睡了7小时30分钟，体重69.2公斤，心情4分");
  await page.locator('button[title="发送"]').click();

  await expect(page.getByRole("heading", { name: "发现可添加的健康记录" })).toBeVisible();
  await expect(page.getByLabel("饮水数值")).toHaveValue("1500");
  await expect(page.getByLabel("步数数值")).toHaveValue("6200");
  await expect(page.getByLabel("睡眠数值")).toHaveValue("450");
  await expect(page.getByLabel("体重数值")).toHaveValue("69.2");
  await expect(page.getByLabel("心情数值")).toHaveValue("4");
  await page.getByLabel("饮水数值").fill("1600");

  const screenshotPath = process.env.QA_CHAT_RECORD_SCREENSHOT_PATH;
  if (screenshotPath) await page.screenshot({ path: screenshotPath.replace(/\.png$/i, `-draft-${testInfo.project.name}.png`), fullPage: false });

  await page.getByRole("button", { name: "确认添加", exact: true }).click();
  const batchResponsePromise = page.waitForResponse((response) => response.url().endsWith("/api/v1/observations/batch") && response.request().method() === "POST");
  await page.getByRole("button", { name: "确认并添加", exact: true }).click();
  const batchResponse = await batchResponsePromise;
  expect(batchResponse.ok()).toBeTruthy();
  const records = await batchResponse.json() as Array<{ id: string }>;
  await expect(page.getByRole("heading", { name: "已添加 5 条健康记录" })).toBeVisible();

  for (const record of records) await request.delete(`http://127.0.0.1:8000/api/v1/observations/${record.id}`);
  const overflow = await page.evaluate(() => ({ scrollWidth: document.documentElement.scrollWidth, clientWidth: document.documentElement.clientWidth }));
  expect(overflow.scrollWidth).toBeLessThanOrEqual(overflow.clientWidth);
  expect(consoleProblems).toEqual([]);

  if (screenshotPath) await page.screenshot({ path: screenshotPath.replace(/\.png$/i, `-${testInfo.project.name}.png`), fullPage: false });
});
