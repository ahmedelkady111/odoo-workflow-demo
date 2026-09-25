---
name: odoo-review
description: Review the current Odoo diff against the project's coding standards before pushing. Use when the user asks to review changes, check an Odoo module, or before opening a PR. Read-only - reports findings, does not fix them unless asked.
---

# Odoo diff review

Read-only review of uncommitted and unpushed work against `CLAUDE.md` section 2.
Report findings; do not fix unless the user asks.

## 1. Establish the diff

```bash
git fetch origin staging --quiet
git diff --stat origin/staging...HEAD
git status --short
```

Review the union of committed-but-unpushed changes and the working tree.

## 2. Run the mechanical checks first

They are cheaper and more reliable than reading:

```bash
pre-commit run --files $(git diff --name-only origin/staging...HEAD)
```

If `pre-commit` is not installed, say so and continue with the manual pass — do not
silently skip. The **mandatory** pylint pass is blocking in CI, so anything it reports
will stop the PR.

## 3. Manual pass — what the linters cannot see

Go file by file over the diff and check:

**Security (highest value — most often missed)**
- Any new model in `models/` → is there a matching row in `security/ir.model.access.csv`?
  A model without an ACL is invisible to non-admin users and the bug surfaces far from here.
- Company/tenant/owner-scoped data → is there an `ir.rule`?
- Every new `.sudo()` → is there an inline comment naming the bypassed rule?
- Any string-built SQL → flag it.

**Correctness**
- Every `compute=` method has `@api.depends` listing *every* field it reads, including
  dotted paths. A missing dependency produces stale values only in production.
- No `search()` / `browse()` / `read()` inside a loop — flag as a performance defect,
  not a nit. This is the usual cause of "fast in dev, times out in prod".
- Overridden `create`/`write`/`unlink` call `super()` **and return its result**.
- Every new `Many2one` declares `ondelete=`.
- Controllers that catch `ValidationError` use an explicit `request.env.cr.savepoint()`
  — without it the partial write commits. Check this specifically; it has bitten before.

**Manifest and load order**
- `data:` lists security → data → views → menus, and every listed path exists.
- `version` is the `<series>.x.y.z` form.

**Views and JS**
- XML IDs follow `<model>_view_<type>` / `<model>_action`.
- No `t-raw` (use `t-out`), no jQuery, no `odoo.define`.

**Tests**
- New model, new computed field, or a bug fix → is there a test, and is it imported in
  `tests/__init__.py`? An unimported test never runs.

## 4. Report

Group findings by severity and give `file:line` for each:

- **Blocking** — CI will fail, or it is a security/data-loss defect.
- **Should fix** — real problem, not caught by CI.
- **Nit** — style, naming.

If nothing is wrong, say so plainly rather than inventing findings. End with whether this
is ready for `/odoo-pr`.
