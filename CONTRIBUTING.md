# Contributing

## Set up

See the [README quick start](README.md#quick-start-local-development). In short:

```bash
cd backend && python -m venv .venv && . .venv/bin/activate && pip install -r requirements-dev.txt
cd frontend && npm ci
```

## Before opening a pull request

```bash
cd backend && ruff check . && pytest -q -W error      # lint (incl. docstrings) + 165 tests
cd frontend && npm run lint && npm run build
```

CI runs the same commands, with the backend tests on both SQLite and PostgreSQL.

## Code standards

**Python (backend)**
* Every module, class and function has a docstring in
  [Google style](https://google.github.io/styleguide/pyguide.html#38-comments-and-docstrings)
  (`Args:`, `Returns:`, `Raises:` when they add information). `ruff` enforces this
  (`D` rules in `backend/ruff.toml`); individual `test_*` functions are exempt because
  their names describe the behaviour.
* Comments explain *why* (a constraint, a trade-off, a security reason), not what the
  next line does.
* Keep the layers: `routers/` handle HTTP (parsing, status codes, auth dependencies),
  `services/` hold business logic and transactions, `ml_utils.py` stays pure functions.
* Settings come only from `app/config.py`; never read `os.environ` elsewhere.
* Every recruiter endpoint uses `require_hr` **and** `get_owned_job`. Add the new route
  to the authorization matrix in `tests/test_rankings_api.py`.

**JavaScript (frontend)**
* Each component file starts with a JSDoc block: what it shows, where its data comes
  from, and its props (`@param`).
* All HTTP calls go through `src/api.js` (token, error messages, session expiry).
* Interactive elements must be keyboard-accessible and labelled; charts need an
  `aria-label`.

**Tests**
* A bug fix comes with a test that fails without the fix.
* Tests must be deterministic and offline: no real model, network or Redis
  (use `fake_model` and the `redis_server` fixture with fakeredis).

## Commits and branches

* Branch from `main`; one topic per branch (`fix/...`, `feat/...`, `docs/...`).
* Commit messages follow [Conventional Commits](https://www.conventionalcommits.org/):
  `feat(scope): ...`, `fix(scope): ...`, `docs: ...`, `test: ...`, `refactor: ...`,
  `build: ...`, `ci: ...`. Explain the reason in the body.
* Update `CHANGELOG.md` and the docs in `docs/` when behaviour, APIs or settings change.
* Never commit secrets: `.env` files are git-ignored; document new settings in
  `.env.example` with a safe placeholder.
