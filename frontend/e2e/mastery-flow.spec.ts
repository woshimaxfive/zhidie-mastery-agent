import path from "node:path";
import { fileURLToPath } from "node:url";

import { expect, test, type Page } from "@playwright/test";


const guideImageDirectory = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "..",
  "..",
  "docs",
  "images",
  "user-guide",
);

async function captureGuideScreenshot(name: string, page: Page) {
  if (process.env.CAPTURE_GUIDE_SCREENSHOTS !== "1") return;
  await page.screenshot({ path: path.join(guideImageDirectory, name), fullPage: false });
}


test("独立掌握、错因提示与新变式复验形成完整证据链", async ({ page }) => {
  const consoleErrors: string[] = [];
  page.on("console", (message) => {
    if (message.type() === "error") consoleErrors.push(message.text());
  });

  await page.goto("/");
  await page.getByRole("button", { name: "开始诊断" }).click();

  await page.getByLabel("你的答案").fill("[2, 5, 8]");
  await page.getByRole("button", { name: "提交答案" }).click();
  await expect(page.getByText("[1, 4, 7, 10]", { exact: true })).toBeVisible();

  await page.getByLabel("你的答案").fill("range(1, 11, 3)");
  await page.getByRole("button", { name: "提交答案" }).click();
  await expect(page.locator(".completion").getByRole("heading", { name: "迁移验证已经通过" })).toBeVisible();

  await page.getByRole("link", { name: "学习首页" }).click();
  await expect(page.getByRole("button", { name: "再练一次" })).toBeVisible();
  await captureGuideScreenshot("repractice.png", page);
  await page.getByRole("button", { name: "再练一次" }).click();

  await page.getByLabel("你的答案").fill("[2, 3, 4]");
  await page.getByRole("button", { name: "提交答案" }).click();
  await expect(page.locator(".feedback").getByText("你把步长 3 理解成了每次增加 1。")).toBeVisible();
  await page.getByRole("button", { name: "我需要一点提示" }).click();
  await expect(page.locator(".hint-panel").getByText(/第三个参数.*相邻两项/)).toBeVisible();
  await captureGuideScreenshot("personalized-hint.png", page);

  await page.getByLabel("你的答案").fill("[2, 5, 8]");
  await page.getByRole("button", { name: "提交答案" }).click();
  await expect(page.getByText("[3, 7, 11, 15]", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "我需要一点提示" }).click();
  await page.getByLabel("你的答案").fill("range(3, 16, 4)");
  await page.getByRole("button", { name: "提交答案" }).click();
  await expect(page.locator(".completion").getByRole("heading", { name: "本次完成，仍需独立验证" })).toBeVisible();
  await captureGuideScreenshot("pending-verification.png", page);

  await page.getByRole("link", { name: "学习首页" }).click();
  await page.getByRole("button", { name: "开始迁移验证" }).click();
  await expect(page.getByText("[-2, 1, 4, 7]", { exact: true })).toBeVisible();
  await page.getByLabel("你的答案").fill("range(-2, 8, 3)");
  await page.getByRole("button", { name: "提交答案" }).click();
  await expect(page.locator(".completion").getByRole("heading", { name: "迁移验证已经通过" })).toBeVisible();

  await page.getByRole("button", { name: "查看证据链" }).click();
  await expect(page.getByRole("heading", { name: /掌握不是一次答对/ })).toBeVisible();
  await expect(page.getByText("迁移已验证", { exact: true }).first()).toBeVisible();
  await expect(page.getByText("使用 1 级提示后完成迁移任务。")).toBeVisible();
  await expect(page.getByText("无提示构造参数并生成目标序列。").first()).toBeVisible();
  await captureGuideScreenshot("evidence.png", page);
  expect(consoleErrors).toEqual([]);
});
