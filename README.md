# Odoo workflow demo

A working demonstration of an Odoo project governance setup: **Odoo/OCA coding standards
enforced by CI, a mandatory green Odoo.sh build before merge, and no path to production
except through `staging`.**

This repo exists to be looked at. Open the [pull request](../../pulls) and read the checks.

## The rules

| # | Rule | Enforced by |
|---|------|-------------|
| 1 | Code follows Odoo/OCA standards | `lint` — ruff + pylint-odoo + OCA module checks |
| 2 | No merge without a green Odoo.sh build | `odoosh-green` — reads the build status of the PR's head commit |
| 3 | Production only via `staging` | `pr-policy` — validates the head → base pair |

```
  feat/<slug>  ──PR──►  staging  ──PR──►  main
  fix/<slug>            (Odoo.sh          (production)
                         staging)
```

## What the open PR shows

`feat/loan-due-date` → `staging`. Three checks run:

- **`lint` passes.** `addons/demo_library` is written to the standards in `CLAUDE.md` —
  every model has an ACL row, `@api.depends` lists every field read, `ondelete` is explicit
  on every `Many2one`, no `search()` inside a loop, manifest `data` in load order.
- **`pr-policy` passes.** `feat/*` → `staging` is an allowed pair. Retarget the same PR at
  `main` and it fails, because production only accepts `staging`.
- **`odoosh-green` fails — on purpose.** There is no Odoo.sh project behind this demo repo,
  so no build status is ever reported. The gate treats *"no build found"* as a failure, not
  as a pass. That fail-closed behaviour is the point of the check: a missing build must
  never read as a green one. In a real project, Odoo.sh reports on each push and this check
  turns green by itself.

## Why a checkbox would not do

The PR template asks for the Odoo.sh build URL, but the gate does not trust it. It takes
`github.event.pull_request.head.sha` — supplied by GitHub, not by the PR author — and asks
the API for the build status recorded against *that exact commit*:

```
push  ->  Odoo.sh builds  ->  writes status on SHA abc123
PR event (head.sha = abc123)  ->  gate  ->  GET /commits/abc123/status
```

Push a new commit and the SHA changes, so the check re-runs from scratch. A tick in a box
does not.

## What is NOT enforced here

**GitHub has no pre-receive hooks.** No workflow can reject a `git push`. The
`no-direct-push` job only *detects* a direct push to a protected branch afterwards and
opens an issue. The control that actually prevents it is **branch protection**, a repo
setting — deliberately not enabled here so the demo stays readable.

## Layout

| Path | What it is |
|------|------------|
| `addons/demo_library/` | A small, standards-compliant Odoo 19 module |
| `.github/workflows/` | The three checks |
| `.github/scripts/` | Policy logic as testable shell, not inline YAML |
| `.claude/skills/` | `/odoo-pr`, `/odoo-review`, `/odoo-module`, `/odoo-build-triage` |
| `tools/odoosh_build_log.py` | Reads a red Odoo.sh build over SSH and points at the failing files |
| `CLAUDE.md` | The rules, as hard constraints for any AI agent working here |
| `docs/WORKFLOW.md` | The same workflow, for humans |

## Try it locally

```bash
pip install pre-commit && pre-commit install
pre-commit run --all-files    # the exact checks CI runs
```

## Credits

The lint layer follows the OCA community standard: [`OCA/odoo-pre-commit-hooks`](https://github.com/OCA/odoo-pre-commit-hooks),
[`OCA/pylint-odoo`](https://github.com/OCA/pylint-odoo), and configuration adapted from
[`OCA/oca-addons-repo-template`](https://github.com/OCA/oca-addons-repo-template).

> Note: OCA's published mandatory pylint list still names messages removed in `pylint-odoo` 10
> (they moved into `odoo-pre-commit-hooks`). Copying it verbatim breaks CI on the first run.
> The list in `.pylintrc-mandatory` was validated against the pinned version.
