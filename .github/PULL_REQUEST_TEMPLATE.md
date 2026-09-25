## What and why

<!-- What changed, and the reason. Link the ticket. -->

Closes #

## Modules touched

<!-- e.g. hr_custom, sale_tenant -->

## Odoo.sh build

> The `odoosh-gate` check verifies this independently against your head commit.
> Pasting a link to a different or older build will not get the PR merged.

- Build URL: <!-- https://www.odoo.sh/project/<project>/branch/<branch>/build/<id> -->
- [ ] The build for **this PR's latest commit** is green.

## Target branch

- [ ] `feat/*` or `fix/*` → **`staging`** (normal change), **or**
- [ ] **`staging` → `main`** (production release; no other source branch is allowed)

## Data and migration impact

- [ ] No schema change
- [ ] Adds fields/models — safe on upgrade
- [ ] Needs a migration script (`migrations/<version>/`) — attached and tested on a staging restore

## Security

- [ ] Every new model has a row in `security/ir.model.access.csv`
- [ ] Record rules added where data is company/tenant/owner scoped
- [ ] Any new `sudo()` carries an inline comment saying which rule it bypasses
- [ ] No secrets, tokens, or customer data in the diff or in test fixtures

## Testing

- [ ] Tests added/updated under `tests/` and imported in `tests/__init__.py`
- [ ] Verified on the Odoo.sh staging build, not only locally

<!-- Reviewers: see docs/WORKFLOW.md for what each check means. -->
