# Testing

Every suite, what it covers, how to run it and its latest results.

| Suite | Location | Command | Needs | In CI |
|---|---|---|---|---|
| Backend unit and integration | `backend/tests/` | `make test` | nothing (SQLite in memory, no network) | `backend` job, SQLite and PostgreSQL |
| Backend coverage | `backend/tests/` | `make coverage` | as above | reports kept as artifacts |
| API end-to-end | `backend/e2e/` | `make e2e` | a running Docker Compose stack | `e2e` job |
| Browser end-to-end (Playwright) | `frontend/e2e/` | `make e2e-browser` | a running stack and Chromium | `e2e` job |
| Lint and build | | `make lint`, `make build` | | `backend` and `frontend` jobs |
| Ranking evaluation | `backend/evaluation/` | `make eval` | the embedding model (about 90 MB download) | no; results are in the README |
| Load test | `loadtest/dashboard.js` | see the README | a stack seeded with 10,000 resumes, Docker for k6 | no |

## Backend unit and integration tests

`cd backend && pytest -q` runs `backend/tests/` (`pytest.ini` limits the default run to that
folder). The tests call the app in-process with FastAPI's test client, on an in-memory SQLite
database (or `TEST_DATABASE_URL`), with a temporary upload folder, a bag-of-words stand-in
for the embedding model and an unreachable Redis (fakeredis where Redis behaviour is
tested). Nothing touches the network or real data, and the suite takes about 25 seconds.

They cover:

- **Auth:** password rules, bcrypt, JWTs (expired, tampered, wrong subject, deleted user),
  registration and sign-in rules, malformed request bodies, the recruiter access code and
  the sign-in rate limit.
- **Authorization:** a matrix of every recruiter endpoint for anonymous callers, candidates,
  other recruiters and the owner.
- **Jobs:** validation, skill parsing, pagination, ownership.
- **Uploads:** file types and signatures, size and batch limits, empty, corrupt,
  password-protected and image-only files, unusual file names, applicant identity rules,
  rate limits, a resume that fails to save inside a batch, and downloads (missing file,
  paths outside the upload folder).
- **Parsing:** PDF, DOCX (headers, footers, tables), TXT encodings, contacts, skill aliases
  and the "Go" language.
- **Ranking:** the formula against a plain reference implementation, stored semantic
  scores, the summary totals, tie order, constant query counts.
- **Operations:** health and readiness (including the database being down), metrics,
  request IDs, security headers, CORS, settings validation, the Redis cache and rate-limit
  fallbacks.
- **Tools:** the `manage.py` commands and the evaluation script.

Coverage settings are in `backend/.coveragerc`. Every backend source file is measured,
including the command-line tools, so a module without tests shows up as 0%.

## API end-to-end tests

`backend/e2e/` runs against a real stack over HTTP, through Nginx, with PostgreSQL, Redis
and the real MiniLM model. Each run registers its own accounts (unique emails), so it can
run again against the same database.

- **Jobs:** validation messages, pasted comma-separated skills, who may create jobs,
  public and own job lists.
- **Uploads:** the 50 evaluation resumes for each of the 5 evaluation jobs (TXT, PDF and
  DOCX, in batches of 25). Also a candidate uploading twice, seven kinds of bad file, a
  password-protected PDF, unusual file names and the batch file limit.
- **Ranking:** every resume parsed and ranked with semantic scores. Live NDCG@10 and
  Precision@5 within 0.03 of the offline evaluation (0.930 and 0.960). Keyword-stuffed
  resumes out of every top 5, dashboard totals, saved rankings in dashboard order, and
  downloads returning the uploaded bytes.
- **Access:** candidates, other recruiters, anonymous callers and invalid tokens on every
  recruiter endpoint; sign-in.
- **Rate limits:** the 11th upload and the 11th failed sign-in in a minute get 429. These
  tests wait for the start of a new minute, so a minute boundary cannot reset the count.

## Browser end-to-end tests

`frontend/e2e/` uses Playwright with Chromium. `global-setup.js` creates a recruiter with a
job, three applicants and a saved ranking, and a candidate, through the API, then saves
both sessions so tests start signed in. Signing in through the form in every test would hit
the sign-in limit of 10 per minute per IP. It then waits for a new minute before the tests
start. Every test fails on a console error, apart from the 401 or 400 responses a test
causes on purpose.

- **Sign-in and accounts:** sign in and out as a recruiter; the wrong-password,
  invalid-email and empty-field messages; candidate registration with the password
  strength check; the recruiter access code prompt; an expired session returning to the
  sign-in screen.
- **Candidate:** apply to a position with a resume and see the detected skills; the
  messages for a file type the browser rejects and for a file the server rejects;
  recruiter pages are not reachable.
- **Recruiter:** dashboard numbers and the doughnut chart against the API; all four
  charts; card order; Evaluate; the comparison and fit dialogs; downloading the original
  file; posting a job (disabled button for a short title, the missing-skills message,
  pasted skills becoming tags, the new job opening on the dashboard).
- **Layout:** every page at 1280, 768 and 375 pixels wide without sideways scrolling or
  console errors.

## Running the end-to-end suites

```bash
cp .env.example .env               # set POSTGRES_PASSWORD, JWT_SECRET_KEY and HR_SIGNUP_CODE
docker compose up -d --build       # wait until http://localhost/readyz reports "ready"
export E2E_BASE_URL=http://localhost
export E2E_HR_SIGNUP_CODE=<HR_SIGNUP_CODE from .env>
make e2e
cd frontend && npx playwright install chromium && cd ..    # once
make e2e-browser
```

Run them against a local or CI stack only, never a shared or production deployment: they
create accounts, jobs and resumes, and the rate-limit tests block sign-in from your
address for a minute. The suites expect the default rate limits from `docker-compose.yml`.
Playwright keeps an HTML report in `frontend/playwright-report/` and, for failed tests,
a trace and a screenshot in `frontend/test-results/`.

## Latest results

Commit `5000dba` (branch `test-docs-audit`), 2026-11-03, Windows 11 with Docker Desktop.
The stack was started from empty volumes.

| Suite | Result |
|---|---|
| Backend tests, SQLite | 227 passed in 24 s |
| Backend tests, PostgreSQL 15 | 227 passed in 26 s |
| Backend branch coverage | 97% (1,773 statements, 47 missed; 416 branches, 13 partial) |
| ruff, ESLint, production build | pass |
| API end-to-end | 34 passed in 175 s |
| Browser end-to-end | 28 passed in 1.6 min |

Before this work the backend had 180 tests at 82% branch coverage, measured the same way.
There were no end-to-end or browser tests.

## Not covered by automated tests

- **`benchmark_scoring.py`:** a micro-benchmark that only prints timings.
- **Loading the real embedding model:** the unit tests use a stand-in model. The
  end-to-end suites run with the real one.
- **PDFs whose decryption itself fails:** the unit tests cover owner-password-only and
  user-password PDFs, not one where decryption raises.
- **Lines after an `await` in async routes:** coverage marks some as missed even though
  the tests exercise them. For example, the "Request body must be an object." response is
  asserted in `tests/test_auth.py`, but the line that raises it shows as missed.
- **The frontend's components and pure functions:** there are no unit tests; the browser
  tests cover them through the UI.
- **Chart drawing:** the tests check the data behind each chart (labels and counts), not
  the pixels drawn.
- **Kubernetes and Render manifests:** `k8s/`, `render.yaml`.

## Manual checks

These are not automated. Run them before a release, or after a change to the area.

1. **Other browsers and real phones.** Playwright runs Chromium only. On Firefox, Safari
   on an iPhone and Chrome on an Android phone:
   1. Sign in as a recruiter and open a job with applicants.
   2. Check that the four charts draw, the cards stack, and the page does not scroll
      sideways.
   3. Sign in as a candidate and upload a resume with the phone's own file picker.
2. **Drag and drop and the system file dialog.** The browser tests set files on the file
   input directly. On the upload page:
   1. Drag a PDF onto the drop zone.
   2. Open the file dialog with the keyboard (Tab to the drop zone, then Enter) and pick a
      DOCX.
   3. Submit both and check that they are listed as received.
3. **Screen reader.** With NVDA (Windows) or VoiceOver (macOS):
   1. Sign in.
   2. On the dashboard, check that each chart's description is read out and that the job
      selector, Evaluate, Compare and Download are announced with their names.
   3. Open and close the comparison dialog with the keyboard.
4. **Production after a deploy.** Do not run the test suites against production.
   1. Open `/readyz` and check that it reports `"ready"` with `"ml_model": "active"`.
   2. Sign in with a real recruiter account and open a job.
   3. Click Evaluate Candidates and check that "Rankings saved" shows the current time.
5. **Ranking quality after a scoring change.** Run `make eval` and compare the table with
   the one in the README.
6. **Load after a change to the dashboard query.** Seed 10,000 resumes and run the k6
   test as described in the README. Compare p50, p95 and response size with the README.
