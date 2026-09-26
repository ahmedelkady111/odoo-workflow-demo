#!/usr/bin/env bash
# Install this repo's modules into a throwaway Odoo and run their tests --
# locally, before pushing, so Odoo.sh never has to be the one to tell you.
#
#   ./tools/run_odoo_tests.sh                 # every module under addons/
#   ./tools/run_odoo_tests.sh demo_library    # just this one
#
# WHY THIS EXISTS, AND WHY IT PARSES THE LOG:
# Odoo exits 0 on a WARNING. Odoo.sh does not -- it turns the build amber and
# reports commit status `error` to GitHub. Odoo 19 dropping `_sql_constraints`
# is exactly that shape: a warning, no traceback, exit 0, build fails. So the
# verdict here comes from tools/odoosh_build_log.py reading the log, the same
# parser used on real Odoo.sh logs -- not from Odoo's exit code.
#
# Everything it creates is namespaced and removed on exit. It never touches a
# container it did not start.
set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ODOO_IMAGE="${ODOO_IMAGE:-odoo:19}"
PG_IMAGE="${PG_IMAGE:-postgres:16}"
ADDONS_DIR="${ADDONS_DIR:-addons}"

# Namespaced so it can never collide with, or be mistaken for, a real stack.
# Deliberately avoids the substring "odoo" in container names.
TAG="otest-$$"
NET="${TAG}-net"
DB_CONTAINER="${TAG}-db"
LOG_DIR="${REPO_ROOT}/.odoo-test-logs"
LOG_FILE="${LOG_DIR}/run-$$.log"

say()  { printf '\033[1m%s\033[0m\n' "$*"; }
warn() { printf '\033[33m%s\033[0m\n' "$*"; }
die()  { printf '\033[31merror: %s\033[0m\n' "$*" >&2; exit 2; }

cleanup() {
    # Only ever touches what this run created.
    docker stop "$DB_CONTAINER" >/dev/null 2>&1
    docker network rm "$NET"    >/dev/null 2>&1
}
trap cleanup EXIT INT TERM

command -v docker >/dev/null || die "docker is not installed"
docker ps >/dev/null 2>&1     || die "cannot talk to the docker daemon"
[ -d "${REPO_ROOT}/${ADDONS_DIR}" ] || die "no ${ADDONS_DIR}/ directory at the repo root"

# --- which modules? -------------------------------------------------------
if [ "$#" -gt 0 ]; then
    MODULES="$(IFS=,; echo "$*")"
else
    MODULES="$(find "${REPO_ROOT}/${ADDONS_DIR}" -mindepth 2 -maxdepth 2 \
                 -name __manifest__.py -printf '%h\n' \
               | xargs -r -n1 basename | sort | paste -sd,)"
fi
[ -n "$MODULES" ] || die "found no modules under ${ADDONS_DIR}/"

# --test-enable alone runs the whole Odoo test suite of every module that gets
# installed as a dependency -- ~1500 tests, most of which fail on things the
# container lacks (websocket-client, browser bits) and none of which are yours.
# "/module" restricts a run to that module's own tests, which is also what
# Odoo.sh reports on.
TEST_TAGS="$(echo "$MODULES" | tr ',' '\n' | sed 's|^|/|' | paste -sd,)"

say "Modules : ${MODULES}"
say "Tests   : ${TEST_TAGS}"
say "Image   : ${ODOO_IMAGE}"
mkdir -p "$LOG_DIR"

# --- throwaway database ---------------------------------------------------
docker network create "$NET" >/dev/null 2>&1 || die "could not create docker network"
say "Postgres: starting ${DB_CONTAINER}"
docker run --rm -d --name "$DB_CONTAINER" --network "$NET" \
    -e POSTGRES_USER=odoo -e POSTGRES_PASSWORD=odoo -e POSTGRES_DB=postgres \
    "$PG_IMAGE" >/dev/null 2>&1 || die "could not start ${PG_IMAGE}"

printf '          waiting for postgres'
for _ in $(seq 1 45); do
    if docker exec "$DB_CONTAINER" pg_isready -U odoo >/dev/null 2>&1; then
        printf ' ready\n'; PG_READY=1; break
    fi
    printf '.'; sleep 1
done
[ "${PG_READY:-0}" = 1 ] || { printf '\n'; die "postgres never became ready"; }

# --- install + test -------------------------------------------------------
say "Odoo    : installing and testing (this is the slow part)"
# The official odoo image's entrypoint injects --db_host from $HOST (default
# "db"), which overrides a --db_host passed on the command line. Connection
# details therefore go in the environment, not in flags.
# Demo data is opt-in from Odoo 19 (--with-demo), so it is simply not requested.
docker run --rm --network "$NET" \
    -e HOST="$DB_CONTAINER" -e USER=odoo -e PASSWORD=odoo \
    -v "${REPO_ROOT}/${ADDONS_DIR}:/mnt/extra-addons:ro" \
    "$ODOO_IMAGE" \
    odoo -d testdb \
         --addons-path=/mnt/extra-addons \
         -i "$MODULES" \
         --test-enable --test-tags="$TEST_TAGS" --stop-after-init \
         --log-level=info \
         --http-interface=127.0.0.1 \
    > "$LOG_FILE" 2>&1
ODOO_RC=$?

LINES=$(wc -l < "$LOG_FILE")
say "Log     : ${LOG_FILE} (${LINES} lines, odoo exit ${ODOO_RC})"
echo

# --- verdict --------------------------------------------------------------
# The parser, not the exit code, decides -- see the header comment.
PARSER="${REPO_ROOT}/tools/odoosh_build_log.py"
if [ -f "$PARSER" ]; then
    python3 "$PARSER" parse "$LOG_FILE"
    PARSE_RC=$?
else
    warn "tools/odoosh_build_log.py not found; falling back to a raw grep"
    grep -E ' (WARNING|ERROR|CRITICAL) ' "$LOG_FILE" && PARSE_RC=1 || PARSE_RC=0
fi

echo
if [ "$PARSE_RC" -eq 1 ]; then
    warn "FAILED — the findings above would also fail the Odoo.sh build."
    exit 1
fi
if [ "$ODOO_RC" -ne 0 ]; then
    warn "Odoo exited ${ODOO_RC} but the log shows no warnings or errors."
    warn "Read ${LOG_FILE} in full; the failure may be outside Odoo's logging."
    exit 1
fi
say "PASSED — clean install, tests green, no warnings."
