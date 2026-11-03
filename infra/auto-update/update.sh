#!/usr/bin/env bash
# Deploy the newest commit on GitHub once its CI has passed. A systemd timer runs this as root
# every 5 minutes (see install.sh); it is also safe to run by hand:
#   sudo bash infra/auto-update/update.sh
#
# It does nothing while the server is on the latest commit, while CI on a new commit is still
# running, or for a commit whose CI failed. Otherwise it fast-forwards the checkout, rebuilds the
# images (Docker reuses unchanged layers), restarts the stack and waits for /readyz. If a step
# fails, it goes back to the previous commit and images and skips the failed commit until a
# newer one arrives.
set -euo pipefail

APP_DIR="${APP_DIR:-/home/ubuntu/ai-resume-screening-platform}"
APP_USER="${APP_USER:-ubuntu}"
BRANCH="${BRANCH:-main}"
READY_URL="${READY_URL:-http://localhost/readyz}"
READY_ATTEMPTS="${READY_ATTEMPTS:-60}"   # 5 s apart: the embedding model takes a minute or two to load
STATE_DIR="${STATE_DIR:-/var/lib/talentflow-update}"
LOCK_FILE="${LOCK_FILE:-/run/talentflow-update.lock}"

# The checkout belongs to the app user, and git refuses to work in it as root.
as_app() { runuser -u "$APP_USER" -- "$@"; }

short() { echo "${1:0:7}"; }

wait_ready() {
  for _ in $(seq 1 "$READY_ATTEMPTS"); do
    curl -fsS "$READY_URL" > /dev/null 2>&1 && return 0
    sleep 5
  done
  return 1
}

github_repo() {
  if [ -n "${GITHUB_REPO:-}" ]; then
    echo "$GITHUB_REPO"
  else
    as_app git remote get-url origin | sed -E 's#^.*github\.com[:/]##; s#\.git$##'
  fi
}

# Prints success, pending or failure for the GitHub check runs of a commit. The repository is
# public, so no token is needed; if GitHub cannot be reached, the answer is pending.
ci_result() {
  curl -fsS -H "Accept: application/vnd.github+json" \
    "https://api.github.com/repos/$(github_repo)/commits/$1/check-runs?per_page=100" 2>/dev/null |
    python3 -c '
import json, sys
runs = json.load(sys.stdin)["check_runs"]
if not runs or any(r["status"] != "completed" for r in runs):
    print("pending")
elif all(r["conclusion"] in ("success", "skipped", "neutral") for r in runs):
    print("success")
else:
    print("failure")' 2>/dev/null || echo pending
}

# Image IDs and names of the running backend and frontend, so a failed update can go back to them.
declare -A previous_id=() previous_name=()

remember_images() {
  local service container
  for service in backend frontend; do
    container=$(docker compose ps -q "$service")
    [ -n "$container" ] || continue
    previous_id[$service]=$(docker inspect --format '{{.Image}}' "$container")
    previous_name[$service]=$(docker inspect --format '{{.Config.Image}}' "$container")
  done
}

restore_images() {
  local service
  for service in "${!previous_id[@]}"; do
    docker tag "${previous_id[$service]}" "${previous_name[$service]}"
  done
}

deploy() {
  local from=$1 to=$2
  echo "Deploying $(short "$to") (running $(short "$from"))."
  remember_images
  as_app git merge --ff-only --quiet "$to"
  if nice -n 10 docker compose build && docker compose up -d && wait_ready; then
    docker image prune -f > /dev/null
    rm -f "$STATE_DIR/failed-commit"
    echo "Deployed $(short "$to")."
    return 0
  fi
  echo "Could not deploy $(short "$to"); going back to $(short "$from")." >&2
  docker compose logs --tail 40 backend >&2 || true
  as_app git reset --hard --quiet "$from"
  restore_images
  docker compose up -d || true
  wait_ready || echo "The previous version is not ready either; check: docker compose logs" >&2
  echo "$to" > "$STATE_DIR/failed-commit"
  return 1
}

main() {
  mkdir -p "$STATE_DIR"
  exec 9> "$LOCK_FILE"
  if ! flock -n 9; then
    echo "Another update is running."
    return 0
  fi
  cd "$APP_DIR"

  as_app git fetch --quiet origin "$BRANCH"
  local current target
  current=$(as_app git rev-parse HEAD)
  target=$(as_app git rev-parse "origin/$BRANCH")
  [ "$current" != "$target" ] || return 0
  [ "$(cat "$STATE_DIR/failed-commit" 2>/dev/null)" != "$target" ] || return 0

  if [ -n "$(as_app git status --porcelain --untracked-files=no)" ]; then
    echo "Files in $APP_DIR were changed on the server; not updating. See: git status" >&2
    return 1
  fi
  if ! as_app git merge-base --is-ancestor HEAD "$target"; then
    echo "$(short "$target") does not follow the checked-out commit; not updating." >&2
    return 1
  fi

  case "$(ci_result "$target")" in
    pending)
      echo "Waiting for CI on $(short "$target")."
      return 0
      ;;
    failure)
      echo "CI failed on $(short "$target"); not deploying it."
      echo "$target" > "$STATE_DIR/failed-commit"
      return 0
      ;;
  esac
  deploy "$current" "$target"
}

# Called last, so bash has read the whole file before the checkout (and this file) changes.
main "$@"
