import { expect, test } from "@playwright/test";

test("meal analysis shows a model center estimate and recalculates from corrected grams", async ({ page }, testInfo) => {
  await page.route("**/api/v1/orchestrate", (route) => route.fulfill({ json: {
    request_id: "request-meal-e2e",
    session_id: "session-meal-e2e",
    run_id: "run-meal-e2e",
    intent: "analyze_meal",
    gate_status: "normal",
    status: "completed",
    actions: [],
    module_plan: [{
      module_id: "meal-e2e",
      type: "MealAnalyzer",
      status: "ready",
      props: {
        action_id: "action-meal-e2e",
        items: [
          { id: "chicken", name: "香煎鸡胸肉", portion: "150g", portion_grams: [140, 160], estimated_calories: [240, 280], estimated_calories_center: 260, confidence: "medium", reference_basis: "按可见鸡胸肉重量和少量煎制用油换算。", uncertainty: "隐藏用油会影响结果。" },
          { id: "broccoli", name: "西兰花", portion: "100g", portion_grams: [90, 110], estimated_calories: [30, 45], estimated_calories_center: 38, confidence: "high", reference_basis: "按熟制蔬菜重量换算。", uncertainty: "调味油不可见。" },
          { id: "rice", name: "糙米饭", portion: "120g", portion_grams: [110, 130], estimated_calories: [130, 160], estimated_calories_center: 145, confidence: "medium", reference_basis: "按熟米饭体积与常见能量密度换算。", uncertainty: "拍摄角度影响体积判断。" },
        ],
        total_calories: [400, 485],
        total_calories_center: 443,
        overall_uncertainty: "单张照片看不到食物厚度和全部用油。",
      },
    }],
  } }));
  await page.route("**/api/v1/runs/run-meal-e2e/events", (route) => route.fulfill({
    status: 200,
    contentType: "text/event-stream",
    body: `data: ${JSON.stringify({ event_id: "event-complete", request_id: "request-meal-e2e", run_id: "run-meal-e2e", type: "run.completed", timestamp: new Date().toISOString(), payload: {} })}\n\n`,
  }));

  await page.goto("/");
  const textbox = page.getByRole("textbox", { name: "健康问题" });
  await textbox.fill("估算这顿饭的热量");
  await textbox.evaluate((element) => {
    const transfer = new DataTransfer();
    transfer.items.add(new File([new Uint8Array([137, 80, 78, 71])], "meal.png", { type: "image/png" }));
    element.dispatchEvent(new ClipboardEvent("paste", { bubbles: true, clipboardData: transfer }));
  });
  await page.getByTitle("发送").click();

  await expect(page.getByRole("heading", { name: "餐食成分识别" })).toBeVisible();
  await expect(page.getByText("约 443 kcal")).toBeVisible();
  await expect(page.getByText("合理范围 400–485 kcal")).toBeVisible();
  await expect(page.getByText("中等置信").first()).toBeVisible();

  await page.getByRole("button", { name: /150g/ }).click();
  const portion = page.locator('input[type="text"][value="150g"]');
  await portion.fill("300g");
  await portion.press("Enter");
  await expect(page.getByText("约 703 kcal")).toBeVisible();
  await expect(page.getByText("合理范围 640–765 kcal")).toBeVisible();

  const screenshotPath = process.env.QA_MEAL_SCREENSHOT_PATH;
  if (screenshotPath) await page.screenshot({ path: screenshotPath.replace(/\.png$/i, `-${testInfo.project.name}.png`), fullPage: false });
});
