// Every page loads without console errors and without sideways scrolling on desktop, tablet and phone.
import { expect, test } from "@playwright/test";
import { candidateState, recruiterState, setupData, watchConsole } from "./helpers.js";

const VIEWPORTS = { desktop: { width: 1280, height: 800 }, tablet: { width: 768, height: 1024 }, phone: { width: 375, height: 812 } };

const PAGES = [
  { name: "sign-in", state: undefined, path: "/", ready: (page) => page.getByRole("heading", { name: "Sign In to TalentFlow" }) },
  { name: "candidate positions", state: candidateState, path: "/", ready: (page) => page.getByRole("button", { name: "Apply for Position" }).first() },
  { name: "candidate upload", state: candidateState, path: "/upload-resume", ready: (page) => page.getByRole("main").getByRole("button", { name: "Submit Application" }) },
  { name: "recruiter dashboard", state: recruiterState, path: "/", ready: (page) => page.getByRole("img", { name: /^Doughnut chart/ }) },
  { name: "post job", state: recruiterState, path: "/upload-job", ready: (page) => page.getByRole("button", { name: "Publish Position" }) },
];

for (const [viewportName, viewport] of Object.entries(VIEWPORTS)) {
  for (const target of PAGES) {
    test.describe(() => {
      test.use({ viewport, storageState: target.state ?? { cookies: [], origins: [] } });

      test(`${target.name} on ${viewportName}`, async ({ page }) => {
        const data = setupData();
        const noConsoleErrors = watchConsole(page);
        await page.goto(target.path);
        if (target.name === "recruiter dashboard") {
          await page.getByLabel("Select job requisition").selectOption(String(data.job.job_id));
        }
        await expect(target.ready(page)).toBeVisible();
        const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
        expect(overflow).toBeLessThanOrEqual(0);
        noConsoleErrors();
      });
    });
  }
}
