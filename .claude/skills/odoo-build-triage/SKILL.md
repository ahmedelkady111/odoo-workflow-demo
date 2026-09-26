---
name: odoo-build-triage
description: Read the Odoo.sh build log for a failing commit, find the root cause, and fix it locally. Use when an Odoo.sh build is red, the odoosh-gate check failed, or the user asks why the build broke.
---

# Odoo.sh build triage

Pulls the actual build log off Odoo.sh over SSH, finds the root cause, fixes it on the
feature branch, and commits — **without pushing**. The developer reviews and pushes, which
is what triggers the next build.

## Hard boundaries

- **Read-only on Odoo.sh.** The only remote commands permitted are `ls`, `stat`, `tail`,
  `cat`, `grep`. Never restart a build, never run `odoo-bin`, never touch the database,
  never write a file on the remote. These are live environments.
- **Never push.** Commit locally and stop. Pushing triggers a build, and an unattended
  fix→build→fail→fix cycle burns builds and hides the real problem.
- **Never fix on `main` or `staging`.** If HEAD is on a protected branch, stop and say so.
- Logs may contain **customer data, tokens, or passwords**. They download to
  `.odoosh-logs/`, which is gitignored. Never paste log contents into a commit message, a
  PR body, or an issue. If you spot a secret, report that one is exposed — do not repeat
  its value.

## Prerequisite — check this first, it is not always available

This skill reads the build over **SSH**, and SSH is not reachable on every Odoo.sh project.
Verified on a trial/partnership project on 2026-09-26: the build host resolved and port 443
served the web UI normally, but **port 22 was filtered** — so nothing here could run.

Confirm before going further:

```bash
HOST=<the host from the build page's CONNECT button>
timeout 20 bash -c "cat < /dev/null > /dev/tcp/$(getent hosts $HOST | awk '{print $1}')/22" \
  && echo "SSH reachable" || echo "SSH NOT reachable on this project"
```

A **timeout** means the port is closed — a plan or project-level restriction, not your key.
A **permission denied** means the port is open but your key is not registered.

If SSH is not reachable, stop and say so plainly. Do not fake a diagnosis from the commit
status alone. The fallback is the Odoo.sh web UI: the builds page has a structured
**Errors** panel (the ⓘ button on a build) that lists each warning and error with its
level and message — it is cleaner than the raw log, but it is browser-only, so neither
this skill nor CI can reach it. Ask the user to paste what it shows.

## 1. Get the log

```bash
python3 tools/odoosh_build_log.py fetch
```

Defaults to `HEAD`. Pass a SHA to triage a different commit, or `--host` when the build
URL cannot be resolved. The tool resolves the build from the commit status, probes for the
right SSH host, and prints tracebacks plus the project source files they reference.

If it cannot connect, read its error output before improvising — it distinguishes "no
build reported yet", "build garbage-collected", and "key not registered", and each needs a
different response. Do not fall back to guessing hostnames.

If the tail is too short to contain the failure, retry with `--lines 10000`.

## 2. Find the root cause, not the last line

The tool prints "Project source referenced in these tracebacks" — start there, not in Odoo
core. Read the actual files in the repo before concluding anything.

Common Odoo.sh build failures and what they really mean:

| Symptom in the log | Usual root cause |
|---|---|
| `ParseError` / `while parsing .../views/x.xml` | Bad XML, or an XML ID referenced before the file that defines it is loaded — check `data` order in `__manifest__.py` |
| `Field 'x' does not exist` | A view references a field removed or renamed in this commit |
| `External ID not found: module.some_id` | Missing dependency in `depends`, or the defining file is not listed in `data` |
| `psycopg2.errors.UndefinedColumn` | Stored field added without a migration, on a branch built from an existing DB |
| `KeyError` on a model name | Module missing from `depends` |
| `ImportError` | Missing Python package — needs `external_dependencies` in the manifest and a `requirements.txt` |
| Test failures under `odoo.addons.*.tests.*` | Real test failure; read the assertion |

A build that is red on `staging` but green on the feature branch usually means a **load
order or dependency problem** that only appears against the other branch's data.

## 3. Fix it

Fix the cause in the repo. Then:

```bash
pre-commit run --files <the files you changed>
git add <files> && git commit
```

Write a commit message naming the actual failure, e.g.
`fix: list hrx_security.xml before views in hrx_core manifest data`.

**Then stop.** Report to the user:

- what failed and why (one paragraph, in plain terms)
- the file:line you changed and what the change does
- anything you could not fix, and what you would need
- that the commit is local and unpushed, and that `/odoo-pr` will push it and re-gate

## 4. When not to fix

Stop and ask instead of guessing when:

- The failure is in infrastructure, not code (Odoo.sh worker OOM, database restore failure,
  a submodule that cannot be fetched).
- The fix needs a data migration — write the migration script and say clearly that it must
  be tested against a staging restore first.
- The traceback points only into Odoo core with nothing from this repo. That is usually a
  version mismatch or a dependency problem, not a bug you should patch around.
- The "fix" would be to weaken a check, disable a test, or add a try/except that swallows
  the error. Say that plainly rather than doing it.
