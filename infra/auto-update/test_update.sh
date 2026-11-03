#!/usr/bin/env bash
# "check && pass || fail" below is safe because pass only echoes.
# shellcheck disable=SC2015
# Tests for update.sh. docker, curl, runuser and sleep are replaced by stubs that record their
# calls, and the server checkout is a throwaway git repository, so no server, Docker or network
# is needed:  bash infra/auto-update/test_update.sh
set -euo pipefail

here=$(cd "$(dirname "$0")" && pwd)
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
export CALLS="$work/calls" CHECK_RUNS="$work/check-runs.json"
export GIT_AUTHOR_NAME=Test GIT_AUTHOR_EMAIL=test@example.com GIT_COMMITTER_NAME=Test GIT_COMMITTER_EMAIL=test@example.com

mkdir "$work/bin"
cat > "$work/bin/docker" << 'EOF'
#!/usr/bin/env bash
echo "docker $*" >> "$CALLS"
case "$*" in
  "compose ps -q "*) echo "container-$4" ;;
  "inspect --format {{.Image}} "*) echo "sha256:${4#container-}-old" ;;
  "inspect --format {{.Config.Image}} "*) echo "talentflow-${4#container-}" ;;
  "compose build") [ "${BUILD_FAILS:-0}" = 0 ] || exit 1 ;;
esac
exit 0
EOF
cat > "$work/bin/curl" << 'EOF'
#!/usr/bin/env bash
echo "curl $*" >> "$CALLS"
case "$*" in
  *api.github.com*) cat "$CHECK_RUNS" ;;
  *readyz*) exit "${READY_EXIT:-0}" ;;
esac
EOF
cat > "$work/bin/runuser" << 'EOF'
#!/usr/bin/env bash
while [ "$1" != "--" ]; do shift; done
shift
exec "$@"
EOF
printf '#!/usr/bin/env bash\n' > "$work/bin/sleep"
chmod +x "$work/bin/"*

new_server() {  # an origin repository and a server checkout of it, both at one commit
  rm -rf "${work:?}/origin.git" "${work:?}/app" "${work:?}/state"
  git init -q --bare -b main "$work/origin.git"
  git clone -q "$work/origin.git" "$work/app" 2> /dev/null
  echo one > "$work/app/file.txt"
  git -C "$work/app" add file.txt
  git -C "$work/app" commit -q -m one
  git -C "$work/app" push -q origin main
  git -C "$work/app" rev-parse HEAD
}

push_commit() {  # a newer commit on origin that the server has not fetched yet
  rm -rf "${work:?}/dev"
  git clone -q "$work/origin.git" "$work/dev"
  echo "$1" > "$work/dev/file.txt"
  git -C "$work/dev" commit -q -am "$1"
  git -C "$work/dev" push -q origin main
  git -C "$work/dev" rev-parse HEAD
}

check_runs() { printf '{"check_runs": [%s]}' "$1" > "$CHECK_RUNS"; }
PASSED='{"status": "completed", "conclusion": "success"}'

run_update() {
  : > "$CALLS"
  APP_DIR="$work/app" APP_USER="$(id -un)" STATE_DIR="$work/state" LOCK_FILE="$work/lock" \
    READY_ATTEMPTS=2 GITHUB_REPO=owner/repo PATH="$work/bin:$PATH" bash "$here/update.sh" > "$work/out" 2>&1
}

head_is() { [ "$(git -C "$work/app" rev-parse HEAD)" = "$1" ]; }
called() { grep -qF -- "$1" "$CALLS"; }
failed_commit_is() { [ "$(cat "$work/state/failed-commit" 2> /dev/null)" = "$1" ]; }
pass() { echo "ok - $1"; }
fail() { echo "not ok - $1"; cat "$work/out"; exit 1; }

start=$(new_server)
run_update || fail "up to date: exits 0"
[ ! -s "$CALLS" ] && pass "up to date: no GitHub or Docker calls" || fail "up to date: no calls"

target=$(push_commit two)
check_runs '{"status": "in_progress", "conclusion": null}'
run_update || fail "CI running: exits 0"
head_is "$start" && ! called "docker compose build" && pass "CI running: waits" || fail "CI running: waits"

check_runs ""
run_update || fail "no CI runs yet: exits 0"
head_is "$start" && pass "no CI runs yet: waits" || fail "no CI runs yet: waits"

check_runs "$PASSED, "'{"status": "completed", "conclusion": "failure"}'
run_update || fail "CI failed: exits 0"
head_is "$start" && failed_commit_is "$target" && pass "CI failed: not deployed, remembered" || fail "CI failed: not deployed"
run_update || fail "CI failed again: exits 0"
! called "api.github.com" && pass "CI failed: later runs skip the commit without asking GitHub" || fail "CI failed: skipped"

start=$(new_server)
target=$(push_commit two)
check_runs "$PASSED, $PASSED"
run_update || fail "CI passed: exits 0"
head_is "$target" && called "docker compose build" && called "docker compose up -d" && called "docker image prune -f" &&
  pass "CI passed: checkout, build, restart and clean-up" || fail "CI passed: deployed"
[ ! -e "$work/state/failed-commit" ] && pass "CI passed: no failed commit recorded" || fail "CI passed: state"

start=$(new_server)
target=$(push_commit two)
check_runs "$PASSED"
if READY_EXIT=22 run_update; then fail "never ready: exits 1"; fi
head_is "$start" && called "docker tag sha256:backend-old talentflow-backend" && called "docker tag sha256:frontend-old talentflow-frontend" &&
  failed_commit_is "$target" && pass "never ready: back to the previous commit and images" || fail "never ready: rolled back"

start=$(new_server)
target=$(push_commit two)
if BUILD_FAILS=1 run_update; then fail "build fails: exits 1"; fi
head_is "$start" && failed_commit_is "$target" && pass "build fails: back to the previous commit" || fail "build fails: rolled back"

start=$(new_server)
push_commit two > /dev/null
echo "edited on the server" >> "$work/app/file.txt"
if run_update; then fail "local edits: exits 1"; fi
head_is "$start" && ! called "docker compose build" && pass "local edits: not updated" || fail "local edits: not updated"

echo "All update.sh tests passed."
