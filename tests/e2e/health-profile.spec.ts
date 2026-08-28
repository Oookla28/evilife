import { expect, test } from "@playwright/test";

test("experimenter profile records an observation and updates the dashboard", async ({ page }, testInfo) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  const consoleProblems: string[] = [];
  page.on("console", (message) => {
    if (["error", "warning"].includes(message.type())) consoleProblems.push(message.text());
  });
  page.on("pageerror", (error) => consoleProblems.push(error.message));

  const observations: Array<Record<string, unknown>> = [];
  await page.route("**/api/v1/today?**", (route) => route.fulfill({
    json: { date: "2026-08-11", fasts: [], meals: [], observations },
  }));
  await page.route("**/api/v1/observations?**", (route) => route.fulfill({ json: observations }));
  await page.route("**/api/v1/observations", async (route) => {
    const body = route.request().postDataJSON();
    const record = {
      id: "obs-water-e2e",
      ...body,
      note: body.note ?? null,
      observed_at: "2026-08-11T08:10:00Z",
    };
    observations.unshift(record);
    await route.fulfill({ json: record });
  });
  await page.route("**/api/v1/health-connectors", (route) => route.fulfill({ json: [
    { id: "apple_healthkit", label: "Apple 健康", status: "requires_native_bridge", authorization: "需要用户在 iPhone 应用内按数据类型授权", transport: "native", docs_url: "https://developer.apple.com/documentation/healthkit", supported_kinds: ["steps"] },
    { id: "android_health_connect", label: "Android Health Connect", status: "requires_native_bridge", authorization: "需要用户在 Android 应用内授权读取范围", transport: "native", docs_url: "https://developer.android.com/health-and-fitness/health-connect", supported_kinds: ["steps"] },
    { id: "huawei_health_kit", label: "华为运动健康", status: "requires_credentials", authorization: "需要 Health Kit 开发者配置和用户授权", transport: "adapter", docs_url: "https://developer.huawei.com/consumer/en/hms/huaweihealth/", supported_kinds: ["steps"] },
    { id: "generic_import", label: "通用数据导入", status: "available", authorization: "调用方必须提交用户同意回执", transport: "https", docs_url: "/docs", supported_kinds: ["steps"] },
  ] }));
  await page.route("**/api/v1/profile/analyze", (route) => route.fulfill({ json: {
    source: "deterministic_fallback",
    cards: [
      { tone: "summary", title: "综合健康分析", preview: "已综合整理近期身体记录。", details: [
        { label: "分析依据", value: "1 条数值记录" },
        { label: "整体趋势", value: "连续数据不足" },
        { label: "需关注信号", value: "暂未发现持续偏离" },
        { label: "生活建议", value: "保持规律作息并继续记录" },
      ] },
    ],
  } }));

  await page.goto("/profile");
  await expect(page.getByRole("heading", { name: "实验者健康档案" })).toBeVisible();
  await expect(page.getByText("记录事实，观察变化，不替代医学判断")).toBeVisible();
  await expect(page.getByTestId("medical-card-flow")).toHaveAttribute("data-card-count", "7");
  await expect(page.getByTestId("medical-card-flow").getByText("今日记录", { exact: true }).first()).toBeVisible();
  const profileScroller = page.getByTestId("profile-scroll-container");
  const scrollMetrics = await profileScroller.evaluate((element) => ({ clientHeight: element.clientHeight, scrollHeight: element.scrollHeight }));
  expect(scrollMetrics.scrollHeight).toBeGreaterThan(scrollMetrics.clientHeight);
  await profileScroller.evaluate((element) => element.scrollTo({ top: element.scrollHeight }));
  await expect(page.getByText("连接健康软件", { exact: true })).toBeVisible();
  expect(await profileScroller.evaluate((element) => element.scrollTop)).toBeGreaterThan(0);
  await profileScroller.evaluate((element) => element.scrollTo({ top: 0 }));

  await page.getByRole("button", { name: "添加记录" }).click();
  const dialog = page.getByRole("dialog", { name: "添加观察记录" });
  await expect(dialog).toBeVisible();
  await dialog.getByRole("button", { name: "饮水" }).click();
  await dialog.getByLabel("饮水（ml）").fill("300");
  await dialog.getByRole("button", { name: "确认记录" }).click();

  await expect(dialog).toBeHidden();
  await expect(page.getByText("300 ml", { exact: true }).first()).toBeVisible();
  await expect(page.getByText("还可补充 4 类观察")).toBeVisible();
  await expect(page.getByText("本人手动记录").first()).toBeVisible();
  await expect(page.getByText("需要手机端授权 / 原生桥接").first()).toBeVisible();
  await expect(page.getByText("导入接口已就绪")).toBeVisible();
  await page.getByRole("button", { name: "生成综合分析" }).click();
  await expect(page.getByRole("heading", { name: "综合健康分析" })).toBeVisible();
  await expect(page.getByTestId("medical-card-flow")).toHaveAttribute("data-card-count", "8");
  await expect(page.getByText("AI 暂不可用，已使用本地规则整理")).toBeVisible();
  await expect(page.getByText("8/8", { exact: true })).toBeVisible();
  const overflow = await page.evaluate(() => ({
    scrollWidth: document.documentElement.scrollWidth,
    clientWidth: document.documentElement.clientWidth,
  }));
  expect(overflow.scrollWidth).toBeLessThanOrEqual(overflow.clientWidth);

  const screenshotPath = process.env.QA_PROFILE_SCREENSHOT_PATH;
  if (screenshotPath) {
    await page.screenshot({
      path: screenshotPath.replace(/\.png$/i, `-${testInfo.project.name}.png`),
      fullPage: false,
    });
  }
  expect(consoleProblems).toEqual([]);
});

test("profile shows its base Flow immediately and prints only the newly added record", async ({ page }, testInfo) => {
  const observations: Array<Record<string, unknown>> = [];
  await page.route("**/api/v1/today?**", (route) => route.fulfill({ json: { date: "2026-08-11", fasts: [], meals: [], observations } }));
  await page.route("**/api/v1/observations?**", (route) => route.fulfill({ json: observations }));
  await page.route("**/api/v1/observations", async (route) => {
    const body = route.request().postDataJSON();
    const record = { id: "obs-new-only", ...body, note: body.note ?? null, observed_at: "2026-08-11T09:00:00Z" };
    observations.unshift(record);
    await route.fulfill({ json: record });
  });
  await page.route("**/api/v1/health-connectors", (route) => route.fulfill({ json: [] }));
  await page.goto("/profile");
  const flow = page.getByTestId("medical-card-flow");
  await expect(flow).toHaveAttribute("data-phase", "idle");
  await expect(flow).toHaveAttribute("data-card-count", "7");
  await page.getByRole("button", { name: "添加记录" }).click();
  const dialog = page.getByRole("dialog", { name: "添加观察记录" });
  await dialog.getByRole("button", { name: "饮水" }).click();
  await dialog.getByLabel("饮水（ml）").fill("300");
  await dialog.getByRole("button", { name: "确认记录" }).click();
  await expect(flow).toHaveAttribute("data-phase", "printing");
  await expect(flow).toHaveAttribute("data-card-count", "7");
  await expect(flow).toContainText("第 1/1 张新增中文观察卡");
  await expect(flow).toHaveAttribute("data-card-count", "8", { timeout: 2600 });
  await expect(flow).toHaveAttribute("data-phase", "idle", { timeout: 1800 });
  const screenshotPath = process.env.QA_PROFILE_DEFAULT_FLOW_SCREENSHOT_PATH;
  if (screenshotPath) await page.screenshot({ path: screenshotPath.replace(/\.png$/i, `-${testInfo.project.name}.png`), fullPage: false });
});

test("a large Apple Health import prints one summary card only", async ({ page }, testInfo) => {
  let imported = false;
  await page.route("**/api/v1/today?**", (route) => route.fulfill({ json: { date: "2026-08-12", fasts: [], meals: [], observations: [] } }));
  await page.route("**/api/v1/observations?**", (route) => route.fulfill({ json: imported ? [
    { id: "apple-step", kind: "steps", value: 6200, note: null, source: "device", observed_at: "2026-08-11T12:00:00Z", connector_id: "apple_healthkit", external_id: "apple-export:steps:2026-08-11" },
    { id: "apple-sleep", kind: "sleep_minutes", value: 450, note: null, source: "device", observed_at: "2026-08-11T12:00:00Z", connector_id: "apple_healthkit", external_id: "apple-export:sleep_minutes:2026-08-11" },
  ] : [] }));
  await page.route("**/api/v1/health-connectors", (route) => route.fulfill({ json: [
    { id: "apple_healthkit", label: "Apple 健康", status: "requires_native_bridge", authorization: "自动同步需要 iPhone 原生授权；网页可手动导入 Apple 健康 XML", transport: "Apple 健康 XML 手动导入", docs_url: "https://developer.apple.com/documentation/healthkit", supported_kinds: ["steps", "sleep_minutes"] },
  ] }));
  await page.route("**/api/v1/health-imports/apple", async (route) => {
    imported = true;
    await route.fulfill({ json: { id: "apple-import-e2e", status: "queued", processed_records: 0, summary: null, error: null } });
  });
  await page.route("**/api/v1/health-imports/apple/apple-import-e2e", (route) => route.fulfill({ json: {
    id: "apple-import-e2e", status: "completed", processed_records: 1309432, error: null,
    summary: { source_file: "导出.xml", processed_records: 1309432, accepted: 2253, skipped: 0, date_from: "2020-11-20", date_to: "2026-08-11", counts: { steps: 1389, sleep_minutes: 338, weight_kg: 169, resting_heart_rate: 357 } },
  } }));

  await page.goto("/profile");
  const flow = page.getByTestId("medical-card-flow");
  await expect(flow).toHaveAttribute("data-card-count", "7");
  await page.getByLabel("选择 Apple 健康导出 XML").setInputFiles({ name: "导出.xml", mimeType: "text/xml", buffer: Buffer.from("<?xml version=\"1.0\"?><HealthData/>") });
  await expect(flow).toHaveAttribute("data-phase", "printing");
  await expect(flow).toContainText("第 1/1 张新增中文观察卡");
  await expect(flow).toHaveAttribute("data-card-count", "8", { timeout: 3000 });
  await expect(flow).toHaveAttribute("data-phase", "idle", { timeout: 1800 });
  await expect(flow.getByText("Apple 健康数据已导入", { exact: true }).first()).toBeVisible();
  await expect(page.getByText("导入完成：新增 2253 条每日汇总，正在打印一张摘要卡。")).toBeVisible();
  const screenshotPath = process.env.QA_APPLE_IMPORT_SCREENSHOT_PATH;
  if (screenshotPath) await page.screenshot({ path: screenshotPath.replace(/\.png$/i, `-${testInfo.project.name}.png`), fullPage: false });
});

test("Flow card back and enlarged detail show monthly and yearly health trends", async ({ page }, testInfo) => {
  const observations = Array.from({ length: 420 }, (_, index) => {
    const date = new Date("2026-08-11T12:00:00Z"); date.setUTCDate(date.getUTCDate() - index);
    return { id: `step-${index}`, kind: "steps", value: 4200 + (index % 11) * 430, note: null, source: "device", observed_at: date.toISOString(), connector_id: "apple_healthkit", external_id: `apple-export:steps:${date.toISOString().slice(0, 10)}` };
  });
  await page.route("**/api/v1/today?**", (route) => route.fulfill({ json: { date: "2026-08-12", fasts: [], meals: [], observations: [] } }));
  await page.route("**/api/v1/observations?**", (route) => route.fulfill({ json: observations }));
  await page.route("**/api/v1/health-connectors", (route) => route.fulfill({ json: [] }));
  await page.goto("/profile");
  const flow = page.getByTestId("medical-card-flow");
  await flow.getByRole("button", { name: "下一张观察卡" }).click();
  await expect(flow.getByText("2/7", { exact: true })).toBeVisible();
  const activityCard = flow.locator('[data-card-id="profile-activity"]');
  await activityCard.click();
  await expect(activityCard).toHaveAttribute("data-flipped", "true");
  await expect(activityCard.getByText("放大查看日、月、年趋势")).toBeVisible();
  await flow.getByRole("button", { name: "放大当前观察卡" }).click();
  const dialog = page.getByRole("dialog");
  await expect(dialog.getByRole("heading", { name: "活动与步数" })).toBeVisible();
  await expect(dialog.getByRole("img", { name: "步数变化折线变化图" })).toBeVisible();
  await dialog.getByRole("tab", { name: "年", exact: true }).click();
  await expect(dialog.getByRole("tab", { name: "年", exact: true })).toHaveAttribute("aria-selected", "true");
  await expect(dialog.getByText("Apple 健康导出").first()).toBeVisible();
  await expect(dialog.getByText("平均值")).toBeVisible();
  const screenshotPath = process.env.QA_FLOW_TREND_SCREENSHOT_PATH;
  if (screenshotPath) await page.screenshot({ path: screenshotPath.replace(/\.png$/i, `-${testInfo.project.name}.png`), fullPage: false });
});
