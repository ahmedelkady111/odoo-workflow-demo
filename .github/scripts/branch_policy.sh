#!/usr/bin/env bash
# Branch policy: which head branches may target which base branches.
#
#   feat/* | fix/*  ->  staging     OK
#   staging         ->  main        OK  (this is the production release)
#   anything else               ->  rejected
#
# Sourced by CI and runnable locally:  ./branch_policy.sh <head> <base>
set -euo pipefail

PROD_BRANCH="${PROD_BRANCH:-main}"
STAGING_BRANCH="${STAGING_BRANCH:-staging}"

# check_policy <head> <base> -> 0 allowed, 1 rejected. Reason on stdout.
check_policy() {
    local head="$1" base="$2"

    case "$base" in
        "$PROD_BRANCH")
            if [ "$head" = "$STAGING_BRANCH" ]; then
                echo "OK: ${STAGING_BRANCH} -> ${PROD_BRANCH} is the production release path."
                return 0
            fi
            echo "REJECTED: '${head}' -> '${PROD_BRANCH}'."
            echo "Production only accepts '${STAGING_BRANCH}'. Retarget this PR at '${STAGING_BRANCH}';"
            echo "it reaches production through the ${STAGING_BRANCH} -> ${PROD_BRANCH} release PR."
            return 1
            ;;
        "$STAGING_BRANCH")
            case "$head" in
                feat/*|fix/*)
                    echo "OK: '${head}' -> '${STAGING_BRANCH}'."
                    return 0
                    ;;
                *)
                    echo "REJECTED: '${head}' -> '${STAGING_BRANCH}'."
                    echo "Only 'feat/<slug>' or 'fix/<slug>' branches may merge into '${STAGING_BRANCH}'."
                    return 1
                    ;;
            esac
            ;;
        *)
            echo "REJECTED: base branch '${base}' is not a merge target."
            echo "Open PRs against '${STAGING_BRANCH}' (feature work) or '${PROD_BRANCH}' (release, from '${STAGING_BRANCH}')."
            return 1
            ;;
    esac
}

# Only run when executed directly, so tests can source this file.
if [ "${BASH_SOURCE[0]}" = "${0}" ]; then
    if [ "$#" -ne 2 ]; then
        echo "usage: $0 <head-branch> <base-branch>" >&2
        exit 2
    fi
    check_policy "$1" "$2"
fi
