---
name: odoo-module
description: Scaffold a new Odoo module in the project's required layout, with security ACLs and a test stub pre-created. Use when the user asks to create a new Odoo module or addon.
---

# New Odoo module scaffold

Creates a module in the layout `CLAUDE.md` section 2 requires. The point of the scaffold
is that the two things people forget — the ACL row and the test — exist from minute one.

## Ask first, if not already clear

- Module technical name (snake_case, e.g. `hr_tenant_leave`)
- Human name and one-line summary
- Which addons it depends on
- The first model's `_name`, if there is one

## Layout to create

```
<module>/
├── __init__.py                 # from . import models
├── __manifest__.py
├── models/__init__.py          # from . import <model_file>
├── models/<model_file>.py
├── security/ir.model.access.csv
├── views/<model>_views.xml
├── views/<module>_menus.xml
└── tests/__init__.py           # from . import test_<model_file>
    tests/test_<model_file>.py
```

Create `data/`, `wizard/`, `report/`, `static/src/` only when they are actually needed.

## Manifest

Keys in this order — `name`, `summary`, `version`, `category`, `author`, `website`,
`license`, `depends`, `data`, `assets`, `installable`.

- `version` is `<series>.1.0.0`, taking the series from `.pylintrc-mandatory`'s
  `valid-odoo-versions`. Do not guess it.
- `data` in load order: **security → data → views → menus**. Getting this wrong works on
  upgrade and fails on a clean install, which is the worst way to find out.

## Security — not optional

Write a real row per model in `security/ir.model.access.csv`:

```csv
id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink
access_<model_file>_user,<model>.user,model_<model_file>,base.group_user,1,1,1,0
```

If the records are company/tenant/owner scoped, add an `ir.rule` in
`security/<module>_security.xml` and list it in `data` *before* the views.

## Model conventions

- File named after `_name` with dots → underscores.
- `_description` is mandatory.
- Every `Many2one` gets an explicit `ondelete=`.
- User-facing strings through `_()`.

## Test stub

A real `TransactionCase` that creates one record and asserts something true — not `pass`.
An empty test passes and gives false confidence.

## Finish

Run `pre-commit run --files <the new files>` and fix what it reports. Then tell the user
what was created and what they still need to fill in.
