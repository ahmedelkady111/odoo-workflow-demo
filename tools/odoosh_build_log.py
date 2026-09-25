#!/usr/bin/env python3
"""Fetch and parse the Odoo.sh build log for a commit.

Two subcommands, deliberately separate so the parsing is testable without
network or SSH:

    fetch <sha>          resolve the build for <sha>, SSH in, print its logs
    parse <logfile...>   extract errors from an already-downloaded log

READ-ONLY on the Odoo.sh side. The only remote commands issued are ls/stat/
tail/cat. This never restarts a build, never writes, never touches the database.

Config: .odoosh.json at the repo root (see .odoosh.json.example).
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = REPO_ROOT / ".odoosh.json"

# Logs worth reading on a failed build, best first.
LOG_CANDIDATES = ["install.log", "update.log", "odoo.log", "build.log", "pip.log"]

SSH_OPTS = [
    "-o",
    "BatchMode=yes",
    "-o",
    "StrictHostKeyChecking=accept-new",
    "-o",
    "ConnectTimeout=15",
    "-o",
    "ServerAliveInterval=30",
    "-o",
    "ServerAliveCountMax=3",
]


# Exit codes: 0 = log clean, 1 = failures found and reported, 2 = tool could not run.
EXIT_CLEAN, EXIT_FOUND, EXIT_TOOL = 0, 1, 2


def die(msg: str, code: int = EXIT_TOOL):
    print(f"error: {msg}", file=sys.stderr)
    sys.exit(code)


def load_config() -> dict:
    if not CONFIG_PATH.exists():
        die(
            f"no {CONFIG_PATH.name} at the repo root.\n"
            f"       Copy .odoosh.json.example to .odoosh.json and fill in the project name."
        )
    try:
        return json.loads(CONFIG_PATH.read_text())
    except json.JSONDecodeError as exc:
        die(f"{CONFIG_PATH.name} is not valid JSON: {exc}")


def run(cmd: list[str], **kw) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


# --------------------------------------------------------------------------
# fetch
# --------------------------------------------------------------------------


def resolve_build_url(repo: str, sha: str, context_match: str) -> str | None:
    """Find the Odoo.sh build URL GitHub recorded for this commit."""
    for endpoint, jq in (
        (f"repos/{repo}/commits/{sha}/status", '.statuses[] | [.context, (.target_url // "")] | @tsv'),
        (f"repos/{repo}/commits/{sha}/check-runs", '.check_runs[] | [.name, (.html_url // "")] | @tsv'),
    ):
        proc = run(["gh", "api", endpoint, "--jq", jq])
        for line in proc.stdout.splitlines():
            parts = line.split("\t")
            if len(parts) == 2 and context_match.lower() in parts[0].lower() and parts[1]:
                return parts[1]
    return None


def parse_build_url(url: str) -> tuple[str | None, str | None, str | None]:
    """Pull (project, branch, build_id) out of an Odoo.sh build URL.

    Odoo.sh has used more than one URL shape; try the known ones and return
    whatever could be identified rather than guessing the rest.
    """
    m = re.search(r"/project/(?P<project>[^/]+)/branch/(?P<branch>.+?)/build/(?P<build>\d+)", url)
    if m:
        return m.group("project"), m.group("branch"), m.group("build")
    m = re.search(r"/build/(?P<build>\d+)", url)
    if m:
        return None, None, m.group("build")
    return None, None, None


def candidate_hosts(cfg: dict, project: str | None, branch: str | None, build: str | None) -> list[str]:
    """Build the list of hostnames to probe, most likely first."""
    if cfg.get("ssh_host"):  # explicit override wins outright
        return [cfg["ssh_host"]]

    project = project or cfg.get("project")
    if not project:
        return []

    domain = cfg.get("domain", "dev.odoo.com")
    slug = (branch or "").replace("/", "-").replace("_", "-")
    out = []
    if slug and build:
        out.append(f"{project}-{slug}-{build}.{domain}")
    if build:
        out.append(f"{project}-{build}.{domain}")
    if slug:
        out.append(f"{project}-{slug}.{domain}")
    return out


def probe(user: str, host: str) -> bool:
    proc = run(["ssh", *SSH_OPTS, f"{user}@{host}", "echo OK"])
    return proc.returncode == 0 and "OK" in proc.stdout


def fetch(args) -> int:
    cfg = load_config()
    user = cfg.get("ssh_user", "admin")
    context_match = cfg.get("check_context", "odoo.sh")
    outdir = Path(args.outdir)

    repo = (
        args.repo
        or run(["gh", "repo", "view", "--json", "nameWithOwner", "-q", ".nameWithOwner"]).stdout.strip()
    )
    sha = args.sha or run(["git", "rev-parse", "HEAD"]).stdout.strip()
    if not repo or not sha:
        die("could not determine repo and commit; pass --repo and <sha>")

    print(f"Repo   : {repo}")
    print(f"Commit : {sha}")

    if args.host:
        hosts, project, branch, build = [args.host], None, None, None
        print(f"Host   : {args.host} (explicit)")
    else:
        url = resolve_build_url(repo, sha, context_match)
        if not url:
            die(
                f"no Odoo.sh build URL recorded on {sha[:12]}.\n"
                f"       Either the build has not reported yet, or its check context does not\n"
                f"       contain '{context_match}'. Pass --host <build-host> to skip this lookup."
            )
        print(f"Build  : {url}")
        project, branch, build = parse_build_url(url)
        hosts = candidate_hosts(cfg, project, branch, build)
        if not hosts:
            die(
                "could not derive an SSH host from the build URL.\n"
                f'       Set "project" in {CONFIG_PATH.name}, or pass --host explicitly.\n'
                "       The host is shown on the build page in Odoo.sh under the SSH tab."
            )

    host = None
    for candidate in hosts:
        print(f"         probing {user}@{candidate} ...", end=" ", flush=True)
        if probe(user, candidate):
            print("connected")
            host = candidate
            break
        print("no")
    if not host:
        die(
            "could not SSH into any candidate host:\n"
            + "".join(f"         - {user}@{h}\n" for h in hosts)
            + "       Check that your key is registered on the Odoo.sh project, and that the\n"
            "       build still exists (Odoo.sh garbage-collects old development builds).\n"
            "       The exact host is on the build page under the SSH tab; pass it with --host."
        )

    listing = run(["ssh", *SSH_OPTS, f"{user}@{host}", "ls -1 ~/logs/ 2>/dev/null"]).stdout.split()
    print(f"Logs   : {', '.join(listing) if listing else '(none found in ~/logs)'}")

    wanted = [n for n in LOG_CANDIDATES if n in listing] or listing
    if not wanted:
        die(f"no log files under ~/logs on {host}")

    outdir.mkdir(parents=True, exist_ok=True)
    saved = []
    for name in wanted:
        # tail, not cat: build logs can be very large.
        proc = run(["ssh", *SSH_OPTS, f"{user}@{host}", f"tail -n {args.lines} ~/logs/{name}"])
        if proc.returncode != 0 or not proc.stdout:
            continue
        dest = outdir / f"{sha[:12]}-{name}"
        dest.write_text(proc.stdout)
        saved.append(dest)
        print(f"         saved {dest} ({len(proc.stdout.splitlines())} lines)")

    if not saved:
        die("connected, but every log read came back empty")

    print()
    return parse_files(saved, args.context)


# --------------------------------------------------------------------------
# parse
# --------------------------------------------------------------------------

TRACEBACK_START = re.compile(r"^\s*Traceback \(most recent call last\):")
LOG_LINE = re.compile(
    r"^(?P<ts>\d{4}-\d{2}-\d{2} [\d:,]+)\s+\d+\s+"
    r"(?P<level>[A-Z]+)\s+(?P<db>\S+)\s+(?P<logger>\S+):\s*(?P<msg>.*)"
)
# Final line of a traceback: "module.ExceptionName: message"
EXC_LINE = re.compile(r"^(?P<exc>[A-Za-z_][\w.]*(?:Error|Exception|Warning|Failure))\s*:\s*(?P<msg>.*)")
# re.M matters: these are searched across whole multi-line traceback blocks.
FILE_LINE = re.compile(r'^\s*File "(?P<path>[^"]+)", line (?P<line>\d+)', re.MULTILINE)
# Odoo XML parse errors name the offending file explicitly.
XML_ERR = re.compile(r'(?P<path>[^",\s]+\.xml)(?:[:,]\s*line\s*|:)(?P<line>\d+)', re.MULTILINE)

INTERESTING = ("ERROR", "CRITICAL")


def extract(text: str) -> dict:
    """Pull structured failures out of an Odoo log."""
    lines = text.splitlines()
    tracebacks, errors = [], []

    i = 0
    while i < len(lines):
        if TRACEBACK_START.search(lines[i]):
            block = [lines[i]]
            i += 1
            while i < len(lines):
                line = lines[i]
                block.append(line)
                # A traceback ends at its exception line -- which is not indented
                # and not another "File ..." frame.
                stripped = line.strip()
                if stripped and not line.startswith((" ", "\t")) and EXC_LINE.match(stripped):
                    break
                # A new timestamped log line means the traceback was cut short.
                if LOG_LINE.match(line):
                    block.pop()
                    i -= 1
                    break
                i += 1
            tracebacks.append("\n".join(block))
        else:
            m = LOG_LINE.match(lines[i])
            if m and m.group("level") in INTERESTING:
                errors.append(
                    {
                        "level": m.group("level"),
                        "logger": m.group("logger"),
                        "msg": m.group("msg").strip(),
                    }
                )
        i += 1

    return {"tracebacks": tracebacks, "errors": errors}


# Odoo.sh checks the repo out here; strip it so paths point at local files.
REMOTE_PREFIXES = ("/home/odoo/src/user/", "/home/odoo/src/")


def _relativize(path: str) -> str:
    for prefix in REMOTE_PREFIXES:
        if path.startswith(prefix):
            return path[len(prefix) :]
    return path


def addon_files(blocks: list[str]) -> list[str]:
    """Source files belonging to this project, not to Odoo core."""
    hits = []
    for block in blocks:
        for m in FILE_LINE.finditer(block):
            p = m.group("path")
            if "/src/odoo/" in p or "/site-packages/" in p or "/usr/lib/" in p:
                continue
            hits.append(f"{_relativize(p)}:{m.group('line')}")
        for m in XML_ERR.finditer(block):
            if "/src/odoo/" in m.group("path"):
                continue
            hits.append(_relativize(m.group("path")) + (f":{m.group('line')}" if m.group("line") else ""))
    seen, out = set(), []
    for h in hits:
        if h not in seen:
            seen.add(h)
            out.append(h)
    return out


def summarize(block: str) -> str:
    for line in reversed(block.splitlines()):
        s = line.strip()
        if EXC_LINE.match(s):
            return s
    return block.splitlines()[-1].strip() if block.splitlines() else "(empty)"


def parse_files(paths, context_lines: int) -> int:
    all_tb, all_err = [], []
    for p in paths:
        p = Path(p)
        if not p.exists():
            die(f"no such file: {p}")
        res = extract(p.read_text(errors="replace"))
        all_tb.extend(res["tracebacks"])
        all_err.extend(res["errors"])

    if not all_tb and not all_err:
        print("No ERROR/CRITICAL lines and no tracebacks found.")
        print("The build may have failed before Odoo started (check pip.log / build.log),")
        print("or the failure is not in the tail that was read -- retry with a larger --lines.")
        return EXIT_CLEAN

    # Deduplicate tracebacks by their exception line; a failing install repeats them.
    seen, unique = set(), []
    for tb in all_tb:
        key = summarize(tb)
        if key not in seen:
            seen.add(key)
            unique.append(tb)

    print("=" * 72)
    print(f"{len(unique)} distinct traceback(s), {len(all_err)} ERROR/CRITICAL line(s)")
    print("=" * 72)

    for n, tb in enumerate(unique, 1):
        print(f"\n--- traceback {n}: {summarize(tb)}")
        body = tb.splitlines()
        if context_lines and len(body) > context_lines:
            print("\n".join(body[: context_lines // 2]))
            print(f"    ... {len(body) - context_lines} frames omitted ...")
            print("\n".join(body[-(context_lines // 2) :]))
        else:
            print(tb)

    files = addon_files(unique)
    if files:
        print("\n" + "=" * 72)
        print("Project source referenced in these tracebacks (start here):")
        for f in files:
            print(f"  {f}")

    if all_err:
        print("\n" + "=" * 72)
        print("ERROR/CRITICAL lines:")
        seen_msgs = set()
        for e in all_err:
            key = (e["logger"], e["msg"][:120])
            if key in seen_msgs:
                continue
            seen_msgs.add(key)
            print(f"  [{e['level']}] {e['logger']}: {e['msg'][:200]}")

    return EXIT_FOUND


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    f = sub.add_parser("fetch", help="resolve the build for a commit, SSH in, read its logs")
    f.add_argument("sha", nargs="?", help="commit SHA (default: HEAD)")
    f.add_argument("--repo", help="owner/repo (default: from gh)")
    f.add_argument("--host", help="SSH host, bypassing URL-based discovery")
    f.add_argument("--lines", type=int, default=3000, help="log tail length (default 3000)")
    f.add_argument("--outdir", default=".odoosh-logs", help="where to save logs")
    f.add_argument("--context", type=int, default=0, help="truncate long tracebacks to N lines")

    p = sub.add_parser("parse", help="extract errors from downloaded log files")
    p.add_argument("files", nargs="+")
    p.add_argument("--context", type=int, default=0)

    args = ap.parse_args()
    if args.cmd == "fetch":
        return fetch(args)
    return parse_files(args.files, args.context)


if __name__ == "__main__":
    sys.exit(main())
