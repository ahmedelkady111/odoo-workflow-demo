#!/usr/bin/env bash
# Verify the Odoo.sh build for a commit is GREEN.
#
# Odoo.sh reports build results back to GitHub as a commit status (and on some
# plans as a check run). This polls both until the Odoo.sh context resolves.
#
# Exit 0 only on success. "No build found" exits non-zero: an absent build must
# never read as a green one.
#
#   ./odoosh_gate.sh <owner/repo> <sha>
# env:
#   ODOOSH_CHECK_CONTEXT   exact context name; default = any context matching 'odoo.sh'
#   ODOOSH_TIMEOUT_MINUTES how long to wait for a pending build (default 30)
#   ODOOSH_POLL_SECONDS    poll interval (default 20)
set -euo pipefail

REPO="${1:?usage: $0 <owner/repo> <sha>}"
SHA="${2:?usage: $0 <owner/repo> <sha>}"

CONTEXT_MATCH="${ODOOSH_CHECK_CONTEXT:-odoo.sh}"
TIMEOUT_MINUTES="${ODOOSH_TIMEOUT_MINUTES:-30}"
POLL_SECONDS="${ODOOSH_POLL_SECONDS:-20}"
DEADLINE=$(( $(date +%s) + TIMEOUT_MINUTES * 60 ))

echo "Repo        : ${REPO}"
echo "Commit      : ${SHA}"
echo "Looking for : context matching '${CONTEXT_MATCH}'"
echo "Timeout     : ${TIMEOUT_MINUTES} min"
echo

# Emit "<state>\t<context>\t<url>" for every Odoo.sh-looking result on the commit,
# from the commit-status API and the check-runs API.
collect_results() {
    gh api "repos/${REPO}/commits/${SHA}/status" \
        --jq ".statuses[] | [.state, .context, (.target_url // \"\")] | @tsv" 2>/dev/null \
        | grep -iF "${CONTEXT_MATCH}" || true

    gh api "repos/${REPO}/commits/${SHA}/check-runs" \
        --jq '.check_runs[] | [(if .status != "completed" then "pending" else (.conclusion // "failure") end), .name, (.html_url // "")] | @tsv' 2>/dev/null \
        | grep -iF "${CONTEXT_MATCH}" || true
}

while :; do
    RESULTS="$(collect_results)"

    if [ -n "${RESULTS}" ]; then
        echo "Odoo.sh results for this commit:"
        echo "${RESULTS}" | awk -F'\t' '{printf "  %-10s %-45s %s\n", $1, $2, $3}'
        echo

        # Any hard failure -> fail immediately, no point waiting.
        if echo "${RESULTS}" | awk -F'\t' '{print $1}' | grep -qxE 'failure|error|cancelled|timed_out|action_required'; then
            echo "::error::Odoo.sh build is RED for ${SHA}. Fix the build, push, and let this check re-run."
            echo "${RESULTS}" | awk -F'\t' '$1 ~ /failure|error|cancelled|timed_out|action_required/ {print "  -> " $3}'
            exit 1
        fi

        # Still waiting on something?
        if echo "${RESULTS}" | awk -F'\t' '{print $1}' | grep -qxE 'pending|queued|in_progress'; then
            :
        elif echo "${RESULTS}" | awk -F'\t' '{print $1}' | grep -qxE 'success|neutral|skipped'; then
            echo "Odoo.sh build is GREEN for ${SHA}."
            exit 0
        fi
    else
        echo "No Odoo.sh result on ${SHA} yet..."
    fi

    NOW=$(date +%s)
    if [ "${NOW}" -ge "${DEADLINE}" ]; then
        echo
        if [ -z "${RESULTS}" ]; then
            echo "::error::No Odoo.sh build reported for ${SHA} within ${TIMEOUT_MINUTES} min."
            echo "Either the Odoo.sh GitHub integration is not reporting on this branch, or the"
            echo "context name differs from '${CONTEXT_MATCH}'. Set the repo variable"
            echo "ODOOSH_CHECK_CONTEXT to the exact name shown in the PR's checks list."
            echo "A missing build is NOT treated as a passing build."
        else
            echo "::error::Odoo.sh build still pending for ${SHA} after ${TIMEOUT_MINUTES} min."
            echo "Re-run this check once the build finishes, or raise ODOOSH_TIMEOUT_MINUTES."
        fi
        exit 1
    fi

    sleep "${POLL_SECONDS}"
done
