// The recruiter flow: dashboard numbers and charts, Evaluate, compare, view fit, download, post a job.
import { expect, test } from "@playwright/test";
import { expectToast, fetchSummary, openSetupJob, recruiterState, setupData, watchConsole } from "./helpers.js";

test.use({ storageState: recruiterState });

test("the dashboard shows the job's numbers and charts", async ({ page, request }) => {
  const data = setupData();
  const noConsoleErrors = watchConsole(page);
  await openSetupJob(page, data);
  const summary = await fetchSummary(request, data);
  const tileValue = (label) => page.locator(".stat-box", { has: page.getByText(label, { exact: true }) }).locator(".stat-value");
  await expect(tileValue("Total Applicants")).toHaveText(summary.total_candidates.toLocaleString("en-US"));
  await expect(tileValue("Shortlisted Candidates")).toHaveText(summary.shortlisted_candidates.toLocaleString("en-US"));
  await expect(tileValue("Average Match Score")).toHaveText(`${Math.round(summary.average_score * 100)}%`);
  await expect(page.getByRole("img", { name: /^Doughnut chart: / })).toHaveAttribute(
    "aria-label",
    `Doughnut chart: ${summary.strong_fits} strong fits (80% or more), ${summary.shortlisted_candidates - summary.strong_fits} other shortlisted, ${summary.total_candidates - summary.shortlisted_candidates} under review`
  );
  for (const name of [/^Bar chart/, /^Scatter chart/, /^Chart of which required skills/]) {
    await expect(page.getByRole("img", { name })).toBeVisible();
  }
  // Applicant cards follow the API's order: best score first.
  const names = summary.candidates.map((c) => c.candidate_name);
  await expect(page.getByRole("button", { name: /^Download resume of / })).toHaveCount(names.length);
  await expect(page.getByRole("button", { name: `Download resume of ${names[0]}` })).toBeVisible();
  noConsoleErrors();
});

test("Evaluate Candidates saves the rankings", async ({ page }) => {
  const data = setupData();
  const noConsoleErrors = watchConsole(page);
  await openSetupJob(page, data);
  await page.getByRole("button", { name: "Evaluate Candidates" }).click();
  await expectToast(page, "resumes and saved the rankings.");
  await expect(page.getByText(/Rankings saved /)).toBeVisible();
  noConsoleErrors();
});

test("two candidates can be compared and one candidate's fit opened", async ({ page, request }) => {
  const data = setupData();
  const noConsoleErrors = watchConsole(page);
  await openSetupJob(page, data);
  const [first, second] = (await fetchSummary(request, data)).candidates;
  const compareButtons = page.getByRole("button", { name: "+ Compare" });
  await compareButtons.nth(0).click();
  await compareButtons.nth(0).click(); // the first button now reads "Selected"
  await page.getByRole("button", { name: "Compare Profiles" }).click();
  const comparison = page.getByRole("dialog");
  await expect(comparison).toContainText("Comparative Candidate Analysis");
  await expect(comparison).toContainText(first.candidate_name);
  await expect(comparison).toContainText(second.candidate_name);
  await comparison.getByRole("button", { name: /Close/ }).click();
  await expect(page.getByRole("dialog")).toHaveCount(0);

  await page.getByRole("button", { name: "View Fit" }).first().click();
  await expect(page.getByRole("dialog")).toContainText(first.candidate_name);
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog")).toHaveCount(0);
  noConsoleErrors();
});

test("a recruiter downloads the original resume", async ({ page, request }) => {
  const data = setupData();
  const noConsoleErrors = watchConsole(page);
  await openSetupJob(page, data);
  // The best-ranked applicant uploaded by global-setup.js. Other tests add applicants to this
  // job too (candidate.spec.js), and close scores can rank theirs first on another machine.
  const candidates = (await fetchSummary(request, data)).candidates;
  const applicant = candidates.find((c) => data.applicants.some((a) => a.name === c.filename));
  const original = data.applicants.find((a) => a.name === applicant.filename);
  const [download] = await Promise.all([
    page.waitForEvent("download"),
    page.getByRole("button", { name: `Download resume of ${applicant.candidate_name}` }).click(),
  ]);
  expect(download.suggestedFilename()).toBe(applicant.filename);
  const chunks = [];
  for await (const chunk of await download.createReadStream()) chunks.push(chunk);
  expect(Buffer.concat(chunks).toString("utf-8")).toBe(original.text);
  noConsoleErrors();
});

test("posting a job validates the form and opens the new job", async ({ page }) => {
  const noConsoleErrors = watchConsole(page);
  await page.goto("/");
  await page.getByRole("button", { name: "Post Job" }).click();
  await expect(page).toHaveURL(/\/upload-job$/);

  const publish = page.getByRole("button", { name: "Publish Position" });
  await page.getByLabel(/Job Title/).fill("QA");
  await page.getByLabel(/Job Description/).fill("Run and improve our container platform on Kubernetes and PostgreSQL.");
  await expect(publish).toBeDisabled(); // titles need 3 to 120 characters
  await page.getByLabel(/Job Title/).fill("Site Reliability Engineer");
  await expect(publish).toBeEnabled();
  await publish.click();
  await expectToast(page, "Please specify at least one required skill (e.g. Python, Docker).");

  const skillInput = page.getByPlaceholder("Type competency and press Enter (e.g. PyTorch, Redis, Kubernetes)");
  await skillInput.fill("Python, k8s, Postgres");
  await skillInput.press("Enter");
  for (const skill of ["python", "k8s", "postgres"]) {
    await expect(page.getByRole("button", { name: `Remove ${skill}` })).toBeVisible();
  }
  await publish.click();
  await expectToast(page, "Position published successfully");
  await expect(page).toHaveURL(/\/$/);
  await expect(page.getByLabel("Select job requisition").locator("option:checked")).toContainText("Site Reliability Engineer");
  noConsoleErrors();
});
