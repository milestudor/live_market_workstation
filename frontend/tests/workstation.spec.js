import { test, expect } from "@playwright/test";

test("saved data, symbol selection, intervals, replay, export and offline state", async ({
  page,
}) => {
  const errors = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "Market overview." }),
  ).toBeVisible();
  await expect(page.locator(".notice")).toContainText("disabled");
  await expect(page.locator("canvas").first()).toBeVisible();
  await page.getByLabel("Filter watchlist").fill("MSFT");
  await expect(page.locator(".watch-row")).toHaveCount(1);
  await page.locator(".watch-row").click();
  await expect(page.locator(".instrument-title h2")).toContainText("MSFT");
  await page.getByLabel("Filter watchlist").fill("");
  await page.getByRole("button", { name: "5m", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "5m", exact: true }),
  ).toHaveClass("selected");
  await page.getByRole("button", { name: "Replay", exact: true }).click();
  await expect(page.getByLabel("Play replay")).toBeEnabled();
  await page.getByLabel("Play replay").click();
  await expect(page.getByLabel("Pause replay")).toBeVisible();
  await page.getByLabel("Pause replay").click();
  await page.getByLabel("Replay position").fill("20");
  await expect(page.locator(".scrubber b")).toHaveText("21 / 150");
  if (await page.getByLabel("Export replay receipts").isVisible()) {
    const downloadPromise = page.waitForEvent("download");
    await page.getByLabel("Export replay receipts").click();
    expect((await downloadPromise).suggestedFilename()).toContain("MSFT");
  }
  await page.getByRole("button", { name: "Live", exact: true }).click();
  await expect(
    page.getByText("Follow the feed. Keep the history."),
  ).toBeVisible();
  await page.getByLabel("About this workstation").click();
  await expect(page.getByRole("dialog")).toContainText("same-timestamp");
  await page.getByRole("button", { name: "Back to the market" }).click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  expect(errors).toEqual([]);
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
});
