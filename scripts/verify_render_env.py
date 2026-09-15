#!/usr/bin/env python3
"""Compare the env vars declared in render.yaml against the live Render service.

Why this exists
---------------
`render.yaml` in this repo does NOT control the live service: `DRONAv2` was created
manually in the Render dashboard and is not Blueprint-managed (ENGINEERING.md trap 4.10).
Before adopting it as a Blueprint, Render's docs warn that you must declare *every* option
the service currently has, or the Blueprint applies a default that "almost definitely
differs". Env vars are the part we cannot see from the CLI, so this closes that gap.

Safety
------
This script prints env var **names only**. Values are secrets and are never printed,
logged, or written to disk. Only `envVar.key` is read from the API response.

Usage
-----
    export RENDER_API_KEY=rnd_xxxxxxxxxxxx      # Dashboard > Account Settings > API Keys
    python scripts/verify_render_env.py

Exit codes
----------
    0  every live env var is declared in render.yaml (and nothing extra is declared)
    1  a mismatch was found -- see the report
    2  could not run (missing key, network/API error)
"""

from __future__ import annotations

import json
import os
import sys

SERVICE_ID = "srv-dajkh37qj5pc73e038i0"  # DRONAv2
API = "https://api.render.com/v1"
RENDER_YAML = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "render.yaml")

# Env vars the platform injects itself; they are never declared in render.yaml.
PLATFORM_MANAGED = {
    "PORT",
    "RENDER",
    "RENDER_SERVICE_ID",
    "RENDER_SERVICE_NAME",
    "RENDER_SERVICE_TYPE",
    "RENDER_EXTERNAL_URL",
    "RENDER_EXTERNAL_HOSTNAME",
    "RENDER_GIT_COMMIT",
    "RENDER_GIT_BRANCH",
    "RENDER_GIT_REPO_SLUG",
    "RENDER_INSTANCE_ID",
    "RENDER_DISCOVERY_SERVICE",
    "IS_PULL_REQUEST",
    "RENDER_CPU_COUNT",
    "RENDER_MEMORY_BYTES",
}


def declared_in_render_yaml() -> set[str]:
    """Env var keys declared in render.yaml, without importing a YAML library."""
    try:
        import yaml  # PyYAML ships with the project's requirements
    except ImportError:
        print("error: PyYAML is required (it is in requirements.txt)", file=sys.stderr)
        raise SystemExit(2)

    with open(RENDER_YAML, encoding="utf-8") as fh:
        doc = yaml.safe_load(fh)

    keys: set[str] = set()
    for service in doc.get("services", []) or []:
        for entry in service.get("envVars", []) or []:
            if isinstance(entry, dict) and entry.get("key"):
                keys.add(entry["key"])
    return keys


def live_keys(api_key: str) -> set[str]:
    """Env var NAMES on the live service. Values are never read out of the response."""
    # `requests` is used rather than urllib because it bundles certifi, which the
    # macOS python.org build does not have by default -- urllib fails there with
    # CERTIFICATE_VERIFY_FAILED.
    try:
        import requests
    except ImportError:
        print("error: `requests` is required (it is in requirements.txt)", file=sys.stderr)
        raise SystemExit(2)

    try:
        resp = requests.get(
            f"{API}/services/{SERVICE_ID}/env-vars",
            params={"limit": 100},
            headers={"Accept": "application/json", "Authorization": f"Bearer {api_key}"},
            timeout=30,
        )
    except requests.RequestException as exc:
        print(f"error: could not reach the Render API: {exc}", file=sys.stderr)
        raise SystemExit(2)

    if resp.status_code != 200:
        hint = {
            401: "API key missing or invalid",
            403: "no permission for this service",
            404: "service not found (check SERVICE_ID)",
        }.get(resp.status_code, "unexpected response")
        print(f"error: Render API returned {resp.status_code} ({hint})", file=sys.stderr)
        raise SystemExit(2)

    keys: set[str] = set()
    for item in resp.json():
        # Shape: [{"envVar": {"key": ..., "value": ...}, "cursor": ...}]
        env_var = item.get("envVar", item) if isinstance(item, dict) else {}
        key = env_var.get("key")
        if key:
            keys.add(key)
    return keys


def main() -> int:
    api_key = os.environ.get("RENDER_API_KEY", "").strip()
    if not api_key:
        print(
            "error: RENDER_API_KEY is not set.\n"
            "Create one at https://dashboard.render.com/u/settings?add-api-key\n"
            "then:  export RENDER_API_KEY=rnd_...",
            file=sys.stderr,
        )
        return 2

    live = live_keys(api_key) - PLATFORM_MANAGED
    declared = declared_in_render_yaml()

    missing = sorted(live - declared)   # live has it, render.yaml does not
    extra = sorted(declared - live)     # render.yaml declares it, live does not
    both = sorted(live & declared)

    print(f"service      : {SERVICE_ID} (DRONAv2)")
    print(f"live env vars: {len(live)}")
    print(f"declared     : {len(declared)}")
    print()

    if both:
        print(f"OK  declared and present on the service ({len(both)}):")
        for k in both:
            print(f"      {k}")
        print()

    if missing:
        print(f"MISSING from render.yaml ({len(missing)}) -- these exist on the service but are")
        print("not declared. Adoption preserves them, but the file is then incomplete:")
        for k in missing:
            print(f"      {k}")
        print()

    if extra:
        print(f"DECLARED but NOT on the service ({len(extra)}) -- adopting would CREATE these:")
        for k in extra:
            print(f"      {k}")
        print()

    if missing or extra:
        print("VERDICT: mismatch. Reconcile render.yaml before adopting the Blueprint.")
        return 1

    print("VERDICT: render.yaml declares exactly the env vars the live service has.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
