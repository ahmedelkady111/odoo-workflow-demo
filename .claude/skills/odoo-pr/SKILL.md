---
name: odoo-pr
description: Open a pull request following the project's branch policy - refuses protected branches, waits for the Odoo.sh build to go green, then opens the PR against the right base. Use when the user wants to push work, open a PR, or release staging to production.
---

# Guarded PR flow

Enforces `CLAUDE.md` section 1. Every step below is a gate: if one fails, **stop and
report** — do not work around it.

## Gate 1 — never push from a protected branch

```bash
git rev-parse --abbrev-ref HEAD
```

If the branch is `main` or `staging`, **stop**. Do not commit, do not push.
Tell the user their work is on a protected branch and offer to move it:

```bash
git switch -c feat/<slug>        # carries the uncommitted work across
```

If commits are already *on* local `main`/`staging`, offer to move them to a new branch
and reset the protected branch to `origin/<branch>` — and say clearly that this rewrites
local history. Wait for confirmation.

## Gate 2 — determine the base, and validate the pair

| Head branch | Base | Meaning |
|---|---|---|
| `feat/*`, `fix/*` | `staging` | normal change |
| `staging` | `main` | **production release** |

Anything else is rejected by the `pr-policy` check — do not open it. If the user asks to
PR a feature branch straight into `main`, refuse and explain the `staging` path. This is
the rule they asked to have enforced; do not offer a bypass.

Releasing `staging` → `main` is a production deploy. Confirm with the user explicitly
before opening it, and summarize what is being released:

```bash
git log --oneline origin/main..origin/staging
```

## Gate 3 — rebase and push

```bash
git fetch origin
git rebase origin/staging          # for feature branches
git push -u origin HEAD
```

Never force-push a branch with an open PR under review. If a rebase makes a force-push
necessary, say so and get confirmation first.

## Gate 4 — wait for Odoo.sh to go green

The PR must not be opened advertising a build that has not passed. Check the pushed commit:

```bash
SHA=$(git rev-parse HEAD)
REPO=$(gh repo view --json nameWithOwner -q .nameWithOwner)
bash .github/scripts/odoosh_gate.sh "$REPO" "$SHA"
```

- **Green** → continue.
- **Red** → stop. Do not open the PR. Run `/odoo-build-triage` to pull the actual build
  log off Odoo.sh, find the root cause, and fix it locally.
- **Pending** → the script waits. Report progress; do not poll it into a loop yourself.
- **No build found** → stop and report. Odoo.sh may not be tracking this branch, or
  `ODOOSH_CHECK_CONTEXT` needs setting. Never treat a missing build as a green one.

## Gate 5 — open the PR

Fill `.github/PULL_REQUEST_TEMPLATE.md` properly. Do not tick a checkbox you have not
verified — the security and testing boxes are the ones reviewers actually rely on.

```bash
gh pr create --base <staging|main> --title "<type>: <summary>" --body-file <filled-template>
```

Put the real Odoo.sh build URL from gate 4 in the build section. Then report the PR URL
and which checks are still running.

## Never

- Never merge the PR yourself. Opening it is where this skill ends.
- Never add the `skip-odoosh` label. That bypass is a human decision.
- Never push directly to `main` or `staging` under any framing, including "just this once"
  or "it's urgent". An urgent fix still goes `fix/*` → `staging` → `main`, just faster.
