#!/bin/bash
# weekly.sh -- recompute every number this repository claims, then publish the diff.
#
# WHY IT EXISTS: a README with hand-typed numbers starts lying within a week and nobody can
# tell when it started. So the numbers are recomputed on a schedule by a machine, and the
# commit history becomes the audit trail of what changed and when.
#
# WHERE IT RUNS: one node of the fleet, unattended, once a week. It needs nothing but git,
# python3 and a logged-in `gh`.
#
# OUTPUT (this is the routine's mouth -- a routine with no named output is unverifiable):
#   <repo>/stats/fleet-stats.json   machine-readable snapshot, every source dated
#   <repo>/stats/FLEET.md           human-readable table
#   <repo>/README.md                the FLEET-STATS block, rewritten in place
#   <repo>/stats/.last-run          freshness stamp for an external watchdog (max age 200h)
#   stdout                          the report; the scheduler captures it to a log
# CONSUMER: Anton's CV and landing page cite these figures; the weekly run is what keeps the
#   citation honest. Second consumer: anyone reading the public repo.
#
# REFUSES TO PUBLISH IF THE EVALS GO RED. A broken gate must not get a fresh timestamp that
# makes it look maintained; that is how a dead control keeps a green badge.
#
# ENV
#   REPO_DIR   clone to work in     (default: $HOME/GitHub/agent-fleet-red-team)
#   FLEET_BUS  routine registry dir (optional; unset -> the fleet rows report "not available")
#   PY         python3 to use       (default: first python3 on PATH)
#   NO_PUSH=1  compute and commit locally, do not push
#
# updated: 2026-10-08
set -uo pipefail

# launchd and cron hand over a bare PATH; gh lives outside it on macOS.
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH"

REPO_DIR="${REPO_DIR:-$HOME/GitHub/agent-fleet-red-team}"
PY="${PY:-$(command -v python3 || true)}"
STAMP="$REPO_DIR/stats/.last-run"

say() { printf '[redteam-stats %s] %s\n' "$(date '+%Y-%m-%d %H:%M')" "$*"; }
die() { say "STOP: $*"; exit 1; }

# FLEET_BUS populates the routine-count rows. Unset but a vault is configured -> try the
# conventional location, so the unit file does not need a per-machine path edit. Still
# unset after that -> the table honestly says "not available on this machine".
if [ -z "${FLEET_BUS:-}" ] && [ -n "${OBSIDIAN_VAULT:-}" ] \
   && [ -d "$OBSIDIAN_VAULT/_machine-bus/routine-registry" ]; then
  export FLEET_BUS="$OBSIDIAN_VAULT/_machine-bus/routine-registry"
  say "FLEET_BUS derived from OBSIDIAN_VAULT"
fi

[ -n "$PY" ] || die "no python3 on PATH"
command -v git >/dev/null || die "no git on PATH"
[ -d "$REPO_DIR/.git" ] || die "no clone at $REPO_DIR (git clone https://github.com/tonydzi/agent-fleet-red-team \"$REPO_DIR\")"

cd "$REPO_DIR" || die "cannot cd $REPO_DIR"

# 1. Take the latest content. A merge conflict means a human edited the same block; stop
#    rather than clobber it.
say "pulling"
git pull --ff-only --quiet || die "pull is not fast-forward; a human change is waiting here"

# 2. Prove the gate still behaves before republishing its numbers.
say "running the mutation suite"
if ! "$PY" evals/test_red_first.py; then
  die "evals are RED -- numbers NOT republished. Fix the gate, do not refresh the timestamp."
fi

# 3. Recompute. --write updates the json, FLEET.md and the README block.
say "recomputing the numbers"
"$PY" stats/fleet_stats.py --write || die "fleet_stats.py failed"

# 4. Cheap leak scan before anything leaves the machine. Deliberately dumb: it looks for the
#    shapes of real credentials, and the only acceptable answer is zero hits.
say "leak scan"
if git diff --unified=0 | grep -nEi '(sk-[A-Za-z0-9_-]{16,}|ghp_[A-Za-z0-9]{20,}|xox[baprs]-[A-Za-z0-9-]{10,}|-----BEGIN [A-Z ]*PRIVATE KEY|AKIA[0-9A-Z]{16})'; then
  die "leak scan tripped on the pending diff -- nothing committed, nothing pushed"
fi

# 5. Publish only if something actually moved.
if git diff --quiet -- stats README.md; then
  say "no change this week; stamping freshness and finishing"
  date -u '+%Y-%m-%dT%H:%M:%SZ' > "$STAMP"
  exit 0
fi

say "changes found:"
git --no-pager diff --stat -- stats README.md

git add stats/fleet-stats.json stats/FLEET.md README.md
git -c user.name="${GIT_AUTHOR_NAME:-Anton Dziatkovskii}" \
    -c user.email="${GIT_AUTHOR_EMAIL:-dzyatkovskiy.a@gmail.com}" \
    commit --quiet -m "stats: weekly recompute $(date '+%Y-%m-%d')" \
    -m "Unattended run of stats/fleet_stats.py. Sources that could not be measured are reported as such in the table." \
  || die "commit failed"

if [ "${NO_PUSH:-0}" = "1" ]; then
  say "NO_PUSH=1 -- committed locally, not pushed"
else
  git push --quiet || die "push failed (commit is local, rerun after fixing auth)"
  say "pushed"
fi

date -u '+%Y-%m-%dT%H:%M:%SZ' > "$STAMP"
say "done"
