// Prepares the stack for the browser tests: a recruiter with a job, three applicants and a
// saved ranking, and a candidate account. Both sessions are written to e2e/.auth so tests
// start signed in; signing in through the form in every test would hit the login rate limit.
import { mkdirSync, writeFileSync } from "node:fs";
import { randomUUID } from "node:crypto";

const AUTH_DIR = new URL("./.auth/", import.meta.url);
export const PASSWORD = "E2e!Passw0rd-2026";

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

/** fetch() against the stack that waits out 429 responses, like a patient user. */
async function call(baseURL, path, options = {}) {
  for (;;) {
    const response = await fetch(new URL(path, baseURL), options);
    if (response.status !== 429) return response;
    await sleep((Number(response.headers.get("retry-after")) || 5) * 1000 + 1000);
  }
}

async function expectStatus(response, status) {
  if (response.status !== status) {
    throw new Error(`${response.url} returned ${response.status}: ${await response.text()}`);
  }
  return response.json();
}

async function register(baseURL, body) {
  const response = await call(baseURL, "/api/register", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ password: PASSWORD, ...body }),
  });
  const data = await expectStatus(response, 201);
  return { email: body.email, name: body.name, token: data.access_token, role: data.role };
}

/** Playwright storage state that holds the app's session, as session.js stores it. */
function storageState(baseURL, user) {
  const session = { token: user.token, role: user.role, name: user.name };
  return { cookies: [], origins: [{ origin: new URL(baseURL).origin, localStorage: [{ name: "session", value: JSON.stringify(session) }] }] };
}

export default async function globalSetup(config) {
  const { baseURL } = config.projects[0].use;
  const hrCode = process.env.E2E_HR_SIGNUP_CODE;
  if (!hrCode) throw new Error("Set E2E_HR_SIGNUP_CODE to the stack's HR_SIGNUP_CODE.");
  const ready = await fetch(new URL("/readyz", baseURL)).catch((error) => error);
  if (!(ready instanceof Response) || ready.status !== 200) {
    throw new Error(`No ready stack at ${baseURL}. Start it with "docker compose up -d --build" and set E2E_BASE_URL.`);
  }

  const run = randomUUID().slice(0, 8);
  const recruiter = await register(baseURL, { name: "Rita Recruiter", email: `rita.${run}@example.com`, role: "hr", access_code: hrCode });
  const candidate = await register(baseURL, { name: "Carl Candidate", email: `carl.${run}@example.com`, role: "candidate" });
  const auth = { Authorization: `Bearer ${recruiter.token}` };

  const jobForm = new FormData();
  jobForm.set("title", `Platform Engineer ${run}`);
  jobForm.set("description", "Build Python APIs with FastAPI, PostgreSQL and Redis, shipped in Docker containers.");
  jobForm.set("skills", "python, fastapi, postgresql, docker");
  const job = await expectStatus(await call(baseURL, "/api/jobs", { method: "POST", headers: auth, body: jobForm }), 201);

  const applicants = [
    ["ana_lima.txt", `Ana Lima\nana.${run}@example.com\nSenior Python engineer. Built FastAPI services on PostgreSQL and Redis, deployed with Docker.`],
    ["ben_okoro.txt", `Ben Okoro\nben.${run}@example.com\nBackend developer using Python and Django with PostgreSQL databases.`],
    ["chloe_martin.txt", `Chloe Martin\nchloe.${run}@example.com\nGraphic designer working in Figma and Illustrator on brand identity.`],
  ];
  const batch = new FormData();
  batch.set("job_id", String(job.job_id));
  for (const [name, text] of applicants) batch.append("files", new Blob([text], { type: "text/plain" }), name);
  const uploaded = await expectStatus(await call(baseURL, "/api/resumes/batch-upload", { method: "POST", headers: auth, body: batch }), 200);
  if (uploaded.successful !== applicants.length) throw new Error(`Setup uploads failed: ${JSON.stringify(uploaded.results)}`);
  await expectStatus(await call(baseURL, `/api/jobs/${job.job_id}/rank`, { method: "POST", headers: auth }), 200);

  mkdirSync(AUTH_DIR, { recursive: true });
  writeFileSync(new URL("recruiter.json", AUTH_DIR), JSON.stringify(storageState(baseURL, recruiter)));
  writeFileSync(new URL("candidate.json", AUTH_DIR), JSON.stringify(storageState(baseURL, candidate)));
  writeFileSync(new URL("data.json", AUTH_DIR), JSON.stringify({ run, job, recruiter, candidate, applicants: applicants.map(([name, text]) => ({ name, text })) }));

  // Sign-in and registration are limited per minute and per IP. Start the tests in a fresh
  // minute so the form tests are not blocked by the requests above or an earlier suite.
  await sleep(60_000 - (Date.now() % 60_000) + 500);
}
