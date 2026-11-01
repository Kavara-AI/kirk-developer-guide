#!/usr/bin/env python3
"""Compare the vendored customer spec with an upstream copy.

Read-only. The upstream location is an argument or KDG_UPSTREAM_SPEC.
A local file path is read directly. Any other value is fetched with gh
using the caller's existing login. No credential is stored.

Exit 0 when the semantic contract matches, 1 when it differs, 2 when the
upstream document cannot be read.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VENDORED = ROOT / "docs" / "customer-rest-api.openapi.json"
IGNORED = {"description", "summary", "example", "examples", "externalDocs"}


def semantic(node):
    if isinstance(node, dict):
        return {
            key: semantic(value)
            for key, value in node.items()
            if key not in IGNORED and not str(key).startswith("x-")
        }
    if isinstance(node, list):
        return [semantic(value) for value in node]
    return node


def view(document):
    components = document.get("components") or {}
    kept = ("schemas", "parameters", "securitySchemes", "requestBodies", "responses", "headers")
    return {
        "paths": semantic(document.get("paths") or {}),
        "security": semantic(document.get("security") or []),
        "components": semantic({key: components.get(key) for key in kept}),
    }


def canonical(document):
    return json.dumps(view(document), sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def load_upstream(location):
    candidate = Path(location)
    if candidate.is_file():
        return json.loads(candidate.read_text(encoding="utf-8"))
    command = ["gh", "api", "-H", "Accept: application/vnd.github.raw", location]
    try:
        completed = subprocess.run(command, capture_output=True, text=True, check=False)
    except OSError as exc:
        print("gh is not available (%s)." % exc, file=sys.stderr)
        return None
    if completed.returncode != 0:
        print("The upstream spec is not readable from this login.", file=sys.stderr)
        return None
    try:
        return json.loads(completed.stdout)
    except ValueError:
        print("Upstream response was not the contract JSON.", file=sys.stderr)
        return None


def main(argv):
    location = argv[1] if len(argv) > 1 else os.environ.get("KDG_UPSTREAM_SPEC", "")
    if not location:
        print("upstream spec location is missing; pass a path or set KDG_UPSTREAM_SPEC", file=sys.stderr)
        return 2
    try:
        upstream = load_upstream(location)
    except (OSError, ValueError):
        print("upstream spec is not valid JSON", file=sys.stderr)
        return 2
    if upstream is None:
        return 2
    try:
        vendored = json.loads(VENDORED.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        print("vendored spec is missing", file=sys.stderr)
        return 2
    upstream_view = view(upstream)
    vendored_view = view(vendored)
    if canonical(upstream) == canonical(vendored):
        print("Vendored spec matches the upstream customer contract.")
        return 0
    print("Vendored spec differs from the upstream customer contract.", file=sys.stderr)
    for name in ("paths", "security", "components"):
        if upstream_view.get(name) != vendored_view.get(name):
            print("%s differs" % name, file=sys.stderr)
    vendored_paths = set((vendored.get("paths") or {}))
    upstream_paths = set((upstream.get("paths") or {}))
    print("paths only upstream: %s" % sorted(upstream_paths - vendored_paths), file=sys.stderr)
    print("paths only vendored: %s" % sorted(vendored_paths - upstream_paths), file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
