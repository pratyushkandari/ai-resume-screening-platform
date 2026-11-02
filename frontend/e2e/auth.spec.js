// Sign-in, registration, sign-out and an expired session, through the real form.
import { randomUUID } from "node:crypto";
import { expect, test } from "@playwright/test";
import { PASSWORD, setupData, watchConsole } from "./helpers.js";

const signInHeading = (page) => page.getByRole("heading", { name: "Sign In to TalentFlow" });

test("a recruiter signs in, lands on the dashboard and signs out", async ({ page }) => {
  const data = setupData();
  const noConsoleErrors = watchConsole(page);
  await page.goto("/");
  await expect(signInHeading(page)).toBeVisible();
  await page.getByLabel("Email Address").fill(data.recruiter.email);
  await page.getByLabel("Password", { exact: true }).fill(PASSWORD);
  await page.getByRole("button", { name: "Sign In" }).click();
  await expect(page.getByRole("heading", { name: "Candidate Evaluation & Rankings" })).toBeVisible();
  await page.getByRole("button", { name: "Sign Out" }).click();
  await expect(signInHeading(page)).toBeVisible();
  noConsoleErrors();
});

test("a wrong password and an invalid email show messages", async ({ page }) => {
  const data = setupData();
  // The rejected sign-in is a 401 response, which the browser logs as a failed resource.
  const noConsoleErrors = watchConsole(page, ["status of 401"]);
  await page.goto("/");
  await page.getByLabel("Email Address").fill("not-an-email");
  await page.getByLabel("Password", { exact: true }).fill(PASSWORD);
  await page.getByRole("button", { name: "Sign In" }).click();
  await expect(page.getByRole("alert")).toHaveText("Please enter a valid email address.");
  await page.getByLabel("Email Address").fill(data.candidate.email);
  await page.getByLabel("Password", { exact: true }).fill("Wr0ng!Password");
  await page.getByRole("button", { name: "Sign In" }).click();
  await expect(page.getByRole("alert")).toHaveText("Invalid email or password.");
  await page.getByLabel("Email Address").fill("");
  await page.getByRole("button", { name: "Sign In" }).click();
  await expect(page.getByRole("alert")).toHaveText("Please complete all required fields.");
  noConsoleErrors();
});

test("a candidate registers and sees the open positions", async ({ page }) => {
  const noConsoleErrors = watchConsole(page);
  await page.goto("/");
  await page.getByRole("button", { name: "Register Now" }).click();
  await expect(page.getByRole("heading", { name: "Create Your Account" })).toBeVisible();
  await page.getByLabel("Full Name").fill("Dana Newcomer");
  await page.getByLabel("Email Address").fill(`dana.${randomUUID().slice(0, 8)}@example.com`);
  await page.getByLabel("Password", { exact: true }).fill("weak");
  await expect(page.getByText("Weak")).toBeVisible();
  await page.getByRole("button", { name: "Create Account" }).click();
  await expect(page.getByRole("alert")).toHaveText("Password must meet all complexity requirements.");
  await page.getByLabel("Password", { exact: true }).fill(PASSWORD);
  await page.getByRole("button", { name: "Create Account" }).click();
  await expect(page.getByRole("button", { name: "Apply for Position" }).first()).toBeVisible();
  await expect(page.getByText("Dana Newcomer")).toBeVisible();
  noConsoleErrors();
});

test("recruiter registration asks for the access code", async ({ page }) => {
  const noConsoleErrors = watchConsole(page);
  await page.goto("/");
  await page.getByRole("button", { name: "Register Now" }).click();
  await page.getByRole("button", { name: "Recruiter / HR" }).click();
  await expect(page.getByLabel("Recruiter Access Code")).toBeVisible();
  await page.getByLabel("Full Name").fill("Rex Recruiter");
  await page.getByLabel("Email Address").fill(`rex.${randomUUID().slice(0, 8)}@example.com`);
  await page.getByLabel("Password", { exact: true }).fill(PASSWORD);
  await page.getByRole("button", { name: "Create Account" }).click();
  await expect(page.getByRole("alert")).toHaveText("Recruiter accounts need the access code provided by your administrator.");
  noConsoleErrors();
});

test("an expired session returns to the sign-in screen", async ({ page }) => {
  // The API answers the stale token with 401, which the browser logs as a failed resource.
  const noConsoleErrors = watchConsole(page, ["status of 401"]);
  await page.addInitScript(() => {
    localStorage.setItem("session", JSON.stringify({ token: "expired.token.value", role: "hr", name: "Old Session" }));
  });
  await page.goto("/");
  await expect(signInHeading(page)).toBeVisible();
  expect(await page.evaluate(() => localStorage.getItem("session"))).toBeNull();
  noConsoleErrors();
});
