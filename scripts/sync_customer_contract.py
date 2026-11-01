#!/usr/bin/env python3
"""Compare the vendored customer spec with the account-service copy.

Read-only. Uses the caller's existing gh login and stores no credential.
Exit 0 when the documents match, 1 when they differ, 2 when the upstream
repo cannot be read.
"""

from __future__ import annotations

import base64
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VENDORED = ROOT / "docs" / "customer-rest-api.openapi.json"
UPSTREAM = "repos/Kavara-AI/kirk-account-service/contents/contracts/kirk-api/openapi.customer.json"


def canonical(document):
    return json.dumps(document, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def fetch():
    command = [
        "gh", "api",
        "-H", "Accept: application/vnd.github.raw",
        UPSTREAM + "?ref=main",
    ]
    try:
        completed = subprocess.run(command, capture_output=True, text=True, check=False)
    except OSError as exc:
        print("gh is not available (%s)." % exc, file=sys.stderr)
        return None
    if completed.returncode != 0:
        print("The account service repo is not readable from this login.", file=sys.stderr)
        detail = (completed.stderr or "").strip().splitlines()
        if detail:
            print(detail[-1], file=sys.stderr)
        return None
    body = completed.stdout
    try:
        return json.loads(body)
    except ValueError:
        # Some gh versions still return the JSON contents wrapper.
        try:
            wrapped = json.loads(body)
        except ValueError:
            print("Upstream response was not the contract JSON.", file=sys.stderr)
            return None
        raw = base64.b64decode(wrapped.get("content") or "")
        return json.loads(raw.decode("utf-8"))


def main():
    upstream = fetch()
    if upstream is None:
        return 2
    vendored = json.loads(VENDORED.read_text(encoding="utf-8"))
    if canonical(upstream) == canonical(vendored):
        print("Vendored spec matches the upstream customer contract.")
        return 0
    print("Vendored spec differs from the upstream customer contract.", file=sys.stderr)
    vendored_paths = set((vendored.get("paths") or {}))
    upstream_paths = set((upstream.get("paths") or {}))
    print("paths only upstream: %s" % sorted(upstream_paths - vendored_paths), file=sys.stderr)
    print("paths only vendored: %s" % sorted(vendored_paths - upstream_paths), file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
