# Changelog

## Unreleased — audit fixes

### Security
- Recruiters can upload resumes only to jobs they created (403 otherwise), and their
  uploads no longer rename an existing applicant profile shared with other jobs.
- Uploads are rate limited per account: `UPLOAD_RATE_LIMIT_PER_MINUTE` (default 10;
  a batch counts once).
- `.env.example` no longer sets `APP_ENV=development` and `REQUIRE_EMBEDDING_MODEL=false`.
  Copied to `./.env` as the deployment guide says, they switched the Docker Compose
  production stack to development mode.

### Correctness
- File names with characters invalid on Windows returned 500, and long names lost
  their extension (and were rejected) or exceeded the 255-byte limit; names are now
  sanitized and capped in bytes.
- `last_ranked_at` carries a UTC offset on SQLite, so "Rankings saved" shows the right time.
- Pasting "Python, Docker, SQL" into the job's skill field created one unmatched skill;
  it now creates three tags.
- Uploads wait as long as Nginx (300 s) instead of timing out after 120 s while the
  server kept processing, which led users to upload the same resumes twice.
- Dashboard: real loading, error (with retry) and empty states; "Evaluating..." only
  during an evaluation; an evaluation cannot be started twice; compare selection is
  keyed by resume. Candidate page: loading and error states with retry.
- The comparison dialog's stylesheet no longer overrides the skill chips of the whole dashboard.
- The candidate-fit dialog no longer scrolls sideways on phones (its layout columns could
  not shrink below their content).

### Accessibility
- Visible keyboard focus on the sign-in inputs; contrast fixes (comparison Close
  button, "Skill Fit" value, comparison bar "Clear" hover); charts expose their labels
  (`role="img"`); labelled role toggle; "Apply for Position" moves focus to the form;
  Space on the upload drop zone no longer scrolls the page.

### Performance and maintenance
- Start-up skill de-duplication loads skill links only when something needs merging.
- Removed the unused `frontend/vercel.json`, the Chart.js `Title` plugin registration
  and an unused session field. README now documents the architecture, API and every setting.

### Upgrade notes
- If your `./.env` was copied from an older `.env.example`, delete the
  `APP_ENV=development` and `REQUIRE_EMBEDDING_MODEL=false` lines (or set production
  values) and restart the stack.

## 3.1.0 — second review: security, robustness and clean-up

### Security
- Login rate limit could be bypassed by sending a fake `X-Forwarded-For` header
  (Uvicorn trusted `*`, Nginx appended to the client's value). Nginx now overwrites
  the header and Uvicorn trusts only private-network proxies (`FORWARDED_ALLOW_IPS`).
- A candidate could attach resumes to, or rename, another applicant by putting that
  person's email in a document. Candidate uploads now belong to the signed-in account.
- Failed logins take the same time whether or not the email exists (dummy bcrypt check).
- Dependency floors raised past known advisories (pypdf, PyJWT, python-multipart,
  python-dotenv, Starlette/FastAPI, Uvicorn); frontend upgraded to Vite 6 and
  React Router 7 (`npm audit`: 0 vulnerabilities).

### Correctness
- Unexpected 500 errors now carry CORS and security headers (the browser previously
  showed a generic network error) and return the request ID.
- `sklearn` → scikit-learn alias never matched; "Go" opening a sentence ("Go beyond…")
  no longer counts as the Go language.
- Job text containing `<` (e.g. "<50k and >20k") is no longer partly deleted.
- UTF-16 `.txt` files, PDFs that only have an owner password, and contact details in
  DOCX headers/footers are now read.
- Two simultaneous "Evaluate" requests no longer fail with a unique-key error (job row lock).
- Files are deleted if saving a batch fails; tables are created later if the database
  was down at start-up (`/readyz` retries).
- Invalid numeric settings stop start-up with a clear message.
- Dashboard: a slow response for a previously selected job can no longer replace the
  current one; the comparison needs two candidates; radar charts use a fixed 0–1 scale;
  the quality chart follows the Shortlisted/Under review decision; the coverage chart
  no longer draws curves outside ✓/✕.
- Modal dialogs keep keyboard focus inside; contrast fixes; the Submit Application page
  has page padding.

### Maintainability
- Removed unused ORM relationships, redundant primary-key indexes, a wrapper function,
  unused CSS rules/variables and a dead UI branch; ORM indexes now match `sql/seed.sql`.
- Each role downloads only its own screens (one 524 kB bundle split; initial download 283 kB).
- Replaced the deprecated Redis `setex` call; tests now cover the Redis cache and rate
  limiter with fakeredis. 157 tests, run with warnings as errors.
- Docker Compose passes every documented setting; Kubernetes adds a hardened container
  security context; CI installs `requirements-dev.txt`; `deploy.ps1` stops on failures.

### Documentation
- Every Python module, class and function has a Google-style docstring, enforced by
  ruff's `D` rules in CI; comments explain the non-obvious decisions.
- Every React module starts with a JSDoc block (purpose, data flow, props).
- New `docs/DEPLOYMENT.md` (AWS EC2 + Docker Compose: instance, HTTPS, updates,
  backups, upgrade from version 2) and `CONTRIBUTING.md` (standards, tests, commits).
- `sql/seed.sql`, `vite.config.js` and the `Makefile` explain each part.

### Upgrade notes
- Frontend needs Node.js 20+. Run `npm ci` in `frontend` and
  `pip install -r requirements-dev.txt` in `backend`.
- Behind your own proxy, set `FORWARDED_ALLOW_IPS` to that proxy's address range.
- Servers running version 2 with Docker Compose (e.g. the AWS EC2 deployment): follow
  `docs/DEPLOYMENT.md` section 5. The old compose file published the database password
  and JWT secret in Git history, so rotate both, and copy `backend/uploads` into the
  new `uploads` volume.

## 3.0.0 — security, correctness and maintainability overhaul

### Security
- Every recruiter endpoint (`summary`, `rank`, `rankings`, resume `download`) now
  requires a recruiter token **and** ownership of the job. Client-supplied `role`,
  `user_id` and `created_by` values are ignored.
- Recruiter self-registration requires `HR_SIGNUP_CODE`; added `manage.py create-user`.
- Removed the "legacy plaintext" login path (a stored bcrypt hash could be used as a
  password and would overwrite the real one).
- Production refuses to start without a private `JWT_SECRET_KEY`; the previously
  published default secret is rejected. Tokens now use the standard `sub` claim and
  default to 60 minutes.
- Real rate limiting on login and registration (Redis or in-process).
- CORS allow-list instead of `*`; security headers on API responses; CSP on the SPA.
- Uploads: `.doc` dropped (could not be parsed), file-signature checks, batch size
  limit, internal error details no longer returned to clients.
- Resumes are downloaded with the auth header (blob) instead of a public link.

### Correctness
- One scoring implementation for the dashboard and saved rankings.
- Missing embeddings score a neutral 0.5 and are flagged (`semantic_available`)
  instead of using random vectors; **Evaluate** backfills them once the model loads.
- The embedding model loads in the background with retry back-off instead of being
  re-imported on every request; readiness can require it.
- Skill extraction: no more false matches for `R&D`, "let's go", `C-suite`;
  matches `C++17`, `python3`, hyphenated skills and common aliases (`k8s`, `Postgres`, `ReactJS`…).
- Contact parsing: international phone formats, Unicode names, skips "Curriculum Vitae"-style headings.
- TXT decoding order fixed (cp1252 before latin-1).
- `top_skills` is now scoped to the job; summary entries use one consistent resume per candidate.
- Resumes must target a job (unassigned resumes were never ranked).
- Works with SQLAlchemy 2.0 and 2.1 (`postgresql://` is mapped to psycopg2).

### Performance
- Constant number of queries for summaries and rankings (was ~3 per resume).
- Batch uploads embed all files in one model call; bcrypt runs off the event loop.

### Maintainability
- `main.py` split into `routers/` and `services/`; settings centralised in `config.py`.
- Removed dead code: unused rate-limit decorator, thread pool, schemas, imports,
  `verify_system.py`, `FileInput` component, `recharts` and `passlib`/`aiofiles` dependencies.
- Shared frontend helpers (`session.js`, `theme.js`, `Modal`, `useUpload` with real upload progress).
- ESLint for the frontend, ruff in CI, CI runs tests on SQLite and PostgreSQL.
- Idempotent `sql/seed.sql`, multi-stage Docker image with the model baked in,
  Nginx upload limits, Kubernetes shared upload volume, honest documentation.
- Test suite rewritten: 129 tests including an authorization matrix and a
  query-count regression test.

### Upgrade notes
- Existing sessions are invalidated (new token format): users sign in again.
- Set `JWT_SECRET_KEY` and (optionally) `HR_SIGNUP_CODE`; see `.env.example`.
- Existing databases need no changes. Absolute `upload_path` values written by older
  versions keep working; case-duplicate skills are merged at start-up.
- Accounts whose password was stored in plaintext must be reset with `manage.py reset-password`.
