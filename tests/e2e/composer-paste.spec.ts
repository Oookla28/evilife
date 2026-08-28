import { expect, test } from "@playwright/test";

test("composer accepts pasted images and document files", async ({ page }, testInfo) => {
  const consoleProblems: string[] = [];
  page.on("console", (message) => {
    if (["error", "warning"].includes(message.type())) {
      consoleProblems.push(message.text());
    }
  });
  page.on("pageerror", (error) => consoleProblems.push(error.message));

  await page.goto("/");
  const textbox = page.getByRole("textbox", { name: "健康问题" });
  await expect(textbox).toBeVisible();

  await textbox.evaluate((element) => {
    const transfer = new DataTransfer();
    transfer.items.add(
      new File([new Uint8Array([137, 80, 78, 71])], "clipboard-image.png", {
        type: "image/png",
      })
    );
    element.dispatchEvent(
      new ClipboardEvent("paste", { bubbles: true, clipboardData: transfer })
    );
  });
  await expect(page.getByText("clipboard-image.png")).toBeVisible();
  await expect(page.getByTitle("发送")).toBeEnabled();

  const screenshotPath = process.env.QA_SCREENSHOT_PATH;
  if (screenshotPath) {
    await page.waitForTimeout(350);
    await page.screenshot({
      path: screenshotPath.replace(/\.png$/i, `-${testInfo.project.name}.png`),
      fullPage: false,
    });
  }

  await page.getByRole("button", { name: "移除附件" }).click();
  await textbox.evaluate((element) => {
    const transfer = new DataTransfer();
    transfer.items.add(new File(["report"], "copied-report.docx", { type: "" }));
    element.dispatchEvent(
      new ClipboardEvent("paste", { bubbles: true, clipboardData: transfer })
    );
  });
  await expect(page.getByText("copied-report.docx")).toBeVisible();
  await expect(page.getByTitle("发送")).toBeEnabled();
  expect(consoleProblems).toEqual([]);
});
