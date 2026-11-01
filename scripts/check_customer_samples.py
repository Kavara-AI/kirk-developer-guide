#!/usr/bin/env python3
"""Check that guide samples call only published customer routes.

The allow-list is the operation set in
Kavara-AI/kirk-account-service contracts/kirk-api/openapi.customer.json.
Samples are fenced python and shell blocks. Prose may name a route that is
not part of v1; a fence may not.

Exit status is 0 when every sample method and path is in the allow-list and
none is excluded, and when docs/customer-rest-api.openapi.json lists that
same operation set. The script uses the Python standard library only.
"""

from __future__ import annotations

import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OPENAPI_PATH = ROOT / "docs" / "customer-rest-api.openapi.json"
QUICKSTART = ROOT / "docs" / "customer-rest-api.md"

# Method and path pairs defined by the published customer contract.
ALLOWED = frozenset(
    {
        ("GET", "/v1/kirk-api/health"),
        ("GET", "/v1/kirk-api/contract"),
        ("GET", "/v1/kirk-api/openapi.json"),
        ("POST", "/v1/kirk-api/create"),
        ("POST", "/v1/kirk-api/learn"),
        ("POST", "/v1/kirk-api/score"),
    }
)
ALLOWED_PATHS = frozenset(path for _, path in ALLOWED)

EXCLUDED_EXACT = frozenset({"/v1/engine", "/v1/models", "/v1/score-book"})
EXCLUDED_SEGMENTS = frozenset({"mcp", "admin", "internal", "svc"})

SAMPLE_LANGS = frozenset({"python", "py", "bash", "sh", "shell", "curl", "http"})
FENCE = re.compile(r"```([^\n`]*)\n(.*?)```", re.DOTALL)
PY_CALL = re.compile(
    r"""call\(\s*['"](GET|POST|PUT|PATCH|DELETE|HEAD)['"]\s*,\s*['"]([^'"]+)['"]""",
    re.IGNORECASE,
)
SH_CALL = re.compile(
    r"""^call[ \t]+(GET|POST|PUT|PATCH|DELETE|HEAD)[ \t]+(/[^\s'"]+)""",
    re.IGNORECASE | re.MULTILINE,
)
QUOTED_PATH = re.compile(
    r"""['"](/(?:v1|usage|mcp|admin|internal|svc)[^'"]*)['"]"""
)
SHELL_PATH = re.compile(
    r"""(?:^|[\s=])(/(?:v1|usage|mcp|admin|internal|svc)[^\s'"]*)"""
)
KEY_LITERAL = re.compile(r"k_[0-9a-fA-F]{32}")

SKIP_DIRS = {".git", ".agents", "node_modules"}


def normalise(path):
    """Drop a query string and a trailing slash, except for the root."""
    bare = path.split("?", 1)[0].split("#", 1)[0]
    if len(bare) > 1:
        bare = bare.rstrip("/")
    return bare


def excluded(path):
    """True when the path is on the v1 exclusion list."""
    bare = normalise(path)
    if bare in EXCLUDED_EXACT or bare.startswith("/usage"):
        return True
    return any(part in EXCLUDED_SEGMENTS for part in bare.split("/"))


def fence_lang(info):
    """Language tag of a fence, ignoring a curly-brace info string."""
    token = info.strip().split()[0].lower() if info.strip() else ""
    if token.startswith("{") and token.endswith("}"):
        token = token[1:-1].split(",")[0].strip().lower()
    return token


def sample_fences(text):
    """Yield (language, body) for fenced samples."""
    for info, body in FENCE.findall(text):
        lang = fence_lang(info)
        if lang in SAMPLE_LANGS:
            yield lang, body


def calls_in_fence(lang, body):
    """Return (method, path) pairs written as call(...) or `call METHOD path`."""
    pattern = PY_CALL if lang in {"python", "py"} else SH_CALL
    found = []
    for method, path in pattern.findall(body):
        found.append((method.upper(), normalise(path)))
    return found


def path_literals(lang, body):
    """Return path strings that look like API routes inside a sample."""
    found = [normalise(path) for path in QUOTED_PATH.findall(body)]
    if lang not in {"python", "py"}:
        found.extend(normalise(path) for path in SHELL_PATH.findall(body))
    return found


def check_text(text, label):
    """Return human-readable failures for one markdown document."""
    failures = []
    for lang, body in sample_fences(text):
        if KEY_LITERAL.search(body):
            failures.append("%s: sample contains a key literal" % label)
        for path in path_literals(lang, body):
            if excluded(path):
                failures.append("%s: excluded path %s" % (label, path))
            elif path not in ALLOWED_PATHS:
                failures.append("%s: path %s is not in the customer contract" % (label, path))
        for method, path in calls_in_fence(lang, body):
            if excluded(path) or (method, path) not in ALLOWED:
                failures.append(
                    "%s: %s %s is not a published customer operation" % (label, method, path)
                )
    return failures


def check_openapi(document):
    """Return failures when the local spec is not exactly the allow-list."""
    failures = []
    found = set()
    paths = document.get("paths") or {}
    for path, item in paths.items():
        bare = normalise(path)
        if not isinstance(item, dict):
            failures.append("openapi: %s is not an object" % bare)
            continue
        for method in item:
            if method.startswith("x-") or method == "parameters":
                continue
            pair = (method.upper(), bare)
            found.add(pair)
            if excluded(bare) or pair not in ALLOWED:
                failures.append("openapi: %s %s is not a published customer operation" % pair)
    missing = ALLOWED - found
    extra = found - ALLOWED
    for method, path in sorted(missing):
        failures.append("openapi: missing %s %s" % (method, path))
    for method, path in sorted(extra):
        failures.append("openapi: unexpected %s %s" % (method, path))
    return failures


def check_quickstart(text):
    """The Python and curl samples must be the same three first calls."""
    wanted = [
        ("GET", "/v1/kirk-api/health"),
        ("GET", "/v1/kirk-api/contract"),
        ("POST", "/v1/kirk-api/create"),
    ]
    failures = []
    by_lang = {"python": [], "bash": []}
    for lang, body in sample_fences(text):
        if lang in {"python", "py"}:
            by_lang["python"].extend(calls_in_fence(lang, body))
        elif lang in {"bash", "sh", "shell"}:
            by_lang["bash"].extend(calls_in_fence(lang, body))
        if "User-Agent" not in body:
            failures.append("quickstart %s sample does not set User-Agent" % lang)
        if "KIP_API_KEY" not in body:
            failures.append("quickstart %s sample does not read KIP_API_KEY" % lang)
        if "X-Kavara-Key" not in body:
            failures.append("quickstart %s sample does not send X-Kavara-Key" % lang)
    for lang, found in by_lang.items():
        if found != wanted:
            failures.append("quickstart %s calls are %s, want %s" % (lang, found, wanted))
    return failures


def markdown_files(root):
    """Developer-guide markdown, skipping vendored skill trees."""
    files = []
    for path in root.rglob("*.md"):
        if any(part in SKIP_DIRS for part in path.relative_to(root).parts):
            continue
        files.append(path)
    return files


def scan_repository(root=ROOT):
    """Collect failures for the repository."""
    failures = []
    for path in markdown_files(root):
        text = path.read_text(encoding="utf-8")
        failures.extend(check_text(text, str(path.relative_to(root))))
    spec_path = root / "docs" / "customer-rest-api.openapi.json"
    document = json.loads(spec_path.read_text(encoding="utf-8"))
    failures.extend(check_openapi(document))
    quickstart = root / "docs" / "customer-rest-api.md"
    failures.extend(check_quickstart(quickstart.read_text(encoding="utf-8")))
    return failures


class SampleRouteTests(unittest.TestCase):
    def test_allowed_call_passes(self):
        text = "```python\ncall(\"GET\", \"/v1/kirk-api/health\")\n```\n"
        self.assertEqual(check_text(text, "fixture"), [])

    def test_excluded_call_fails(self):
        text = "```python\ncall(\"GET\", \"/v1/engine\")\n```\n"
        self.assertTrue(check_text(text, "fixture"))

    def test_usage_and_mcp_fail(self):
        text = "```bash\ncall GET /usage/me\ncall POST /mcp/rpc\n```\n"
        failures = check_text(text, "fixture")
        self.assertGreaterEqual(len(failures), 2)

    def test_prose_may_name_an_excluded_route(self):
        text = "GET /v1/engine is not part of v1.\n"
        self.assertEqual(check_text(text, "fixture"), [])

    def test_key_literal_fails(self):
        text = "```python\ncall(\"GET\", \"/v1/kirk-api/health\")  # k_" + ("a" * 32) + "\n```\n"
        self.assertTrue(any("key literal" in item for item in check_text(text, "fixture")))

    def test_openapi_must_match_the_allow_list(self):
        document = {"paths": {"/v1/models": {"get": {}}, "/v1/kirk-api/health": {"get": {}}}}
        failures = check_openapi(document)
        self.assertTrue(any("/v1/models" in item for item in failures))
        self.assertTrue(any("missing" in item for item in failures))


def main(argv):
    if "--self-test" in argv:
        suite = unittest.defaultTestLoader.loadTestsFromTestCase(SampleRouteTests)
        result = unittest.TextTestRunner(verbosity=1).run(suite)
        if not result.wasSuccessful():
            return 1
    failures = scan_repository()
    if failures:
        for item in failures:
            print(item, file=sys.stderr)
        print("%d customer-sample check(s) failed" % len(failures), file=sys.stderr)
        return 1
    print("customer sample routes match the published contract (%d operations)" % len(ALLOWED))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
