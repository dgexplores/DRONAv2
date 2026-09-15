#!/usr/bin/env python3
"""Apply render.yaml to the live Render service, via the Render CLI.

Why this exists
---------------
`render.yaml` in this repo does NOT control the live service: `DRONAv2` was created
manually in the Render dashboard and is not Blueprint-managed (ENGINEERING.md trap 4.10).
Editing the file therefore changes nothing, which has already caused a real incident -- a
`set -e` fix sat inert while production kept running `A && B || true; C`.

This script closes that gap without needing a Blueprint: it reads render.yaml and pushes the
values onto the service with `render services update`. After this, **render.yaml is the
source of truth** -- edit it, run this, done.

What it can and cannot apply
----------------------------
Applied:      buildCommand, startCommand, healthCheckPath, plan, branch, runtime, repo,
              rootDir, previews
NOT applied:  region          -- immutable after creation; Render rejects changes
              numInstances    -- no CLI flag exists
              autoDeploy off  -- the CLI only has `--auto-deploy` (enable), no disable
              envVars         -- `services update` has no env-var flag; secrets stay in the
                                 dashboard. `sync: false` entries must be set there anyway.
Anything it cannot apply is reported, never silently skipped.

Usage
-----
    python scripts/apply_render_config.py                # dry run: show what would change
    python scripts/apply_render_config.py --apply        # actually update the service
    python scripts/apply_render_config.py --apply --deploy   # and trigger a deploy

    # config changes do NOT auto-deploy; --deploy runs `render deploys create` for you.

Exit codes
----------
    0  success (or a clean dry run)
    1  the service could not be found, or the update failed
    2  could not run (missing render CLI, bad render.yaml, missing PyYAML)
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RENDER_YAML = os.path.join(REPO_ROOT, "render.yaml")
FALLBACK_SERVICE_ID = "srv-dajkh37qj5pc73e038i0"  # DRONAv2

# render.yaml field -> `render services update` flag
FIELD_TO_FLAG = {
    "buildCommand": "--build-command",
    "startCommand": "--start-command",
    "healthCheckPath": "--health-check-path",
    "plan": "--plan",
    "branch": "--branch",
    "repo": "--repo",
    "rootDir": "--root-directory",
    "previews": "--previews",
}

# Declared in render.yaml but NOT expressible through `render services update`. Reported,
# never silently skipped.
NOT_APPLICABLE = {
    "runtime": (
        "the CLI refuses it outright -- \"cannot switch runtimes via the CLI\". "
        "A runtime change needs the API or a new service."
    ),
    "region": "immutable after creation -- Render rejects changes",
    "numInstances": "no CLI flag exists for instance count",
    "envVars": "`services update` has no env-var flag; secrets live in the dashboard",
}


def find_render() -> str | None:
    """Locate the render CLI. PATH can be thin in non-interactive shells."""
    found = shutil.which("render")
    if found:
        return found
    for candidate in ("/opt/homebrew/bin/render", "/usr/local/bin/render"):
        if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return candidate
    return None


def load_service_block() -> dict:
    try:
        import yaml
    except ImportError:
        print("error: PyYAML is required (it is in requirements.txt)", file=sys.stderr)
        raise SystemExit(2)

    with open(RENDER_YAML, encoding="utf-8") as fh:
        doc = yaml.safe_load(fh)

    services = doc.get("services") or []
    if not services:
        print(f"error: no services defined in {RENDER_YAML}", file=sys.stderr)
        raise SystemExit(2)
    if len(services) > 1:
        print(
            f"error: {len(services)} services defined; this script assumes exactly one.",
            file=sys.stderr,
        )
        raise SystemExit(2)
    return services[0]


def resolve_service_id(render_bin: str, declared_name: str, override: str | None) -> str:
    """Prefer an explicit override, then look the name up, then fall back to the known ID."""
    if override:
        return override

    try:
        proc = subprocess.run(
            [render_bin, "services", "-o", "json"],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if proc.returncode == 0:
            for entry in json.loads(proc.stdout):
                svc = entry.get("service", {})
                if svc.get("name") == declared_name:
                    return svc["id"]
            print(
                f"warning: no live service named {declared_name!r}; "
                f"falling back to {FALLBACK_SERVICE_ID}",
                file=sys.stderr,
            )
    except (subprocess.SubprocessError, json.JSONDecodeError, KeyError, TypeError) as exc:
        print(f"warning: could not list services ({exc}); using {FALLBACK_SERVICE_ID}", file=sys.stderr)

    return FALLBACK_SERVICE_ID


def build_flags(service: dict) -> tuple[list[str], list[str], list[str]]:
    """Return (flags, applied_field_names, notes).

    `notes` explains anything in render.yaml this script could not apply, so nothing is
    skipped silently.
    """
    flags: list[str] = []
    applied: list[str] = []
    notes: list[str] = []

    for field, flag in FIELD_TO_FLAG.items():
        value = service.get(field)
        if value is None:
            continue
        flags += [flag, str(value)]
        applied.append(field)

    trigger = service.get("autoDeployTrigger")
    if trigger in ("commit", "checksPass"):
        flags.append("--auto-deploy")
        applied.append("autoDeployTrigger")
    elif trigger == "off":
        notes.append(
            "autoDeployTrigger: off -- the CLI only offers `--auto-deploy` (enable); "
            "disable auto-deploy in the dashboard instead."
        )

    for field, why in NOT_APPLICABLE.items():
        if field in service:
            notes.append(f"{field}: {why}")

    return flags, applied, notes


def verify(render_bin: str, service_id: str, expected: dict) -> bool:
    """Read the service back and compare. Never trust the file; check the running service."""
    try:
        proc = subprocess.run(
            [render_bin, "services", "-o", "json"],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if proc.returncode != 0:
            print("warning: could not read the service back for verification", file=sys.stderr)
            return False
        for entry in json.loads(proc.stdout):
            svc = entry.get("service", {})
            if svc.get("id") != service_id:
                continue
            details = svc.get("serviceDetails", {})
            actual = {
                "startCommand": details.get("envSpecificDetails", {}).get("startCommand"),
                "buildCommand": details.get("envSpecificDetails", {}).get("buildCommand"),
                "healthCheckPath": details.get("healthCheckPath"),
                "plan": details.get("plan"),
                "branch": svc.get("branch"),
            }
            ok = True
            print()
            print("verification (live service vs render.yaml):")
            for field, want in actual.items():
                if field not in expected:
                    continue
                match = str(want) == str(expected[field])
                ok &= match
                mark = "OK  " if match else "DIFF"
                print(f"  {mark} {field}")
                if not match:
                    print(f"        render.yaml: {expected[field]}")
                    print(f"        live       : {want}")
            return ok
    except (subprocess.SubprocessError, json.JSONDecodeError) as exc:
        print(f"warning: verification failed: {exc}", file=sys.stderr)
    return False


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Apply render.yaml to the live Render service (dry run by default).",
    )
    parser.add_argument("--apply", action="store_true", help="actually update the service")
    parser.add_argument("--deploy", action="store_true", help="trigger a deploy afterwards")
    parser.add_argument("--service", help="service ID or name (default: resolved from render.yaml)")
    args = parser.parse_args()

    render_bin = find_render()
    if not render_bin:
        print(
            "error: the `render` CLI was not found.\n"
            "Install it with:  brew install render",
            file=sys.stderr,
        )
        return 2

    service = load_service_block()
    service_id = resolve_service_id(render_bin, service.get("name", ""), args.service)
    flags, applied, notes = build_flags(service)

    print(f"render.yaml  : {RENDER_YAML}")
    print(f"service      : {service.get('name')} ({service_id})")
    print()

    if notes:
        print("NOT applied by this script:")
        for note in notes:
            print(f"  - {note}")
        print()

    if not flags:
        print("nothing to apply.")
        return 0

    cmd = [render_bin, "services", "update", service_id, *flags, "--confirm"]

    if not args.apply:
        print("DRY RUN -- nothing was changed. The command that would run:")
        print()
        print("  " + " \\\n    ".join(_quote(a) for a in cmd))
        print()
        print("Re-run with --apply to execute it.")
        return 0

    print(f"applying {len(applied)} setting(s) to {service_id}: {', '.join(applied)}")
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        print("error: `render services update` failed:", file=sys.stderr)
        print(proc.stderr.strip() or proc.stdout.strip(), file=sys.stderr)
        return 1
    print("update accepted.")

    verified = verify(render_bin, service_id, service)

    if args.deploy:
        print()
        print("triggering a deploy ...")
        deploy = subprocess.run(
            [render_bin, "deploys", "create", service_id, "--confirm"],
            capture_output=True,
            text=True,
        )
        if deploy.returncode != 0:
            print("error: `render deploys create` failed:", file=sys.stderr)
            print(deploy.stderr.strip() or deploy.stdout.strip(), file=sys.stderr)
            return 1
        print(deploy.stdout.strip() or "deploy created.")
    else:
        print()
        print("NOTE: a config change does not auto-deploy. Re-run with --deploy, or run:")
        print(f"  render deploys create {service_id} --confirm")

    return 0 if verified else 1


def _quote(arg: str) -> str:
    """Shell-quote for display only; the command is executed without a shell."""
    if arg and all(c.isalnum() or c in "-_./:=@," for c in arg):
        return arg
    return "'" + arg.replace("'", "'\\''") + "'"


if __name__ == "__main__":
    raise SystemExit(main())
