// Shared helpers for the browser tests.
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { expect } from "@playwright/test";

export { PASSWORD } from "./global-setup.js";

/** Accounts, job and applicants created by global-setup.js. */
export function setupData() {
  return JSON.parse(readFileSync(new URL("./.auth/data.json", import.meta.url), "utf-8"));
}

export const recruiterState = fileURLToPath(new URL("./.auth/recruiter.json", import.meta.url));
export const candidateState = fileURLToPath(new URL("./.auth/candidate.json", import.meta.url));

/**
 * Collect console errors and uncaught exceptions; call the returned function at the end of
 * a test to assert there were none. `allowed` lists substrings of errors a test expects.
 */
export function watchConsole(page, allowed = []) {
  const errors = [];
  page.on("console", (message) => {
    if (message.type() === "error") errors.push(message.text());
  });
  page.on("pageerror", (error) => errors.push(error.message));
  return () => expect(errors.filter((text) => !allowed.some((a) => text.includes(a)))).toEqual([]);
}

/** Wait for the toast that contains `text` (react-toastify renders them with role="alert"). */
export async function expectToast(page, text) {
  await expect(page.getByRole("alert").filter({ hasText: text }).first()).toBeVisible();
}

/** The dashboard summary for the setup job, read through the API with the recruiter's token. */
export async function fetchSummary(request, data) {
  const response = await request.get(`/api/jobs/${data.job.job_id}/summary`, {
    headers: { Authorization: `Bearer ${data.recruiter.token}` },
  });
  expect(response.status()).toBe(200);
  return response.json();
}

/** Select the setup job in the dashboard's job selector and wait for its charts. */
export async function openSetupJob(page, data) {
  await page.goto("/");
  await page.getByLabel("Select job requisition").selectOption(String(data.job.job_id));
  await expect(page.locator("canvas")).toHaveCount(4);
}
