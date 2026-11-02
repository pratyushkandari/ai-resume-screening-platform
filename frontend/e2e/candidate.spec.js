// The candidate flow: browse open positions, apply, and the messages for rejected files.
import { expect, test } from "@playwright/test";
import { candidateState, expectToast, setupData, watchConsole } from "./helpers.js";

test.use({ storageState: candidateState });

test("a candidate applies to a position with a resume", async ({ page }) => {
  const data = setupData();
  const noConsoleErrors = watchConsole(page);
  await page.goto("/");
  const card = page.locator(".card", { has: page.getByRole("heading", { name: data.job.title }) });
  await card.getByRole("button", { name: "Apply for Position" }).click();
  await expect(page.getByLabel("Target Position")).toHaveValue(String(data.job.job_id));

  await page.locator('input[type="file"]').setInputFiles({
    name: "carl_candidate.txt",
    mimeType: "text/plain",
    buffer: Buffer.from("Carl Candidate\nPython developer who builds FastAPI services with PostgreSQL and Docker."),
  });
  await expect(page.getByText("carl_candidate.txt")).toBeVisible();
  await page.getByRole("main").getByRole("button", { name: "Submit Application" }).click();
  await expectToast(page, "Resume submitted.");
  await expect(page.getByRole("status").filter({ hasText: "carl_candidate.txt" })).toContainText("carl_candidate.txt: received (skills detected: docker, fastapi, postgresql, python)");
  noConsoleErrors();
});

test("files the app cannot read are rejected with a message", async ({ page }) => {
  const data = setupData();
  // The server's 400 for the fake PDF is logged by the browser as a failed resource.
  const noConsoleErrors = watchConsole(page, ["status of 400"]);
  await page.goto("/upload-resume");
  await page.getByLabel("Target Position").selectOption(String(data.job.job_id));

  await page.locator('input[type="file"]').setInputFiles({ name: "setup.exe", mimeType: "application/octet-stream", buffer: Buffer.from("MZ") });
  await expectToast(page, "1 file(s) were not accepted.");
  await expect(page.getByText("'setup.exe': unsupported format (.exe)")).toBeVisible();
  await expect(page.getByRole("main").getByRole("button", { name: "Submit Application" })).toBeDisabled();

  await page.locator('input[type="file"]').setInputFiles({ name: "cv.pdf", mimeType: "application/pdf", buffer: Buffer.from("plain text, not a PDF") });
  await page.getByRole("main").getByRole("button", { name: "Submit Application" }).click();
  await expectToast(page, "The file is not a valid PDF document.");
  noConsoleErrors();
});

test("candidates cannot open recruiter pages", async ({ page }) => {
  const noConsoleErrors = watchConsole(page);
  await page.goto("/upload-job");
  await expect(page).toHaveURL(/\/$/);
  await expect(page.getByRole("button", { name: "Apply for Position" }).first()).toBeVisible();
  await expect(page.getByRole("button", { name: "Evaluate Candidates" })).toHaveCount(0);
  noConsoleErrors();
});
