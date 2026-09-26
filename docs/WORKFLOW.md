# Development workflow — odoo-workflow-demo

Three branches, one direction of travel. No exceptions, no hotfix shortcut.

```
  feat/<slug>  ─┐
  fix/<slug>   ─┼─► PR ─► staging ──► PR ──► main
                │         (Odoo.sh          (production)
                │          staging)
            cut from staging
```

## Daily loop

```bash
git switch staging && git pull
git switch -c feat/leave-accrual
# ...work...
pre-commit run --all-files          # fast checks: lint, manifest, security
./tools/run_odoo_tests.sh           # slow check: real Odoo install + tests
git push -u origin HEAD
```

Install the hooks once and the slow check runs automatically on `git push`:

```bash
pre-commit install --hook-type pre-push
```

It boots Odoo in Docker, so it takes minutes — which is why it runs on push, not
on every commit.

Then open the PR against **`staging`**. Or run `/odoo-pr`, which does all of the above
and refuses the paths that CI would reject anyway.

## Releasing to production

A release is a PR from `staging` to `main`. Nothing else reaches production.

```bash
git log --oneline origin/main..origin/staging   # what is about to ship
gh pr create --base main --head staging --title "Release $(date +%Y-%m-%d)"
```

## The checks on your PR

| Check | What it means | Fix |
|---|---|---|
| `lint` | `pre-commit` — ruff, pylint-odoo (mandatory pass), OCA module checks | Run `pre-commit run --all-files` locally; most issues auto-fix |
| `pr-policy` | Your head→base pair is allowed | Retarget the PR at `staging` |
| `odoosh-green` | Odoo.sh built **this commit** successfully | See below |

### When `odoosh-green` fails

- **Red build** — open the build URL in the check output, or pull the log yourself:

  ```bash
  python3 tools/odoosh_build_log.py fetch
  ```

  That SSHes into the build (read-only), reads `~/logs/`, and prints the tracebacks plus
  the files in *this repo* they point at. `/odoo-build-triage` does the same and fixes the
  cause. Usual causes: a module fails to install (bad `data` load order, missing
  dependency), a Python import error, or a failing test. Fix, push; the check re-runs on
  the new commit.
- **Pending past the timeout** — the build is slow, not broken. Re-run the check once
  Odoo.sh finishes, or raise the `ODOOSH_TIMEOUT_MINUTES` repo variable.
- **"No Odoo.sh build reported"** — the check could not find a status matching `odoo.sh`
  on your commit. Either Odoo.sh is not tracking this branch, or its check is named
  something else: look at the PR's checks list and set the repo variable
  `ODOOSH_CHECK_CONTEXT` to the exact name. A missing build is deliberately treated as a
  failure, never as a pass.

### Why there is no "run the tests" job in CI

Odoo.sh already installs your modules and runs their tests on every push — in about 25
seconds — and `odoosh-green` blocks the merge on that verdict. A GitHub Actions job doing
the same thing would take 6-10 minutes (it downloads a 2 GB image and builds from scratch)
and would tell you nothing new.

When Odoo.sh goes red it gives you the verdict, not the reason. You get the reason by
running the same script locally, for free:

```bash
./tools/run_odoo_tests.sh
```

### Why the tests are judged on the log, not the exit code

`odoo -i <module> --test-enable` exits **0** even when it logs a warning. Odoo.sh does not:
a warning turns its build amber and reports commit status `error` to GitHub. Odoo 19
dropping `_sql_constraints` is exactly that shape — a warning, no traceback, exit 0, and
the constraint silently never reaches the database.

So `run_odoo_tests.sh` reads the log with the same parser used on real Odoo.sh logs and
fails on `WARNING` too. Verified: with `_sql_constraints` reintroduced, Odoo exits 0 and
the script still fails, naming the warning.

## Rules that are not negotiable

- No commits or pushes to `main` or `staging`. Ever. The `no-direct-push` check will
  notice and open an issue naming you.
- No PR into `main` from anything but `staging`.
- No merging on a red or missing Odoo.sh build. The `skip-odoosh` label exists for a
  genuine emergency and its use is logged loudly in the check output — it is a decision a
  human owns, in writing, in the PR.
- An urgent fix is not an exception. It goes `fix/<slug>` → `staging` → `main`. Two PRs,
  ten minutes.
