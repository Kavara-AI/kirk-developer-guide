#!/usr/bin/env python3
"""Fail closed on customer samples that drift from the vendored spec.

Scans text in the repository. Unknown fence languages are scanned, not skipped.
The operation allow-list is loaded from docs/customer-rest-api.openapi.json
at runtime. Term matching uses KDG_BANNED_TERMS and refuses to run when that
list is missing.

Secret lines are trimmed and blank lines are ignored. A line that starts with
``/`` is a route entry. An exact entry matches when its segments are a
contiguous run at the end of a path. A trailing ``*`` is a prefix entry and
also matches when further segments follow. A partial segment does not match.
Normalisation is NFKC, casefold, URL-decoding, slash collapsing, a trailing
slash, query, fragment, or parameter suffix, and ``.`` and ``..`` segments.
A leading version segment matches any version. Dashes and dots inside a
segment are removed. The base64 and rot13 of the whole path are checked.
Literal pieces joined in one expression are evaluated too. ``short:`` never
applies to a route.
``short:`` (any case) marks a short root matched on a token boundary. Any
other line is a long root, including inside a longer word and with its parts
joined and with no separator.
"""

from __future__ import annotations

import base64
import datetime
import functools
import hashlib
import html
import ipaddress
import json
import os
import posixpath
import re
import shlex
import shutil
import sys
import tempfile
import unicodedata
import unittest
from pathlib import Path
from urllib.parse import unquote_plus, urlsplit

ROOT = Path(__file__).resolve().parents[1]
OPENAPI_PATH = ROOT / "docs" / "customer-rest-api.openapi.json"
PUBLIC_API_BASE = "https://api.kavara.ai"
SECRET_NAME = "KDG_BANNED_TERMS"
MISSING_SECRET = SECRET_NAME + " is missing or empty"

# Retired route names are extra entries in KDG_BANNED_TERMS, not literals here.
# A line prefixed with "short:" is a short root, matched on a token boundary.
# Every other non-blank line is a long root, matched anywhere. Length is not used.
SHORT_PREFIX = "short:"
DIGEST_RELATIVE = "scripts/customer-spec.digest"
SYNTHETIC_PATH = "/v1/kirk-api/synthetic-extra"
# Exact whole token only. Digits only: the max_body_bytes const in the vendored spec.
# 8 * 1024 * 1024. Strict ISO 8601 dates are exempt separately, not listed here.
HEX_ALLOW = frozenset({"8388608"})
# skills.<name>.computedHash in this file only, and only an exact 64-hex value.
LOCK_RELATIVE = "skills-lock.json"
LOCK_OBJECT = "skills"
LOCK_FIELD = "computedHash"

BLOCKED_SEGMENTS = frozenset({"mcp", "admin", "internal", "svc"})
HTTP_METHODS = frozenset({"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"})
SKIP_DIRS = {".git", "node_modules"}
BINARY_SUFFIXES = {
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".pdf", ".zip",
    ".woff", ".woff2", ".ico", ".pyc", ".so", ".dll", ".exe",
    ".bin", ".npy", ".npz", ".wasm",
}
KEY_LITERAL = re.compile(r"k_[0-9a-fA-F]{32}")
FENCE_RE = re.compile(
    r"(?ms)^(?P<open>`{3,}|~{3,})[ \t]*(?P<info>[^\n]*)\n(?P<body>.*?)^(?P=open)[ \t]*$"
)
INLINE_RE = re.compile(r"(?<!`)`([^`\n]+)`(?!`)")
ROUTE_RE = re.compile(
    r"https?://[^\s'\"`<>)\]]+"
    r"|\$\{(?:BASE_URL|BASE|HOST|API)[^}]*\}(/[A-Za-z0-9_./{}~$-]*)"
    r"|(?<![\w$])(/(?:v1|mcp|admin|internal|svc)(?:/[A-Za-z0-9_./{}~$-]*)?)",
    re.IGNORECASE,
)
QUICKSTART_CALLS = (
    ("GET", "/v1/kirk-api/health"),
    ("GET", "/v1/kirk-api/contract"),
    ("POST", "/v1/kirk-api/create"),
)


def spec_fingerprint(document):
    """Canonical digest of the whole document, including paths and components."""
    blob = json.dumps(document, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def load_document(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def normalise(path):
    bare = (path or "").split("?", 1)[0].split("#", 1)[0]
    if len(bare) > 1:
        bare = bare.rstrip("/")
    return bare


def blocked(path):
    bare = normalise(path)
    return any(part.lower() in BLOCKED_SEGMENTS for part in bare.split("/") if part)


def resolve_ref(schema, document):
    seen = set()
    while isinstance(schema, dict) and "$ref" in schema:
        ref = schema["$ref"]
        if ref in seen:
            break
        seen.add(ref)
        node = document
        for part in ref.lstrip("#/").split("/"):
            if not isinstance(node, dict) or part not in node:
                return schema
            node = node[part]
        schema = node
    return schema


class Spec(object):
    def __init__(self, document):
        self.document = document
        servers = document.get("servers") or [{}]
        self.public_base = (servers[0].get("url") if servers else "") or ""
        self.operations = {}
        for path, item in (document.get("paths") or {}).items():
            if not isinstance(item, dict):
                continue
            bare = normalise(path)
            for method, operation in item.items():
                if method.upper() in HTTP_METHODS and isinstance(operation, dict):
                    self.operations[(method.upper(), bare)] = operation
        self.allowed_paths = frozenset(path for _, path in self.operations)
        schemes = ((document.get("components") or {}).get("securitySchemes") or {})
        names = []
        for scheme in schemes.values():
            if isinstance(scheme, dict) and scheme.get("type") == "apiKey" and scheme.get("in") == "header":
                if scheme.get("name"):
                    names.append(scheme["name"])
        self.security_headers = tuple(names)

    def operation(self, method, path):
        return self.operations.get((method.upper(), normalise(path)))

    def content_types(self, operation):
        body = (operation or {}).get("requestBody") or {}
        content = body.get("content") or {}
        return tuple(content.keys())

    def body_schema(self, operation, content_type):
        body = (operation or {}).get("requestBody") or {}
        content = body.get("content") or {}
        media = content.get(content_type) or {}
        schema = media.get("schema")
        if schema is None:
            return None
        return resolve_ref(schema, self.document)

    def body_required(self, operation):
        body = (operation or {}).get("requestBody") or {}
        return bool(body.get("required"))


def is_allowed_path(path, spec):
    bare = normalise(path)
    if bare in spec.allowed_paths:
        return True
    prefix = bare + "/"
    return any(allowed.startswith(prefix) for allowed in spec.allowed_paths)


def bad_base(url, public_base):
    """Why this absolute URL is not the public API base, or None."""
    parsed = urlsplit(url)
    host = parsed.hostname
    public = urlsplit(public_base)
    if not host:
        return "missing host"
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        ip = None
    if ip is not None and (ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_unspecified):
        return "private, loopback or non-public host"
    if parsed.scheme != public.scheme or host != public.hostname:
        return "base URL is not the public api base"
    return None


def assigned_base(text):
    match = re.search(r"""BASE_URL\s*=\s*['"]([^'"]+)['"]""", text)
    return match.group(1) if match else None


def resolve_url(raw, text):
    base = assigned_base(text)
    if raw.startswith("${BASE_URL}"):
        if not base:
            return None
        return base + raw[len("${BASE_URL}"):]
    if raw.startswith(("http://", "https://")):
        return raw
    if raw.startswith("/") and base:
        return base.rstrip("/") + raw
    return None


def header_map(items):
    found = {}
    for item in items:
        name, _, value = item.partition(":")
        name = name.strip()
        if name:
            found[name] = value.strip()
    return found


def validate_schema(instance, schema, document, path):
    """Return errors. Unknown object fields fail even when the schema omits additionalProperties."""
    if not isinstance(schema, dict):
        return ["%s: missing schema" % path]
    schema = resolve_ref(schema, document)
    errors = []
    if "const" in schema and instance != schema["const"]:
        errors.append("%s: expected %r" % (path, schema["const"]))
    if "enum" in schema and instance not in schema["enum"]:
        errors.append("%s: value not in enum" % path)
    expected = schema.get("type")
    if expected == "object":
        if not isinstance(instance, dict):
            return errors + ["%s: expected object" % path]
        properties = schema.get("properties") or {}
        for key in schema.get("required") or []:
            if key not in instance:
                errors.append("%s: missing %s" % (path, key))
        for key, value in instance.items():
            if key not in properties:
                errors.append("%s: unknown field %s" % (path, key))
            else:
                errors.extend(validate_schema(value, properties[key], document, path + "." + key))
        return errors
    if expected == "integer":
        if isinstance(instance, bool) or not isinstance(instance, int):
            return errors + ["%s: expected integer" % path]
        if "minimum" in schema and instance < schema["minimum"]:
            errors.append("%s: below minimum" % path)
        if "maximum" in schema and instance > schema["maximum"]:
            errors.append("%s: above maximum" % path)
        return errors
    if expected == "string":
        if not isinstance(instance, str):
            errors.append("%s: expected string" % path)
        return errors
    if expected == "array":
        if not isinstance(instance, list):
            errors.append("%s: expected array" % path)
        return errors
    return errors


def validate_call(method, path, url, headers, body, output, spec, label):
    failures = []
    bare = normalise(path)
    if blocked(bare) or bare not in spec.allowed_paths:
        failures.append("%s: operation 0" % label)
        return failures
    if url is None:
        failures.append("%s: operation 0" % label)
    else:
        reason = bad_base(url, spec.public_base)
        if reason:
            failures.append("%s: base 0" % label)
        if bad_base(url, PUBLIC_API_BASE):
            failures.append("%s: sample base is not %s" % (label, PUBLIC_API_BASE))
    if spec.public_base != PUBLIC_API_BASE:
        failures.append("%s: vendored server URL is not the public api base" % label)
    allowed_names = {name.lower() for name in spec.security_headers}
    operation = spec.operation(method, bare)
    types = spec.content_types(operation)
    content_type = None
    for name, value in headers.items():
        if name.lower() == "content-type":
            content_type = value.split(";", 1)[0].strip().lower()
            continue
        if name.lower() == "authorization" or name.lower() not in allowed_names:
            failures.append("%s: header %s is not in the security scheme" % (label, name))
    for name in spec.security_headers:
        if name.lower() not in {key.lower() for key in headers}:
            failures.append("%s: missing required header %s" % (label, name))
    if body is None:
        if content_type is not None:
            failures.append("%s: content type on a call with no body" % label)
        if spec.body_required(operation):
            failures.append("%s: missing request body" % label)
    else:
        if content_type is None:
            failures.append("%s: missing content type" % label)
        elif content_type not in {item.lower() for item in types}:
            failures.append("%s: content type %s is not in the spec" % (label, content_type))
        else:
            schema = spec.body_schema(operation, content_type)
            if schema is not None:
                try:
                    parsed = json.loads(body)
                except ValueError:
                    failures.append("%s: request body is not JSON" % label)
                else:
                    failures.extend(
                        "%s: %s" % (label, item)
                        for item in validate_schema(parsed, schema, spec.document, "body")
                    )
    if output is not None and output == "":
        failures.append("%s: curl sample has an empty -o path" % label)
    return failures


def python_headers(text):
    match = re.search(r"headers\s*=\s*\{", text)
    headers = {}
    if match:
        raw = balanced(text, match.end() - 1, "{", "}")
        if raw:
            pairs = re.finditer(
                r"""['"]([A-Za-z][A-Za-z0-9-]*)['"]\s*:\s*(['"]([^'"]*)['"]|[A-Za-z_][A-Za-z0-9_]*)""",
                raw,
            )
            for found in pairs:
                headers[found.group(1)] = found.group(3) if found.group(3) is not None else "present"
    conditional = None
    cond = re.search(
        r"""if payload is not None:[\s\S]{0,400}?headers\[\s*['"]Content-Type['"]\s*\]\s*=\s*['"]([^'"]+)['"]""",
        text,
    )
    if cond and "Content-Type" not in headers:
        conditional = cond.group(1)
    return headers, conditional


def python_calls(text):
    calls = []
    start = 0
    while True:
        index = text.find("call(", start)
        if index < 0:
            break
        prefix = text[max(0, index - 4):index]
        if prefix.endswith("def "):
            start = index + 5
            continue
        cursor = index + 5
        method, cursor = parse_string(text, skip_ws(text, cursor))
        if method is None:
            start = index + 5
            continue
        cursor = skip_ws(text, cursor)
        if cursor < len(text) and text[cursor] == ",":
            cursor += 1
        path, cursor = parse_string(text, skip_ws(text, cursor))
        if path is None:
            start = index + 5
            continue
        body = None
        cursor = skip_ws(text, cursor)
        if cursor < len(text) and text[cursor] == ",":
            cursor = skip_ws(text, cursor + 1)
            if cursor < len(text) and text[cursor] == "{":
                body = balanced(text, cursor, "{", "}")
        calls.append((method.upper(), path, body))
        start = index + 5
    return calls


def curl_commands(text):
    joined = text.replace("\\\n", " ")
    commands = []
    for match in re.finditer(r"(?m)^\s*curl\b(.*)$", joined):
        try:
            argv = shlex.split(match.group(1), posix=True)
        except ValueError:
            commands.append({"error": "curl command could not be parsed"})
            continue
        method = None
        url = None
        headers = []
        data = None
        output = None
        basic = False
        url_query = []
        index = 0
        while index < len(argv):
            arg = argv[index]
            nxt = argv[index + 1] if index + 1 < len(argv) else None
            if arg in ("--request", "-X") and nxt is not None:
                method = nxt
                index += 2
                continue
            if arg == "--url" and nxt is not None:
                url = nxt
                index += 2
                continue
            if arg in ("--header", "-H") and nxt is not None:
                headers.append(nxt)
                index += 2
                continue
            if arg in ("--data", "--data-raw", "--data-binary", "-d") and nxt is not None:
                data = nxt
                index += 2
                continue
            if arg in ("--output", "-o") and nxt is not None:
                output = nxt
                index += 2
                continue
            if arg == "--url-query" and nxt is not None:
                url_query.append(nxt)
                index += 2
                continue
            if arg.startswith("--url-query="):
                url_query.append(arg.split("=", 1)[1])
                index += 1
                continue
            if arg in ("-u", "--user") or arg.startswith("--user="):
                basic = True
                index += 2 if arg in ("-u", "--user") and nxt is not None else 1
                continue
            if arg.startswith("-u") and not arg.startswith("--"):
                basic = True
                index += 1
                continue
            if arg.startswith(("http://", "https://", "${")):
                url = arg
            index += 1
        if method is None:
            method = "POST" if data is not None else "GET"
        commands.append({
            "method": method.upper(),
            "url": url,
            "headers": header_map(headers),
            "data": data,
            "output": output,
            "basic": basic,
            "url_query": url_query,
        })
    return commands


def route_hits(text):
    hits = []
    for match in ROUTE_RE.finditer(text):
        absolute = match.group(0)
        if absolute.startswith(("http://", "https://")):
            path = urlsplit(absolute).path or ""
            hits.append((normalise(path), absolute))
            continue
        if absolute.startswith("${"):
            path = match.group(1) or ""
            hits.append((normalise(path), absolute))
            continue
        path = match.group(2) or absolute
        hits.append((normalise(path), path))
    return hits


def customer_sample_target(path, shown):
    """Absolute URLs count only when they address the API or an API-shaped path."""
    if not str(shown).startswith(("http://", "https://")):
        return True
    parsed = urlsplit(shown)
    host = (parsed.hostname or "").lower()
    public_host = (urlsplit(PUBLIC_API_BASE).hostname or "").lower()
    if host == public_host:
        return True
    try:
        ipaddress.ip_address(host)
        return True
    except ValueError:
        pass
    parts = [part for part in normalise(path).split("/") if part]
    roots = {"v1", "mcp", "admin", "internal", "svc"}
    return bool(parts) and parts[0].lower() in roots


def check_routes(text, spec, label):
    failures = []
    for path, shown in route_hits(text):
        if not path:
            continue
        if not customer_sample_target(path, shown):
            continue
        if blocked(path) or not is_allowed_path(path, spec):
            failures.append("%s: unpublished route" % label)
        if shown.startswith(("http://", "https://")):
            reason = bad_base(shown, PUBLIC_API_BASE)
            if reason and not blocked(path):
                failures.append("%s: %s" % (label, reason))
    return failures


def misplaced_secret(text, label):
    """The customer key belongs only in the request header."""
    failures = []
    if re.search(
        r"(?i)(?:\?|&amp;|&|%3f|%26)"
        r"(?:access_token|api_key|apikey|x-kavara-key|key)(?:=|%3d)",
        text,
    ):
        failures.append("%s: key must be a request header, not a query string" % label)
    if re.search(r"(?i)--url-query(?:\s+|=)\S*(?:key|x-kavara-key)\b", text):
        failures.append("%s: key must be a request header, not --url-query" % label)
    if re.search(r"(?i)(?:^|\s)-G\b", text) and re.search(
        r"(?i)(?:--data(?:-raw|-binary|-urlencode)?\b|(?:^|\s)-d\b)",
        text,
    ):
        failures.append("%s: key must not be moved into the query with -G --data-urlencode" % label)
    if re.search(r"(?i)--oauth2-bearer\b", text):
        failures.append("%s: oauth2 bearer is not the security scheme" % label)
    if re.search(r"(?i)params\s*=\s*\{[^}]*(?:X-Kavara-Key|\bkey\b)", text):
        failures.append("%s: key must be a request header, not a params mapping" % label)
    if re.search(r"(?i)\bparams\s*=\s*[A-Za-z_][A-Za-z0-9_]*\b", text):
        failures.append("%s: key must be a request header, not a params variable" % label)
    if re.search(r"(?i)\bparams\s*=\s*\[", text):
        failures.append("%s: key must be a request header, not a params list" % label)
    if re.search(r"(?i)\bparams\s*\.\s*(?:append|extend|update|setdefault)\s*\(", text):
        failures.append("%s: key must be a request header, not a params list" % label)
    if re.search(r"(?i)\bparams\s*\[", text):
        failures.append("%s: key must be a request header, not a params mapping" % label)
    if re.search(r"\*\*\s*(?:kwargs|params|options|extra|query|request_kwargs|kw|opts|\{)", text):
        failures.append("%s: key must be a request header, not a spread argument" % label)
    if re.search(r"(?i)\burlencode\s*\(", text):
        failures.append("%s: key must be a request header, not a urlencode query" % label)
    if re.search(r"(?i)\bauth\s*=", text):
        failures.append("%s: httpx auth is not the security-scheme header" % label)
    if re.search(r"(?i)\b(?:HTTPBasicAuth|BasicAuth)\s*\(", text):
        failures.append("%s: httpx auth is not the security-scheme header" % label)
    if re.search(r"(?i)\.auth\s*=", text):
        failures.append("%s: httpx auth is not the security-scheme header" % label)
    if re.search(r"(?i)\bparams\s*=\s*\(", text):
        failures.append("%s: key must be a request header, not a params tuple" % label)
    if re.search(r"(?i)(?:\bs\.params\b|\.params\b)", text):
        failures.append("%s: key must be a request header, not an attribute params" % label)
    if re.search(r"(?i)\bcookies\s*=", text):
        failures.append("%s: key must be a request header, not cookies" % label)
    if re.search(
        r"(?i)\b(?:data|json)\s*=\s*\{[^}]*(?:x[-_]kavara[-_]key|api_key|\bkey\b|Authorization)",
        text,
    ):
        failures.append("%s: key must be a request header, not a body field" % label)
    if re.search(r"""(?i)['"]api_key['"]\s*:""", text):
        failures.append("%s: key must be a request header, not a body field" % label)
    if re.search(r"""(?i)\b(?:data|json)\s*=\s*['"][^'"]*\bkey\s*=""", text):
        failures.append("%s: key must be a request header, not a body field" % label)
    if re.search(r"""(?i)--data(?:-raw|-binary)?(?:\s+|=)['"][^'"]*\bkey\s*=""", text):
        failures.append("%s: key must be a request header, not a body field" % label)
    if re.search(r"(?i)\bdict\s*\([^)]*\b(?:key|api_key)\s*=", text):
        failures.append("%s: key must be a request header, not a body field" % label)
    if re.search(
        r"(?i)\b(?:data|json|cookies)\s*=\s*[\[(][^\]\)]*(?:x[-_]kavara[-_]key|\bkey\b|Authorization)",
        text,
    ):
        failures.append("%s: key must be a request header, not a body field" % label)
    if re.search(
        r"(?i)\[\s*\(\s*['\"](?:authorization|x-kavara-key|key)['\"]",
        text,
    ):
        failures.append("%s: key must be a request header, not a header tuple" % label)
    if re.search(r"(?i)['\"]Authorization['\"]\s*:", text):
        failures.append("%s: Authorization is not a security-scheme header" % label)
    if re.search(r"""(?i)headers\s*\[\s*['"]Authorization['"]\s*\]\s*=""", text):
        failures.append("%s: Authorization is not a security-scheme header" % label)
    if re.search(
        r"""(?is)headers\s*\.\s*update\s*\([^)]*(?:X-Kavara-Key|Authorization|\bkey\b)""",
        text,
    ):
        failures.append("%s: headers.update must not add a key or Authorization" % label)
    return failures


def check_piece(text, spec, label):
    failures = []
    if KEY_LITERAL.search(text):
        failures.append("%s: sample contains a key literal" % label)
    failures.extend(misplaced_secret(text, label))
    failures.extend(check_routes(text, spec, label))
    base = assigned_base(text)
    static_headers, conditional_type = python_headers(text)
    for method, path, body in python_calls(text):
        headers = dict(static_headers)
        if body is not None and conditional_type and "Content-Type" not in headers:
            headers["Content-Type"] = conditional_type
        url = None
        if base and path.startswith("/"):
            url = base.rstrip("/") + path
        failures.extend(validate_call(method, path, url, headers, body, None, spec, label))
    for command in curl_commands(text):
        if "error" in command:
            failures.append("%s: %s" % (label, command["error"]))
            continue
        if command.get("basic"):
            failures.append("%s: curl basic auth is not the security scheme" % label)
        for item in command.get("url_query") or []:
            if re.search(r"(?i)X-Kavara-Key", item):
                failures.append("%s: X-Kavara-Key must be a request header, not --url-query" % label)
        raw = command["url"] or ""
        url = resolve_url(raw, text) if raw else None
        path = ""
        if raw.startswith("${BASE_URL}"):
            path = normalise(raw[len("${BASE_URL}"):].split("?", 1)[0])
        elif url:
            path = normalise(urlsplit(url).path)
        elif raw.startswith("/"):
            path = normalise(raw.split("?", 1)[0])
        if command["output"] is None:
            failures.append("%s: curl sample must use -o file" % label)
        failures.extend(validate_call(
            command["method"], path, url, command["headers"], command["data"],
            command["output"], spec, label,
        ))
    return failures


def code_pieces(text):
    """Yield (kind, info, body, start, end) for fences and inline spans."""
    spans = []
    for match in FENCE_RE.finditer(text):
        info = (match.group("info") or "").strip()
        kind = "fence"
        spans.append((match.start(), match.end()))
        yield kind, info, match.group("body"), match.start(), match.end()
    masked = list(text)
    for start, end in spans:
        for index in range(start, end):
            masked[index] = " "
    masked_text = "".join(masked)
    for match in INLINE_RE.finditer(masked_text):
        yield "inline", "", match.group(1), match.start(), match.end()


def scan_text(text, spec, label):
    failures = []
    for _kind, _info, body, start, _end in code_pieces(text):
        line_no = text.count("\n", 0, start) + 1
        failures.extend(check_piece(body, spec, "%s:%s" % (label, line_no)))
    return failures


def digest_path_for(spec_path):
    spec_path = Path(spec_path)
    root = spec_path.parent.parent if spec_path.parent.name == "docs" else spec_path.parent
    return root / DIGEST_RELATIVE


def read_expected_digest(path):
    path = Path(path)
    if not path.is_file():
        return None, "vendored spec digest is missing"
    try:
        text = path.read_text(encoding="utf-8").strip()
    except OSError:
        return None, "vendored spec digest is missing"
    if re.fullmatch(r"[0-9a-f]{64}", text) is None:
        return None, "vendored spec digest is not 64 hex"
    return text, None


def check_digest(spec_path, digest_path=None):
    """Compare the vendored spec with the stored digest. Missing input is an error."""
    spec_path = Path(spec_path)
    if digest_path is None:
        digest_path = digest_path_for(spec_path)
    if not spec_path.is_file():
        return ["vendored spec is missing"]
    try:
        document = json.loads(spec_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return ["vendored spec is not valid JSON"]
    if not isinstance(document, dict):
        return ["vendored spec is not a JSON object"]
    try:
        actual = spec_fingerprint(document)
        spec = Spec(document)
    except Exception:
        return ["vendored spec digest could not be computed"]
    expected, error = read_expected_digest(digest_path)
    failures = []
    if error:
        failures.append(error)
    elif actual != expected:
        failures.append("vendored spec digest does not match")
    if spec.public_base != PUBLIC_API_BASE:
        failures.append("vendored server URL is not the public api base")
    for path_item in spec.allowed_paths:
        if blocked(path_item):
            failures.append("vendored spec publishes a blocked path")
    if not spec.security_headers:
        failures.append("vendored spec has no header security scheme")
    return failures


def digest_rc(spec_path, digest_path=None):
    """Exit status for a digest comparison. Non-zero when the spec does not match."""
    try:
        failures = check_digest(spec_path, digest_path)
    except Exception:
        return 1
    return 1 if failures else 0


INVISIBLE = dict.fromkeys(map(ord, "\u200b\u200c\u200d\ufeff\u2060\u180e\u00ad\u2061\u2062\u2063"), None)
CONFUSABLES = str.maketrans({
    "\u0430": "a", "\u0435": "e", "\u043e": "o", "\u0440": "p", "\u0441": "c",
    "\u0443": "y", "\u0445": "x", "\u0456": "i", "\u0458": "j", "\u04bb": "h",
    "\u0501": "d", "\u0261": "g", "\u03bf": "o", "\u03b1": "a", "\u03c1": "p",
})


def normalize_text(text):
    """NFKC, casefold, drop invisible characters, decode encodings, fold confusables."""
    if text is None:
        return ""
    text = str(text)
    for _ in range(8):
        decoded = html.unescape(unquote_plus(text))
        if decoded == text:
            break
        text = decoded
    text = unicodedata.normalize("NFKC", text).casefold()
    text = text.translate(INVISIBLE)
    return text.translate(CONFUSABLES)


HYPHEN_VARIANTS = str.maketrans({
    "_": "-",
    "\u00ad": "-",
    "\u2010": "-",
    "\u2011": "-",
    "\u2012": "-",
    "\u2013": "-",
    "\u2014": "-",
    "\u2015": "-",
    "\u2212": "-",
    "\ufe63": "-",
    "\uff0d": "-",
})


def fold_for_terms(text):
    """NFKC, then treat hyphen, underscore and non-breaking hyphen as one mark."""
    return normalize_text(text).translate(HYPHEN_VARIANTS)


def terms_from_env(raw=None):
    """One secret entry per line, trimmed. Blank lines are ignored.

    A line that starts with ``/`` is a route. An exact entry matches when its
    segments sit at the end of a path, so a mount prefix is allowed. A trailing
    ``*`` also matches when further segments follow. A partial segment does not
    match. Normalisation resolves ``.`` and ``..``, drops a parameter suffix,
    and removes dashes and dots inside a segment. A leading version segment
    matches any version. The base64 and rot13 forms of the whole path are
    checked too. ``short:`` does not apply to a route.

    ``short:`` (any case) marks a short root, matched on a token boundary.
    A one-letter short root, or a short root that itself starts with
    ``short:``, is rejected. The error text does not contain the entry.
    Every other non-blank line is a long root. Parts split on that term's own
    separators match in order with any run of separators between them, and the
    parts concatenated with no separator also match, including inside a longer
    word. A term that has no separator of its own does not match two adjacent
    words. Length is not used.
    """
    if raw is None:
        raw = os.environ.get(SECRET_NAME)
    if raw is None or not str(raw).strip():
        return None, MISSING_SECRET
    entries = []
    for line in str(raw).splitlines():
        line = line.strip()
        if not line:
            continue
        if line.lower().startswith(SHORT_PREFIX):
            root = line[len(SHORT_PREFIX):].strip()
            if len(root) < 2 or root.lower().startswith(SHORT_PREFIX):
                return None, "short root is not accepted"
            if root.startswith("/"):
                return None, "short root is not accepted"
            entries.append(("bound", root))
            continue
        if line.startswith("/"):
            entries.append(("route", line))
            continue
        entries.append(("any", line))
    if not entries:
        return None, MISSING_SECRET
    return entries, None


def _as_entries(entries, shorts=None):
    if entries is None:
        parsed = []
    elif entries and isinstance(entries[0], str):
        parsed = [("route" if item.startswith("/") else "any", item) for item in entries]
    else:
        parsed = list(entries)
    for item in shorts or []:
        parsed.append(("bound", item))
    return parsed


def _boundary(folded, needle):
    return re.search("(?<![0-9a-z])" + re.escape(needle) + "(?![0-9a-z])", folded) is not None


@functools.lru_cache(maxsize=None)
def _b64_forms(term):
    raw = term.encode("utf-8")
    forms = []
    standard = getattr(base64, "b64" + "encode")
    urlsafe = getattr(base64, "urlsafe_" + "b64" + "encode")
    for encoded in (standard(raw), urlsafe(raw)):
        form = encoded.decode("ascii")
        forms.append(form)
        forms.append(form.rstrip("="))
    return forms


def _rot13(text):
    out = []
    for char in text:
        if "a" <= char <= "z":
            out.append(chr((ord(char) - 97 + 13) % 26 + 97))
        elif "A" <= char <= "Z":
            out.append(chr((ord(char) - 65 + 13) % 26 + 65))
        else:
            out.append(char)
    return "".join(out)


def _term_parts(term):
    folded = fold_for_terms(term)
    return [part for part in re.split(r"[-\s]+", folded) if part]


@functools.lru_cache(maxsize=None)
def _compiled_part(parts):
    """Long roots match inside a longer word. Separators sit only at the term's breaks."""
    gap = r"[\s\-]+"
    body = gap.join(re.escape(part) for part in parts)
    return re.compile(body)


def _part_pattern(parts):
    return _compiled_part(tuple(parts))


def _strip_route_tail(path):
    """Drop a query, a fragment, a parameter suffix, and a trailing slash."""
    path = path.split("#", 1)[0].split("?", 1)[0].split(";", 1)[0]
    if len(path) > 1:
        path = path.rstrip("/")
    return path


_VERSION_SEGMENT = re.compile(r"v[0-9]+\Z")


def _fold_segment(segment):
    return "".join(char for char in segment if not char.isspace() and char not in "-.")


def _path_segments(path):
    """Resolve '.' and '..' segments, then fold dashes and dots inside a name."""
    parts = []
    for segment in _strip_route_tail(path).split("/"):
        if segment == "" or segment == ".":
            continue
        if segment == "..":
            if parts:
                parts.pop()
            continue
        folded = _fold_segment(segment)
        if folded:
            parts.append(folded)
    return parts


@functools.lru_cache(maxsize=None)
def _entry_info(term):
    text = fold_for_terms(term).strip()
    prefix = text.endswith("*")
    if prefix:
        text = text[:-1]
    raw = []
    for segment in _strip_route_tail(text).split("/"):
        if segment == "" or segment == ".":
            continue
        if segment == "..":
            if raw:
                raw.pop()
            continue
        raw.append(segment)
    versioned = bool(raw) and _VERSION_SEGMENT.fullmatch(raw[0]) is not None
    segments = tuple(folded for folded in (_fold_segment(part) for part in raw) if folded)
    return segments, prefix, versioned


def _slice_match(found, entry, versioned):
    if len(found) != len(entry) or not entry:
        return False
    for index, (got, want) in enumerate(zip(found, entry)):
        if index == 0 and versioned:
            if _VERSION_SEGMENT.fullmatch(got) is None:
                return False
        elif got != want:
            return False
    return True


def _route_match_segments(found, entry, prefix, versioned):
    if not entry or len(found) < len(entry):
        return False
    if prefix:
        last = len(found) - len(entry)
        for start in range(last + 1):
            if _slice_match(found[start:start + len(entry)], entry, versioned):
                return True
        return False
    return _slice_match(found[len(found) - len(entry):], entry, versioned)


_URL_RE = re.compile(r"https?://[^\s<>()\[\]\"']+")
_HOST_PATH_RE = re.compile(
    r"(?<![:/\w])(?:[a-z0-9](?:[-a-z0-9]*[a-z0-9])?\.)+[a-z]{2,}(?::[0-9]+)?(/[^\s<>()\[\]\"']+)"
)
_BARE_PATH_RE = re.compile(r"(?<![0-9a-z])(/[a-z0-9][^\s<>()\[\]\"']*)")


def _paths_in(text):
    """Paths from full URLs, links, autolinks, host/path forms, and bare paths."""
    found = []
    for match in _URL_RE.finditer(text):
        raw = match.group(0).rstrip(".,;")
        path = urlsplit(raw).path
        if path:
            found.append((_strip_route_tail(path), _line_of(text, match.start())))
    for match in _HOST_PATH_RE.finditer(text):
        found.append((_strip_route_tail(match.group(1)), _line_of(text, match.start(1))))
    for match in _BARE_PATH_RE.finditer(text):
        found.append((_strip_route_tail(match.group(1)), _line_of(text, match.start())))
    return found


_QUOTED = re.compile(
    r"""(?P<f>[fF])?(?P<q>')(?P<body>(?:\\.|[^'\\])*)'"""
    r"""|(?P<f2>[fF])?(?P<q2>")(?P<body2>(?:\\.|[^"\\])*)\""""
)


def _literal_body(body):
    out = []
    index = 0
    escapes = {"n": "\n", "t": "\t", "r": "\r", "\\": "\\", "'": "'", '"': '"'}
    while index < len(body):
        if body[index] == "\\" and index + 1 < len(body):
            out.append(escapes.get(body[index + 1], body[index + 1]))
            index += 2
            continue
        out.append(body[index])
        index += 1
    return "".join(out)


def _fstring_value(body):
    parts = []
    index = 0
    while index < len(body):
        if body.startswith("{{", index):
            parts.append("{")
            index += 2
            continue
        if body.startswith("}}", index):
            parts.append("}")
            index += 2
            continue
        if body[index] != "{":
            parts.append(body[index])
            index += 1
            continue
        end = body.find("}", index)
        if end < 0:
            return None
        expr = body[index + 1:end].strip()
        if len(expr) >= 2 and expr[0] in "'\"" and expr[-1] == expr[0]:
            parts.append(_literal_body(expr[1:-1]))
        index = end + 1
    return "".join(parts)


def _quoted_value(match):
    if match.group("body") is not None:
        body = match.group("body")
        flag = match.group("f")
    else:
        body = match.group("body2")
        flag = match.group("f2")
    if flag:
        return _fstring_value(body)
    return _literal_body(body)


def _triple_spans(text):
    return [match.span() for match in re.finditer(r'"""[\s\S]*?"""|\'\'\'[\s\S]*?\'\'\'', text)]


def _covered(index, spans):
    return any(start <= index < end for start, end in spans)


def _quoted_matches(text):
    spans = _triple_spans(text)
    return [match for match in _QUOTED.finditer(text) if not _covered(match.start(), spans)]


_CONCAT_GAP = re.compile(
    r"[ \t]*(?:\\(?:\r?\n)[ \t]*)*(?:\+[ \t]*(?:\\(?:\r?\n)[ \t]*)*)?\Z"
)
_COMMA_GAP = re.compile(
    r"[ \t]*(?:\\(?:\r?\n)[ \t]*)*,[ \t]*(?:\\(?:\r?\n)[ \t]*)*\Z"
)
_FORMAT_TAIL = re.compile(r"\s*\.\s*format\s*\(")
_PATH_JOIN = re.compile(r"(?:os\.path\.join|posixpath\.join)\s*\(\s*([^\)]*)\)")
_PERCENT_CALL = re.compile(
    r"""(?P<q>['"])(?P<fmt>(?:\\.|[^\\])*?)(?P=q)\s*%\s*"""
    r"""(?P<arg>\((?:[^()]*)\)|['"](?:\\.|[^\\])*?['"])"""
)
_JOIN_CALL = re.compile(
    r"""(?P<q>['"])(?P<sep>(?:\\.|[^\\])*?)(?P=q)\s*\.\s*join\s*\(\s*[\[(](?P<items>[^\]\)]*)[\]\)]\s*\)"""
)


def _gap_kind(gap):
    if _CONCAT_GAP.fullmatch(gap):
        return "concat"
    if _COMMA_GAP.fullmatch(gap):
        return "comma"
    return None


def _format_pieces(fmt, args):
    """Keep literal text. A placeholder contributes only a literal argument."""
    out = []
    index = 0
    used = 0
    while index < len(fmt):
        if fmt.startswith("{{", index):
            out.append("{")
            index += 2
            continue
        if fmt.startswith("}}", index):
            out.append("}")
            index += 2
            continue
        if fmt[index] != "{":
            out.append(fmt[index])
            index += 1
            continue
        end = fmt.find("}", index)
        if end < 0:
            break
        expr = fmt[index + 1:end].strip()
        if expr == "" or expr.isdigit():
            if used < len(args) and args[used] is not None:
                out.append(args[used])
            used += 1
        elif len(expr) >= 2 and expr[0] in "'\"" and expr[-1] == expr[0]:
            out.append(_literal_body(expr[1:-1]))
        index = end + 1
    return "".join(out)


def _arg_literals(src):
    """Top-level format arguments. None marks a non-literal piece."""
    args = []
    buf = []
    quote = None
    for char in src:
        if quote:
            buf.append(char)
            if char == quote and (len(buf) < 2 or buf[-2] != "\\"):
                quote = None
            continue
        if char in "'\"":
            quote = char
            buf.append(char)
            continue
        if char == ",":
            args.append("".join(buf).strip())
            buf = []
            continue
        buf.append(char)
    tail = "".join(buf).strip()
    if tail:
        args.append(tail)
    values = []
    for piece in args:
        item = _QUOTED.fullmatch(piece) if piece else None
        if item is None or item.group("f") or item.group("f2"):
            values.append(None)
        else:
            values.append(_quoted_value(item))
    return values


def _assembled_routes(text):
    """Best-effort values of routes built from literal pieces. (value, start)."""
    found = []
    spans = _triple_spans(text)
    matches = [match for match in _QUOTED.finditer(text) if not _covered(match.start(), spans)]
    index = 0
    while index < len(matches):
        value = _quoted_value(matches[index])
        start = matches[index].start()
        end = matches[index].end()
        cursor = index + 1
        chained = False
        kind_used = None
        pieces = [] if value is None else [value]
        while cursor < len(matches) and value is not None:
            gap = text[end:matches[cursor].start()]
            kind = _gap_kind(gap)
            if kind is None or (kind_used is not None and kind != kind_used):
                break
            nxt = _quoted_value(matches[cursor])
            if nxt is None:
                break
            kind_used = kind
            pieces.append(nxt)
            value += nxt
            end = matches[cursor].end()
            chained = True
            cursor += 1
        if kind_used == "comma" and pieces and all(part.startswith("/") for part in pieces):
            found.append(("".join(pieces), start))
        elif value and chained and "/" in value:
            found.append((value, start))
        elif value and "/" in value and (matches[index].group("f") or matches[index].group("f2")):
            found.append((value, start))
        index = cursor if chained else index + 1
    for match in matches:
        if match.group("f") or match.group("f2"):
            continue
        tail = text[match.end():]
        marker = _FORMAT_TAIL.match(tail)
        if marker is None:
            continue
        rest = tail[marker.end():]
        close = rest.find(")")
        if close < 0:
            continue
        fmt = _quoted_value(match)
        if not fmt:
            continue
        built = _format_pieces(fmt, _arg_literals(rest[:close]))
        if built and "/" in built:
            found.append((built, match.start()))
    for match in _JOIN_CALL.finditer(text):
        if _covered(match.start(), spans):
            continue
        items = []
        rest = match.group("items")
        ok = True
        while rest.strip():
            rest = rest.lstrip(" \t\r\n,")
            if not rest:
                break
            item = _QUOTED.match(rest)
            if item is None or item.group("f") or item.group("f2"):
                ok = False
                break
            items.append(_quoted_value(item))
            rest = rest[item.end():]
        if ok and items:
            sep = _literal_body(match.group("sep"))
            built = sep.join(items)
            if sep == "/" and built and not built.startswith("/"):
                built = "/" + built
            found.append((built, match.start()))
    for match in _PATH_JOIN.finditer(text):
        if _covered(match.start(), spans):
            continue
        items = []
        rest = match.group(1)
        ok = True
        while rest.strip():
            rest = rest.lstrip(" \t\r\n,")
            if not rest:
                break
            item = _QUOTED.match(rest)
            if item is None or item.group("f") or item.group("f2"):
                ok = False
                break
            items.append(_quoted_value(item))
            rest = rest[item.end():]
        if ok and items:
            found.append((posixpath.join(*items), match.start()))
    for match in _PERCENT_CALL.finditer(text):
        if _covered(match.start(), spans):
            continue
        arg = match.group("arg")
        if arg.startswith("("):
            chunk = arg[1:-1]
        else:
            chunk = arg
        items = []
        rest = chunk
        ok = True
        while rest.strip():
            rest = rest.lstrip(" \t\r\n,")
            if not rest:
                break
            item = _QUOTED.match(rest)
            if item is None or item.group("f") or item.group("f2"):
                ok = False
                break
            items.append(_quoted_value(item))
            rest = rest[item.end():]
        if not ok:
            continue
        applied = _apply_percent(_literal_body(match.group("fmt")), items)
        if applied and "/" in applied:
            found.append((applied, match.start()))
    return found


def _apply_percent(fmt, args):
    out = []
    index = 0
    used = 0
    while index < len(fmt):
        if fmt[index] == "%" and index + 1 < len(fmt):
            nxt = fmt[index + 1]
            if nxt == "%":
                out.append("%")
                index += 2
                continue
            if nxt == "s" and used < len(args):
                out.append(args[used])
                used += 1
                index += 2
                continue
            return None
        out.append(fmt[index])
        index += 1
    if used != len(args):
        return None
    return "".join(out)


def _prepared_routes(text, folded):
    """Paths and assembled literals for one text, computed once per scan."""
    direct = [(_path_segments(path), line_no) for path, line_no in _paths_in(folded)]
    built = []
    for value, start in _assembled_routes(text):
        line_no = _line_of(text, start)
        for path, _line in _paths_in(fold_for_terms(value)):
            built.append((_path_segments(path), line_no))
    return direct, built


def _match_prepared(prepared, entry, prefix, versioned):
    direct, built = prepared
    for segments, line_no in direct:
        if _route_match_segments(segments, entry, prefix, versioned):
            return line_no
    for segments, line_no in built:
        if _route_match_segments(segments, entry, prefix, versioned):
            return line_no
    return None


def _line_of(text, index):
    return text.count("\n", 0, index) + 1


def term_hits(text, entries, shorts=None):
    """Return (line, index) pairs. The term text is not returned."""
    hits = []
    folded = fold_for_terms(text)
    decoded = normalize_text(text)
    parsed = list(_as_entries(entries, shorts))
    prepared = _prepared_routes(text, folded) if any(kind == "route" for kind, _term in parsed) else None
    for index, (kind, term) in enumerate(parsed):
        found_at = None
        if kind == "route":
            entry, prefix, versioned = _entry_info(term)
            if entry and prepared is not None:
                found_at = _match_prepared(prepared, entry, prefix, versioned)
            path = term[:-1] if term.endswith("*") else term
            if found_at is None:
                for form in _b64_forms(path):
                    at = text.find(form)
                    if at >= 0:
                        found_at = _line_of(text, at)
                        break
            if found_at is None:
                rotated = _rot13(path)
                at = decoded.find(normalize_text(rotated))
                if rotated and at >= 0:
                    found_at = _line_of(decoded, at)
        else:
            parts = _term_parts(term)
            if not parts:
                continue
            if len(parts) == 1:
                needle = parts[0]
                if kind == "bound":
                    match = re.search(
                        "(?<![0-9a-z])" + re.escape(needle) + "(?![0-9a-z])",
                        folded,
                    )
                else:
                    match = re.search(re.escape(needle), folded)
                if match:
                    found_at = _line_of(folded, match.start())
            else:
                match = _part_pattern(parts).search(folded)
                if match is None:
                    match = re.search(re.escape("".join(parts)), folded)
                if match:
                    found_at = _line_of(folded, match.start())
            if found_at is None:
                for form in _b64_forms(term):
                    at = text.find(form)
                    if at >= 0:
                        found_at = _line_of(text, at)
                        break
        if found_at is not None:
            hits.append((found_at, index))
    return hits


def _hex_digits():
    # Split so this source file is not one long hex run.
    return set("012345") | set("6789") | set("abc") | set("def")


def _separators():
    return set("._-:") | set(
        "\u00b7\u30fb\uff65\u2010\u2011\u2012\u2013\u2014\u2015\u2212\ufe58\ufe63\uff0d\u2027\u2043"
    )


_ED_TOKEN = "ed" + "25519"


def checked_allow(allow):
    """Allow-list entries are exact whole tokens of digits. No a-f values."""
    if allow is None:
        allow = HEX_ALLOW
    for item in allow:
        if not re.fullmatch(r"[0-9]+", item or ""):
            raise ValueError("allow-list entry must be a digits-only token")
    return allow


_OFFSET_MARK = "\uE000"


def _protect_iso_offsets(text):
    """Keep a +hh:mm offset intact. URL decoding would otherwise turn + into a space."""
    return re.sub(r"(?<=\d)\+(?=\d{2}:\d{2})", _OFFSET_MARK, text)


def _iso_edge(text, index):
    """True when this side does not glue hex onto the date."""
    if index < 0 or index >= len(text):
        return True
    char = text[index]
    if char in _hex_digits() or char in _separators() or ("a" <= char <= "z"):
        return False
    return True


def _mask_iso(text):
    """Blank a standalone strict ISO 8601 date or datetime. Attached hex stays."""

    def date_ok(year, month, day):
        try:
            year_n = int(year)
            if year_n < 1900 or year_n > 2099:
                return False
            datetime.date(year_n, int(month), int(day))
        except ValueError:
            return False
        return True

    def time_ok(hour, minute, second):
        return 0 <= int(hour) <= 23 and 0 <= int(minute) <= 59 and 0 <= int(second) <= 60

    dt = re.compile(
        r"(\d{4})-(\d{2})-(\d{2})[t ](\d{2}):(\d{2}):(\d{2})"
        r"(?:\.(\d{1,6}))?\s?(z|[+-]\d{2}:\d{2}|" + _OFFSET_MARK + r"\d{2}:\d{2})"
    )
    day = re.compile(r"(\d{4})-(\d{2})-(\d{2})")

    def blank_if(match, ok):
        if not ok:
            return match.group(0)
        if not _iso_edge(text, match.start() - 1) or not _iso_edge(text, match.end()):
            return match.group(0)
        return " " * len(match.group(0))

    def dt_sub(match):
        fraction = match.group(7)
        ok = (
            date_ok(match.group(1), match.group(2), match.group(3))
            and time_ok(match.group(4), match.group(5), match.group(6))
            and (fraction is None or len(fraction) <= 6)
        )
        return blank_if(match, ok)

    def day_sub(match):
        return blank_if(match, date_ok(match.group(1), match.group(2), match.group(3)))

    return day.sub(day_sub, dt.sub(dt_sub, text))


def _reduce_token(token, hexdigits, separators):
    """Strip separators and letter gaps inside an otherwise hex token."""
    simplified = "".join(char for char in token if char not in separators)
    if re.fullmatch(r"[0-9a-f]+", simplified or ""):
        return True, simplified
    # One letter-gap of any length, or several single-letter gaps, when every
    # hex piece is at least two characters (abcgdefg01, abggcdef0).
    one_gap = re.fullmatch(r"[0-9a-f]{2,}[g-z]+[0-9a-f]{2,}", simplified or "")
    many = re.fullmatch(r"[0-9a-f]{2,}(?:[g-z][0-9a-f]{2,})+", simplified or "")
    if one_gap or many:
        return True, re.sub(r"[g-z]+", "", simplified)
    runs = re.findall(r"[0-9a-f]+", simplified or "")
    return False, runs


def _mixes(token):
    return any("a" <= char <= "f" for char in token) and any(char.isdigit() for char in token)


def _ed_exempt(text, token):
    """True when every exact occurrence is an alg or kty value."""
    if token != _ED_TOKEN:
        return False
    hexdigits = _hex_digits()
    start = 0
    found = False
    while True:
        index = text.find(token, start)
        if index < 0:
            break
        found = True
        before = text[index - 1] if index else ""
        after = text[index + len(token)] if index + len(token) < len(text) else ""
        if before.isalnum() or after.isalnum():
            return False
        window = text[max(0, index - 48):index]
        if not re.search(r"""['"](?:alg|kty)['"]\s*:\s*['"]\s*$""", window):
            return False
        start = index + len(token)
    return found


def hex_findings(text, allow=None):
    """7+ hex runs after separator stripping. A run with no digit is not a hit.

    Space, tab, slash, and comma join pure hex tokens only when the joined
    run has both an a-f letter and a digit.
    """
    allow = checked_allow(HEX_ALLOW if allow is None else allow)
    text = _mask_iso(normalize_text(_protect_iso_offsets(text)))
    hexdigits = _hex_digits()
    separators = _separators()
    findings = []

    def keep(token):
        if len(token) < 7 or token in allow:
            return
        if not any(char.isdigit() for char in token):
            return
        if _ed_exempt(text, token):
            return
        if token not in findings:
            findings.append(token)

    for line in text.splitlines() or [text]:
        parts = re.split(r"[ \t/,]+", line)
        group = []

        def flush():
            if not group:
                return
            for item in group:
                if len(item) >= 7:
                    keep(item)
            if len(group) >= 2:
                joined = "".join(group)
                if _mixes(joined):
                    keep(joined)
            del group[:]

        for part in parts:
            if not part:
                continue
            pure, value = _reduce_token(part, hexdigits, separators)
            if pure and value:
                group.append(value)
                continue
            flush()
            if not pure:
                for run in value:
                    if len(run) >= 7:
                        keep(run)
        flush()
    return findings


def repo_relative(path, root):
    path = Path(path)
    root = Path(root)
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.name


def is_inside(path, parent):
    try:
        Path(path).resolve().relative_to(Path(parent).resolve())
        return True
    except (ValueError, OSError, RuntimeError):
        return False


def symlink_failure(path, root):
    """None when a link stays inside the tree. A docs link must stay under docs."""
    root = Path(root)
    label = repo_relative(path, root)
    try:
        target = path.resolve(strict=False)
    except (OSError, RuntimeError):
        return "%s: symlink cannot be resolved" % label
    if not is_inside(target, root):
        return "%s: symlink resolves outside the repository" % label
    if label == "docs" or label.startswith("docs/"):
        if not is_inside(target, root / "docs"):
            return "%s: symlink resolves outside docs" % label
    return None


def is_markdown_name(name):
    lower = name.lower()
    return lower.endswith(".markdown") or lower.endswith(".md")


_ACTION_PIN = re.compile(
    r"^[ \t]*(?:-[ \t]+)?uses:[ \t]+[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+@[0-9a-f]{40}"
    r"(?:[ \t]+#[ \t]*v[0-9]+(?:\.[0-9]+)*)?[ \t]*$"
)


def _mask_action_pins(text):
    """A 40-hex pin is exempt only on an exact uses: owner/repo@sha line."""
    kept = []
    for line in text.splitlines(keepends=True):
        ending = ""
        body = line
        if body.endswith("\r\n"):
            ending = "\r\n"
            body = body[:-2]
        elif body.endswith("\n") or body.endswith("\r"):
            ending = body[-1]
            body = body[:-1]
        if _ACTION_PIN.match(body):
            body = re.sub(r"[0-9a-f]{40}", "pin", body, count=1)
        kept.append(body + ending)
    return "".join(kept)


class DuplicateJsonKey(ValueError):
    """A JSON object repeated a key. json.loads would otherwise keep the last one."""


def _reject_duplicate_keys(pairs):
    found = {}
    for key, value in pairs:
        if key in found:
            raise DuplicateJsonKey("duplicate key")
        found[key] = value
    return found


def load_strict_json(text):
    """Parse JSON. A duplicate key at any nesting level is an error."""
    return json.loads(text, object_pairs_hook=_reject_duplicate_keys)


def _skill_folders(root):
    base = Path(root) / ".agents" / "skills"
    if not base.is_dir():
        return set()
    return {item.name for item in base.iterdir() if item.is_dir()}


def lock_errors(text, root):
    """Errors for the skills lock. A duplicate key fails before any exemption."""
    try:
        document = load_strict_json(text)
    except DuplicateJsonKey:
        return ["duplicate key"]
    except ValueError:
        return []
    if not isinstance(document, dict):
        return []
    skills = document.get(LOCK_OBJECT)
    if not isinstance(skills, dict):
        return []
    folders = _skill_folders(root)
    return ["skill folder is missing" for name in skills if name not in folders]


def _mask_lock_hashes(text):
    """Blank only skills.<name>.computedHash when the value is 64 lowercase hex."""
    try:
        document = load_strict_json(text)
    except (DuplicateJsonKey, ValueError):
        return text
    if not isinstance(document, dict):
        return text
    skills = document.get(LOCK_OBJECT)
    if not isinstance(skills, dict):
        return text
    changed = False
    for entry in skills.values():
        if not isinstance(entry, dict) or LOCK_FIELD not in entry:
            continue
        value = entry[LOCK_FIELD]
        if isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value):
            entry[LOCK_FIELD] = ""
            changed = True
    if not changed:
        return text
    return json.dumps(document)


def _workflow_yml(relative):
    """A pin is exempt only in a file directly inside .github/workflows."""
    prefix = ".github/workflows/"
    if not relative.startswith(prefix):
        return False
    name = relative[len(prefix):]
    if not name or "/" in name:
        return False
    return name.endswith(".yml") or name.endswith(".yaml")


def hex_for_path(path, root, text, allow=None):
    """Hex findings for a file. Exemptions are exact paths and exact values."""
    relative = repo_relative(path, root)
    if relative == DIGEST_RELATIVE:
        return []
    if relative == LOCK_RELATIVE:
        text = _mask_lock_hashes(text)
    if _workflow_yml(relative):
        text = _mask_action_pins(text)
    return hex_findings(text, allow)


def iter_markdown(root):
    """Every Markdown file. An escaping symlink is an error, not a skipped file."""
    root = Path(root)
    failures = []
    files = []
    if not root.is_dir():
        return files, ["repository root is missing"]
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        current = Path(dirpath)
        kept = []
        for name in dirnames:
            if name in SKIP_DIRS:
                continue
            candidate = current / name
            if candidate.is_symlink():
                problem = symlink_failure(candidate, root)
                if problem:
                    failures.append(problem)
                    continue
            kept.append(name)
        dirnames[:] = kept
        for name in filenames:
            if not is_markdown_name(name):
                continue
            candidate = current / name
            if candidate.is_symlink():
                problem = symlink_failure(candidate, root)
                if problem:
                    failures.append(problem)
                    continue
            files.append(candidate)
    return files, failures


def read_text_file(path):
    """Return decoded text, or None when the file is binary or unreadable."""
    try:
        raw = path.read_bytes()
    except OSError:
        return None
    if b"\x00" in raw[:8192]:
        return None
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return None


def scan_repository(root=ROOT, terms=None, shorts=None):
    if terms is None and shorts is None:
        terms, error = terms_from_env()
        if error:
            return [error]
    root = Path(root)
    spec_path = root / "docs" / "customer-rest-api.openapi.json"
    failures = list(check_digest(spec_path))
    if failures:
        return failures
    try:
        document = load_document(spec_path)
        spec = Spec(document)
    except (OSError, ValueError, TypeError, AttributeError):
        return ["vendored spec is not valid JSON"]
    if not root.is_dir():
        return failures + ["repository root is missing"]
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        current = Path(dirpath)
        kept = []
        for name in dirnames:
            if name in SKIP_DIRS:
                continue
            candidate = current / name
            if candidate.is_symlink():
                problem = symlink_failure(candidate, root)
                if problem:
                    failures.append(problem)
                    continue
            kept.append(name)
        dirnames[:] = kept
        for name in filenames:
            path = current / name
            label = repo_relative(path, root)
            if path.suffix.lower() in BINARY_SUFFIXES:
                continue
            if path.is_symlink():
                problem = symlink_failure(path, root)
                if problem:
                    failures.append(problem)
                    continue
            text = read_text_file(path)
            if text is None:
                if is_markdown_name(name):
                    failures.append("%s: markdown file is not readable" % label)
                continue
            try:
                label = path.resolve().relative_to(root.resolve()).as_posix()
            except (ValueError, OSError, RuntimeError):
                failures.append("%s: symlink resolves outside the repository" % repo_relative(path, root))
                continue
            if is_markdown_name(name):
                failures.extend(scan_text(text, spec, label))
            if label == LOCK_RELATIVE:
                for problem in lock_errors(text, root):
                    failures.append("%s: %s" % (label, problem))
            for token in hex_for_path(path, root, text):
                failures.append("%s: hex run %s" % (label, token))
            for line_no, index in term_hits(text, terms, shorts):
                failures.append("%s:%s: term %s" % (label, line_no, index))
    quick_path = root / "docs" / "customer-rest-api.md"
    if not quick_path.is_file():
        failures.append("quickstart is missing")
    else:
        quick = quick_path.read_text(encoding="utf-8")
        python_found, curl_found = quickstart_calls(quick, spec)
        if python_found != list(QUICKSTART_CALLS):
            failures.append("quickstart python calls do not match")
        if curl_found != list(QUICKSTART_CALLS):
            failures.append("quickstart curl calls do not match")
    return failures


def quickstart_calls(text, spec):
    python = []
    curl = []
    for _kind, info, body, _start, _end in code_pieces(text):
        lang = info.split()[0].lower() if info else ""
        if lang in {"python", "py"}:
            python.extend((method, normalise(path)) for method, path, _body in python_calls(body))
        if lang in {"bash", "sh", "shell"}:
            for command in curl_commands(body):
                if "error" in command:
                    continue
                raw = command["url"] or ""
                if raw.startswith("${BASE_URL}"):
                    path = normalise(raw[len("${BASE_URL}"):])
                else:
                    path = normalise(urlsplit(resolve_url(raw, body) or "").path)
                curl.append((command["method"], path))
    return python, curl


def balanced(text, start, open_ch, close_ch):
    if start >= len(text) or text[start] != open_ch:
        return None
    depth = 0
    for index in range(start, len(text)):
        if text[index] == open_ch:
            depth += 1
        elif text[index] == close_ch:
            depth -= 1
            if depth == 0:
                return text[start:index + 1]
    return None


def skip_ws(text, index):
    while index < len(text) and text[index] in " \t\r\n":
        index += 1
    return index


def parse_string(text, index):
    if index >= len(text) or text[index] not in "\"'":
        return None, index
    quote = text[index]
    index += 1
    chars = []
    while index < len(text):
        if text[index] == "\\":
            if index + 1 < len(text):
                chars.append(text[index + 1])
            index += 2
            continue
        if text[index] == quote:
            return "".join(chars), index + 1
        chars.append(text[index])
        index += 1
    return None, index


def _slash(*parts):
    return "/" + "/".join(parts)


def _prefixed(name):
    return "/" + name + "*"


def synthetic_secret_lines():
    """Real-shaped list: short roots, one prefix, full paths, and long roots."""
    lines = []
    for root in ("q" + "z" + "q", "q" + "x" + "q", "q" + "v" + "q", "q" + "k" + "q"):
        lines.append("short:" + root)
    lines.append(_prefixed("q" + "z" + "q"))
    lines.append(_slash("qa", "one"))
    lines.append(_slash("qb", "two"))
    lines.append(_slash("qc", "three"))
    for index in range(32):
        lines.append("longroot" + "q" + str(index))
    return lines


class CheckerTests(unittest.TestCase):
    def spec(self):
        return Spec(load_document(OPENAPI_PATH))

    def piece(self, text):
        return check_piece(text, self.spec(), "fixture")

    def wrapped(self, text):
        return scan_text(text, self.spec(), "fixture")

    def independent_digest(self, document):
        """Hash the whole document without using spec_fingerprint or a module constant."""
        blob = json.dumps(document, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()

    def test_vendored_digest_matches_independent_hash(self):
        document = load_document(OPENAPI_PATH)
        self.assertEqual(spec_fingerprint(document), self.independent_digest(document))
        self.assertEqual(check_digest(OPENAPI_PATH), [])

    def test_missing_spec_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            missing = Path(directory) / "absent.json"
            self.assertEqual(check_digest(missing), ["vendored spec is missing"])

    def test_invalid_spec_fails_closed(self):
        terms = self.synthetic_terms()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            docs = root / "docs"
            docs.mkdir()
            spec = docs / "customer-rest-api.openapi.json"
            spec.write_text("not-json", encoding="utf-8")
            self.assertEqual(check_digest(spec), ["vendored spec is not valid JSON"])
            self.assertEqual(
                scan_repository(root, terms=terms),
                ["vendored spec is not valid JSON"],
            )
            spec.write_text("[]", encoding="utf-8")
            self.assertEqual(check_digest(spec), ["vendored spec is not a JSON object"])
            self.assertEqual(
                scan_repository(root, terms=terms),
                ["vendored spec is not a JSON object"],
            )

    def test_schema_edit_changes_digest(self):
        document = load_document(OPENAPI_PATH)
        original = self.independent_digest(document)
        edited = json.loads(json.dumps(document))
        node = edited["components"]["schemas"]["CreateRequest"]["properties"]["hyperparameters"]
        node["properties"]["visible_nodes"]["minimum"] = 0
        self.assertNotEqual(self.independent_digest(edited), original)
        self.assertNotEqual(spec_fingerprint(edited), spec_fingerprint(document))

    def test_full_url(self):
        text = "```bash\ncurl https://api.kavara.ai/v1/kirk-api/synthetic-extra -o out.json\n```\n"
        self.assertTrue(self.wrapped(text))

    def test_var_path(self):
        text = "```bash\nBASE_URL=\"https://api.kavara.ai\"\ncurl --url \"${BASE_URL}/v1/kirk-api/synthetic-extra\" -o out.json\n```\n"
        self.assertTrue(self.wrapped(text))

    def test_untagged_fence(self):
        text = "```\nhttps://api.kavara.ai/v1/kirk-api/synthetic-extra\n```\n"
        self.assertTrue(self.wrapped(text))

    def test_console_fence(self):
        text = "```console\ncurl https://api.kavara.ai/v1/kirk-api/synthetic-extra\n```\n"
        self.assertTrue(self.wrapped(text))

    def test_js_fence(self):
        text = "```js\nfetch(\"https://api.kavara.ai/v1/kirk-api/synthetic-extra\")\n```\n"
        self.assertTrue(self.wrapped(text))

    def test_tilde_fence(self):
        text = "~~~\ncurl https://api.kavara.ai/v1/kirk-api/synthetic-extra\n~~~\n"
        self.assertTrue(self.wrapped(text))

    def test_json_body(self):
        text = "```json\n{\"path\": \"/v1/kirk-api/synthetic-extra\"}\n```\n"
        self.assertTrue(self.wrapped(text))

    def test_inline_curl(self):
        text = "Run `curl https://api.kavara.ai/v1/kirk-api/synthetic-extra` now.\n"
        self.assertTrue(self.wrapped(text))

    def test_unknown_fence_type(self):
        text = "```not-a-language\nGET https://api.kavara.ai/v1/kirk-api/synthetic-extra\n```\n"
        self.assertTrue(self.wrapped(text))

    def test_authorization_python(self):
        text = "\n".join([
            'BASE_URL = "https://api.kavara.ai"',
            'headers = {"X-Kavara-Key": API_KEY, "Authorization": "Bearer x"}',
            'call("GET", "/v1/kirk-api/health")',
        ])
        self.assertTrue(any("Authorization" in item for item in self.piece(text)))

    def test_authorization_curl(self):
        text = "\n".join([
            'BASE_URL="https://api.kavara.ai"',
            'curl --request GET --url "${BASE_URL}/v1/kirk-api/health" '
            '--header "X-Kavara-Key: ${KIP_API_KEY}" --header "Authorization: Bearer x" -o out.json',
        ])
        self.assertTrue(any("Authorization" in item for item in self.piece(text)))

    def test_wrong_body_field(self):
        text = "\n".join([
            'BASE_URL = "https://api.kavara.ai"',
            'headers = {"X-Kavara-Key": API_KEY}',
            'if payload is not None:',
            '    headers["Content-Type"] = "application/json"',
            'call("POST", "/v1/kirk-api/create", {"hyperparameters": {"visible_nodes": 1}, "extra": 1})',
        ])
        self.assertTrue(any("unknown field" in item for item in self.piece(text)))

    def test_visible_nodes_zero(self):
        text = "\n".join([
            'BASE_URL = "https://api.kavara.ai"',
            'headers = {"X-Kavara-Key": API_KEY}',
            'if payload is not None:',
            '    headers["Content-Type"] = "application/json"',
            'call("POST", "/v1/kirk-api/create", {"hyperparameters": {"visible_nodes": 0}})',
        ])
        self.assertTrue(any("minimum" in item for item in self.piece(text)))

    def test_text_plain(self):
        text = "\n".join([
            'BASE_URL = "https://api.kavara.ai"',
            'headers = {"X-Kavara-Key": API_KEY, "Content-Type": "text/plain"}',
            'call("POST", "/v1/kirk-api/create", {"hyperparameters": {"visible_nodes": 1}})',
        ])
        self.assertTrue(any("text/plain" in item for item in self.piece(text)))

    def test_key_in_curl_query(self):
        text = "\n".join([
            'BASE_URL="https://api.kavara.ai"',
            'curl --request GET --url "${BASE_URL}/v1/kirk-api/health?X-Kavara-Key=abc" '
            '--header "X-Kavara-Key: ${KIP_API_KEY}" -o out.json',
        ])
        self.assertTrue(any("query string" in item for item in self.piece(text)))

    def test_key_in_python_params(self):
        text = "\n".join([
            'BASE_URL = "https://api.kavara.ai"',
            'headers = {"X-Kavara-Key": API_KEY}',
            'params = {"X-Kavara-Key": API_KEY}',
            'call("GET", "/v1/kirk-api/health")',
        ])
        self.assertTrue(any("params" in item for item in self.piece(text)))

    def test_key_in_url_query_flag(self):
        text = "\n".join([
            'BASE_URL="https://api.kavara.ai"',
            'curl --request GET --url "${BASE_URL}/v1/kirk-api/health" '
            '--url-query "X-Kavara-Key=abc" --header "X-Kavara-Key: ${KIP_API_KEY}" -o out.json',
        ])
        self.assertTrue(any("--url-query" in item for item in self.piece(text)))

    def test_curl_basic_auth(self):
        text = "\n".join([
            'BASE_URL="https://api.kavara.ai"',
            'curl --request GET --url "${BASE_URL}/v1/kirk-api/health" '
            '--header "X-Kavara-Key: ${KIP_API_KEY}" -u "user:pass" -o out.json',
        ])
        self.assertTrue(any("basic auth" in item for item in self.piece(text)))

    def test_authorization_assigned_later(self):
        text = "\n".join([
            'BASE_URL = "https://api.kavara.ai"',
            'headers = {"X-Kavara-Key": API_KEY}',
            'headers["Authorization"] = "Bearer x"',
            'call("GET", "/v1/kirk-api/health")',
        ])
        self.assertTrue(any("Authorization" in item for item in self.piece(text)))

    def test_query_key_parameter(self):
        text = "\n".join([
            'BASE_URL="https://api.kavara.ai"',
            'curl --request GET --url "${BASE_URL}/v1/kirk-api/health?key=abc" '
            '--header "X-Kavara-Key: ${KIP_API_KEY}" -o out.json',
        ])
        self.assertTrue(any("query string" in item for item in self.piece(text)))

    def test_url_query_key_parameter(self):
        text = "\n".join([
            'BASE_URL="https://api.kavara.ai"',
            'curl --request GET --url "${BASE_URL}/v1/kirk-api/health" '
            '--url-query "key=abc" --header "X-Kavara-Key: ${KIP_API_KEY}" -o out.json',
        ])
        self.assertTrue(any("--url-query" in item for item in self.piece(text)))

    def test_get_data_urlencode(self):
        text = "\n".join([
            'BASE_URL="https://api.kavara.ai"',
            'curl -G --data-urlencode "key=abc" --request GET '
            '--url "${BASE_URL}/v1/kirk-api/health" --header "X-Kavara-Key: ${KIP_API_KEY}" -o out.json',
        ])
        self.assertTrue(any("data-urlencode" in item for item in self.piece(text)))

    def test_python_params_key(self):
        text = "\n".join([
            'BASE_URL = "https://api.kavara.ai"',
            'headers = {"X-Kavara-Key": API_KEY}',
            'params = {"key": "abc"}',
            'call("GET", "/v1/kirk-api/health")',
        ])
        self.assertTrue(any("params" in item for item in self.piece(text)))

    def test_python_params_variable(self):
        text = "\n".join([
            'BASE_URL = "https://api.kavara.ai"',
            'headers = {"X-Kavara-Key": API_KEY}',
            'q = {"limit": 1}',
            'params = q',
            'call("GET", "/v1/kirk-api/health")',
        ])
        self.assertTrue(any("params variable" in item for item in self.piece(text)))

    def test_python_params_pair_list(self):
        text = "\n".join([
            'BASE_URL = "https://api.kavara.ai"',
            'headers = {"X-Kavara-Key": API_KEY}',
            'params = [("key", API_KEY)]',
            'call("GET", "/v1/kirk-api/health")',
        ])
        self.assertTrue(any("params list" in item for item in self.piece(text)))

    def test_kwargs_spread(self):
        text = "\n".join([
            'BASE_URL = "https://api.kavara.ai"',
            'headers = {"X-Kavara-Key": API_KEY}',
            'client.get(BASE_URL + "/v1/kirk-api/health", **kwargs)',
        ])
        self.assertTrue(any("spread argument" in item for item in self.piece(text)))

    def test_urlencode_query(self):
        text = "\n".join([
            'BASE_URL = "https://api.kavara.ai"',
            'headers = {"X-Kavara-Key": API_KEY}',
            'urlencode({"key": API_KEY})',
            'call("GET", "/v1/kirk-api/health")',
        ])
        self.assertTrue(any("urlencode" in item for item in self.piece(text)))

    def test_percent_encoded_query(self):
        text = "\n".join([
            'BASE_URL = "https://api.kavara.ai"',
            'headers = {"X-Kavara-Key": API_KEY}',
            'call("GET", "/v1/kirk-api/health%3Fkey%3Dabc")',
        ])
        self.assertTrue(any("query string" in item for item in self.piece(text)))

    def test_httpx_auth_is_rejected(self):
        text = "\n".join([
            'BASE_URL = "https://api.kavara.ai"',
            'headers = {"X-Kavara-Key": API_KEY}',
            'httpx.get(BASE_URL + "/v1/kirk-api/health", auth=creds)',
        ])
        self.assertTrue(any("httpx auth" in item for item in self.piece(text)))

    def test_more_key_carriers(self):
        common = [
            'BASE_URL = "https://api.kavara.ai"',
            'headers = {"X-Kavara-Key": API_KEY}',
        ]
        samples = [
            common + ['params = ("key", API_KEY)', 'call("GET", "/v1/kirk-api/health")'],
            common + ['client.get(BASE_URL + "/v1/kirk-api/health", **opts)'],
            common + ['session.params = {"key": API_KEY}', 'call("GET", "/v1/kirk-api/health")'],
            common + ['cookies = {"key": API_KEY}', 'call("GET", "/v1/kirk-api/health")'],
            common + ['data = {"key": API_KEY}', 'call("GET", "/v1/kirk-api/health")'],
            common + ['json = {"Authorization": API_KEY}', 'call("GET", "/v1/kirk-api/health")'],
        ]
        for sample in samples:
            self.assertTrue(self.piece("\n".join(sample)))

    def test_headers_update_adds_authorization(self):
        text = "\n".join([
            'BASE_URL = "https://api.kavara.ai"',
            'headers = {"X-Kavara-Key": API_KEY}',
            'headers.update({"Authorization": "Bearer x"})',
            'call("GET", "/v1/kirk-api/health")',
        ])
        self.assertTrue(any("headers.update" in item for item in self.piece(text)))

    def test_headers_update_adds_key(self):
        text = "\n".join([
            'BASE_URL = "https://api.kavara.ai"',
            'headers = {"Content-Type": "application/json"}',
            'headers.update({"X-Kavara-Key": API_KEY})',
            'call("GET", "/v1/kirk-api/health")',
        ])
        self.assertTrue(any("headers.update" in item for item in self.piece(text)))

    def test_unrelated_absolute_url_is_not_a_sample(self):
        host = "example" + ".invalid"
        text = "```\npip install torch --index-url https://%s/wheels/cpu\n```\n" % host
        self.assertEqual(self.wrapped(text), [])

    def test_oauth2_bearer(self):
        text = "\n".join([
            'BASE_URL="https://api.kavara.ai"',
            'curl --request GET --url "${BASE_URL}/v1/kirk-api/health" '
            '--oauth2-bearer abc --header "X-Kavara-Key: ${KIP_API_KEY}" -o out.json',
        ])
        self.assertTrue(any("oauth2 bearer" in item for item in self.piece(text)))

    def test_unpublished_sample(self):
        self.assertTrue(self.piece("curl https://api.kavara.ai" + SYNTHETIC_PATH + " -o out.json"))

    def test_good_python_call(self):
        text = "\n".join([
            'BASE_URL = "https://api.kavara.ai"',
            'headers = {"X-Kavara-Key": API_KEY}',
            'if payload is not None:',
            '    headers["Content-Type"] = "application/json"',
            'call("GET", "/v1/kirk-api/health")',
            'call("POST", "/v1/kirk-api/create", {"hyperparameters": {"visible_nodes": 1}})',
        ])
        self.assertEqual(self.piece(text), [])

    def test_documentation_address_is_not_the_api_base(self):
        text = "\n".join([
            'BASE_URL = "https://192.0.2.1"',
            'headers = {"X-Kavara-Key": API_KEY}',
            'call("GET", "/v1/kirk-api/health")',
        ])
        self.assertTrue(any("base 0" in item for item in self.piece(text)))
        self.assertFalse(any("192.0.2.1" in item for item in self.piece(text)))

    def test_security_scheme_change(self):
        document = load_document(OPENAPI_PATH)
        mutated = json.loads(json.dumps(document))
        mutated["components"]["securitySchemes"]["kavaraKey"]["name"] = "X-Other-Key"
        with tempfile.TemporaryDirectory() as directory:
            tmp = Path(directory) / "openapi.json"
            tmp.write_text(json.dumps(mutated), encoding="utf-8")
            reloaded = load_document(tmp)
        self.assertNotEqual(self.independent_digest(reloaded), self.independent_digest(document))
        self.assertNotEqual(spec_fingerprint(reloaded), spec_fingerprint(document))

    def test_hex_runs(self):
        pieces = ["a", "b", "c", "d", "e", "f", "0"]
        self.assertTrue(hex_findings("token " + "abc" + "def" + "0", allow=frozenset()))
        self.assertTrue(hex_findings("-".join(pieces), allow=frozenset()))
        self.assertTrue(hex_findings("_".join(pieces), allow=frozenset()))
        self.assertTrue(hex_findings("\u2013".join(pieces), allow=frozenset()))
        self.assertTrue(hex_findings(".".join(pieces), allow=frozenset()))
        self.assertTrue(hex_findings("\u00b7".join(pieces), allow=frozenset()))
        self.assertTrue(hex_findings("ab cd ef " + "01", allow=frozenset()))
        self.assertTrue(hex_findings("ab\tcd\tef\t" + "01", allow=frozenset()))
        self.assertTrue(hex_findings("abc " + "def " + "0", allow=frozenset()))
        self.assertTrue(hex_findings("12:" + "34:" + "56:" + "7", allow=frozenset()))
        self.assertTrue(hex_findings("abc" + "g" + "def" + "0", allow=frozenset()))
        self.assertTrue(hex_findings(".".join(["1", "2", "3", "4", "5", "6", "7"]), allow=frozenset()))
        self.assertFalse(hex_findings("workload added under 6 W"))
        self.assertFalse(hex_findings("for T in 1 2 4 8 16 32 64; do"))
        self.assertFalse(hex_findings("label example-revision"))
        self.assertFalse(hex_findings("body cap 8388608"))

    def test_iso_dates_are_exempt_and_a_near_miss_is_not(self):
        valid_day = "2026" + "-07-" + "28"
        valid_when = "2026" + "-07-" + "28T" + "09:" + "30:" + "00Z"
        near = "2026" + "-07-" + "28T" + "99:" + "99:" + "99"
        self.assertFalse(hex_findings("noted " + valid_day + " in prose"))
        self.assertFalse(hex_findings("noted " + valid_when + " in prose"))
        self.assertTrue(hex_findings("noted " + near + " in prose", allow=frozenset()))

    def test_allow_list_rejects_letters_and_is_exact(self):
        with self.assertRaises(ValueError):
            hex_findings("token", allow=frozenset(["abc"]))
        self.assertFalse(hex_findings("8388608"))
        self.assertTrue(hex_findings("8388608" + "1", allow=frozenset(["8388608"])))

    def test_curve_token_is_exempt_only_in_alg_or_kty(self):
        token = "ed" + "25519"
        self.assertFalse(hex_findings('{"alg": "%s"}' % token))
        self.assertFalse(hex_findings('{"kty": "%s"}' % token))
        self.assertTrue(hex_findings("see %s now" % token, allow=frozenset()))

    def synthetic_terms(self):
        long_term = "synth" + "token"
        host = "preview" + "host" + "test"
        short_term = "zz"
        return [long_term, host, short_term]

    def minimal_repo(self, root):
        docs = root / "docs"
        docs.mkdir()
        shutil.copy(OPENAPI_PATH, docs / "customer-rest-api.openapi.json")
        shutil.copy(ROOT / "docs" / "customer-rest-api.md", docs / "customer-rest-api.md")
        digest = root / DIGEST_RELATIVE
        digest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(ROOT / DIGEST_RELATIVE, digest)
        return docs

    def test_missing_secret_fails_closed(self):
        previous = os.environ.pop(SECRET_NAME, None)
        try:
            self.assertEqual(scan_repository(ROOT), [MISSING_SECRET])
        finally:
            if previous is not None:
                os.environ[SECRET_NAME] = previous

    def test_short_root_needs_a_boundary(self):
        short_term = "zz"
        self.assertEqual(
            term_hits("prefix " + short_term + " suffix", [], shorts=[short_term]),
            [(1, 0)],
        )
        self.assertEqual(term_hits("aa" + short_term + "bb", [], shorts=[short_term]), [])

    def test_secret_lines_are_trimmed_and_blank_lines_ignored(self):
        previous = os.environ.get(SECRET_NAME)
        os.environ[SECRET_NAME] = "  alpha  \n\n  \n short: zz \n"
        try:
            entries, error = terms_from_env()
        finally:
            if previous is None:
                os.environ.pop(SECRET_NAME, None)
            else:
                os.environ[SECRET_NAME] = previous
        self.assertIsNone(error)
        self.assertEqual(entries, [("any", "alpha"), ("bound", "zz")])

    def test_concatenated_words_are_not_a_term(self):
        term = "synth" + "token"
        self.assertEqual(term_hits("synth token", [term]), [])
        self.assertTrue(term_hits("see " + term + " now", [term]))

    def test_internal_break_allows_space_or_hyphen(self):
        term = "synth" + "-" + "token"
        self.assertTrue(term_hits("synth token", [term]))
        self.assertTrue(term_hits("synth-token", [term]))
        self.assertTrue(term_hits("synth_token", [term]))
        joined = "synth" + "token"
        self.assertTrue(term_hits(joined, [term]))
        self.assertTrue(term_hits("pre" + joined + "post", [term]))
        self.assertTrue(term_hits("xxsynth-tokenyy", [term]))

    def test_path_entry_matches_only_the_full_path(self):
        term = _slash("qa", "one")
        self.assertTrue(term_hits("call " + term + " now", [term]))
        self.assertTrue(term_hits("call " + term.replace("one", "/one") + " now", [term]))
        self.assertEqual(term_hits("see one here", [term]), [])
        self.assertEqual(term_hits("call " + term + "/more", [term]), [])
        self.assertEqual(term_hits("call " + _slash("qaone"), [term]), [])

    def test_route_in_url_link_host_and_tail(self):
        term = _slash("qa", "one")
        host = "https://preview.example"
        self.assertTrue(term_hits(host + term, [term]))
        self.assertTrue(term_hits("see " + term + "/", [term]))
        self.assertTrue(term_hits("see " + term + "?x=1", [term]))
        self.assertTrue(term_hits("see " + term + "#frag", [term]))
        self.assertTrue(term_hits("[doc](" + host + term + ")", [term]))
        self.assertTrue(term_hits("<" + host + term + ">", [term]))
        self.assertTrue(term_hits("preview.example" + term, [term]))
        self.assertTrue(term_hits("preview.example:8443" + term + "/", [term]))
        self.assertTrue(term_hits("see " + _slash("v1", "qa", "one"), [term]))
        self.assertTrue(term_hits(host + _slash("v1", "qa", "one"), [term]))
        self.assertEqual(term_hits("see " + term + "/more", [term]), [])
        self.assertEqual(term_hits("see " + term + "abc", [term]), [])
        prefix = _prefixed("zz")
        self.assertTrue(term_hits(host + "/zz/more?x=1", [prefix]))
        self.assertEqual(term_hits("see /zzy?x=1", [prefix]), [])

    def test_route_built_from_literal_pieces(self):
        term = _slash("qd", "four")
        samples = [
            '"/qd" + "/four"',
            "'/qd' + '/' + 'four'",
            '"/".join(["", "qd", "four"])',
            '"/%s/%s" % ("qd", "four")',
            'f"/qd/{\'four\'}"',
            'os.path.join("/qd", "four")',
        ]
        for sample in samples:
            self.assertTrue(term_hits(sample, [term]), sample)
        self.assertTrue(term_hits('"/v1" + "/qd" + "/four"', [term]))
        self.assertEqual(term_hits('"/qd" + "/four" + "/more"', [term]), [])
        self.assertEqual(term_hits('"/xqd" + "/four"', [term]), [])

    def test_mount_prefix_version_and_dot_segments(self):
        term = _slash("qd", "four")
        self.assertTrue(term_hits(_slash("pre", "qd", "four"), [term]))
        self.assertTrue(term_hits(_slash("pre", "qd", "four") + "/", [term]))
        self.assertTrue(term_hits(_slash("pre", "qd", "four") + "?q=1", [term]))
        self.assertTrue(term_hits(_slash("pre", "qd", "four") + "#f", [term]))
        self.assertTrue(term_hits(term + ";x=1", [term]))
        self.assertTrue(term_hits("/a/../" + term.lstrip("/"), [term]))
        self.assertTrue(term_hits("/a/b/../../" + term.lstrip("/"), [term]))
        self.assertTrue(term_hits("/a/./" + term.lstrip("/"), [term]))
        self.assertEqual(term_hits(_slash("pre", "qd", "fourabc"), [term]), [])
        self.assertEqual(term_hits(_slash("pre", "qd", "four", "more"), [term]), [])
        self.assertEqual(term_hits("/a/../qd/fourabc", [term]), [])
        version = _slash("v1", "qd", "four")
        self.assertTrue(term_hits(_slash("v2", "qd", "four"), [version]))
        self.assertTrue(term_hits(_slash("v10", "qd", "four") + "?q=1", [version]))
        self.assertTrue(term_hits(_slash("pre", "v8", "qd", "four") + "/", [version]))
        self.assertEqual(term_hits(_slash("vx", "qd", "four"), [version]), [])
        self.assertEqual(term_hits(_slash("v2", "qd", "five"), [version]), [])
        self.assertEqual(term_hits(_slash("v2", "qd", "four", "more"), [version]), [])
        self.assertEqual(term_hits(_slash("v2", "qd", "fourabc"), [version]), [])
        prefix = _prefixed("zz")
        self.assertTrue(term_hits(_slash("pre", "zz", "more"), [prefix]))
        self.assertTrue(term_hits(_slash("pre", "zz") + "?q=1", [prefix]))
        self.assertEqual(term_hits(_slash("pre", "zzy"), [prefix]), [])
        self.assertEqual(term_hits(_slash("pre", "zzmore"), [prefix]), [])

    def test_code_built_route_forms(self):
        term = _slash("qd", "four")
        hits = [
            '"/qd" "/four"',
            '"/qd" \\\n+ "/four"',
            '"/qd/{}".format("four")',
            '"{}".format("/qd/four")',
            'f"/qd/{\'four\'}"',
            'f"/qd/{name}/four"',
            '"/".join(["qd", "four"])',
            '"/".join(("qd", "four"))',
            '("/qd", "/four")',
        ]
        for sample in hits:
            self.assertTrue(term_hits(sample, [term]), sample)
        misses = [
            'f"/no/{name}"',
            '"/no/{}".format("zz")',
            '"/no" + "/match"',
            '"/".join(["no", "match"])',
            '"/".join(["qd", name])',
            '("/no", "/match")',
            '"/qd" \\\n+ "/other"',
        ]
        for sample in misses:
            self.assertEqual(term_hits(sample, [term]), [], sample)

    def test_path_prefix_marker(self):
        term = "/" + "zz" + "*"
        self.assertTrue(term_hits("see /zz now", [term]))
        self.assertTrue(term_hits("see /zz/anything now", [term]))
        self.assertEqual(term_hits("see /zzy now", [term]), [])
        self.assertEqual(term_hits("see zz now", [term]), [])

    def test_letter_gaps_of_two_or_more_still_fold(self):
        plant = "abc" + "g" + "def" + "g" + "01"
        self.assertTrue(hex_findings(plant, allow=frozenset()))

    def test_slash_and_comma_join_mixed_hex_only(self):
        self.assertTrue(hex_findings("ab/cd/ef/" + "01", allow=frozenset()))
        self.assertTrue(hex_findings("ab,cd,ef," + "01", allow=frozenset()))
        self.assertFalse(hex_findings("1,2,3"))
        self.assertFalse(hex_findings(".".join(["1", "2", "3"])))
        self.assertFalse(hex_findings("/v1/kirk-api/health"))
        self.assertFalse(hex_findings("12/34/56/" + "78", allow=frozenset()))
        self.assertFalse(hex_findings("feedback loop"))

    def test_iso_adjacency_still_hits(self):
        day = "2026" + "-07-" + "28"
        tail = "abc" + "def" + "0"
        cases = [
            day + "-" + tail,
            tail + "-" + day,
            day + "_" + tail,
            day + "." + tail,
            day + ":" + tail,
            day + "\u00b7" + tail,
            day + "\u2013" + tail,
            day + "g" + tail,
            day + "T" + "09:" + "30:" + "00Z-" + tail,
            tail + "." + day,
        ]
        self.assertEqual(len(cases), 10)
        for case in cases:
            self.assertTrue(hex_findings(case, allow=frozenset()), case)
        quiet = "1234" + "-12-" + "12"
        self.assertTrue(hex_findings("on " + quiet + " only", allow=frozenset()))
        self.assertTrue(hex_findings("1899" + "-01-" + "01", allow=frozenset()))
        self.assertTrue(hex_findings("2100" + "-12-" + "31", allow=frozenset()))
        self.assertFalse(hex_findings("1900" + "-01-" + "01"))
        self.assertFalse(hex_findings("2099" + "-12-" + "31"))
        plus = "2026" + "-07-" + "28T" + "09:" + "30:" + "00+" + "00:00"
        self.assertFalse(hex_findings("noted " + plus))
        frac6 = "2026" + "-07-" + "28T" + "09:" + "30:" + "00." + "123456" + "Z"
        frac7 = "2026" + "-07-" + "28T" + "09:" + "30:" + "00." + "123456" + "7Z"
        self.assertFalse(hex_findings(frac6))
        self.assertTrue(hex_findings(frac7, allow=frozenset()))
        self.assertTrue(hex_findings(
            "2026" + "-07-" + "28T" + "09:" + "30:" + "00",
            allow=frozenset(),
        ))

    def test_short_root_rejections_print_no_term(self):
        for raw in ("short:a", "SHORT:b", "short:short:x"):
            entries, error = terms_from_env(raw)
            self.assertIsNone(entries)
            self.assertEqual(error, "short root is not accepted")
            self.assertNotIn("short:", error.lower().replace("short root", ""))

    def test_synthetic_secret_has_no_false_hits(self):
        lines = synthetic_secret_lines()
        self.assertEqual(len(lines), 40)
        self.assertEqual(sum(1 for line in lines if line.startswith("short:")), 4)
        self.assertEqual(sum(1 for line in lines if line.endswith("*")), 1)
        entries, error = terms_from_env("\n".join(lines))
        self.assertIsNone(error)
        self.assertEqual(len(entries), 40)
        self.assertEqual(scan_repository(ROOT, terms=entries), [])

    def test_hex_allow_and_lock_path_are_pinned(self):
        self.assertEqual(HEX_ALLOW, frozenset({"8388608"}))
        self.assertEqual(LOCK_RELATIVE, "skills-lock.json")
        self.assertEqual(LOCK_OBJECT, "skills")
        self.assertEqual(LOCK_FIELD, "computedHash")

    def test_lock_hash_field_is_exempt_only_there(self):
        token = "a1" * 32
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.minimal_repo(root)
            lock = root / LOCK_RELATIVE
            lock.write_text(json.dumps({
                "version": 1,
                LOCK_OBJECT: {"demo": {LOCK_FIELD: token}},
            }), encoding="utf-8")
            self.assertEqual(hex_for_path(lock, root, lock.read_text(encoding="utf-8")), [])
            wrong_case = root / LOCK_RELATIVE
            wrong_case.write_text(json.dumps({
                LOCK_OBJECT: {"demo": {"ComputedHash": token}},
            }), encoding="utf-8")
            self.assertTrue(hex_for_path(wrong_case, root, wrong_case.read_text(encoding="utf-8")))
            nested = root / LOCK_RELATIVE
            nested.write_text(json.dumps({
                LOCK_OBJECT: {"demo": {"meta": {LOCK_FIELD: token}}},
            }), encoding="utf-8")
            self.assertTrue(hex_for_path(nested, root, nested.read_text(encoding="utf-8")))
            note = root / LOCK_RELATIVE
            note.write_text(json.dumps({
                LOCK_OBJECT: {"demo": {LOCK_FIELD: token, "note": token}},
            }), encoding="utf-8")
            noted = hex_for_path(note, root, note.read_text(encoding="utf-8"))
            self.assertTrue(any(token in item for item in noted))
            longer = root / LOCK_RELATIVE
            longer.write_text(json.dumps({
                LOCK_OBJECT: {"demo": {LOCK_FIELD: token + "a"}},
            }), encoding="utf-8")
            self.assertTrue(hex_for_path(longer, root, longer.read_text(encoding="utf-8")))
            other = root / "other.json"
            other.write_text(json.dumps({
                LOCK_OBJECT: {"demo": {LOCK_FIELD: token}},
            }), encoding="utf-8")
            self.assertTrue(hex_for_path(other, root, other.read_text(encoding="utf-8")))

    def test_duplicate_lock_keys_fail(self):
        token = "a1" * 32
        field = LOCK_FIELD
        group = LOCK_OBJECT
        bodies = [
            '{"%s": {"one": {"%s": "%s", "%s": "%s"}}}' % (group, field, token, field, token),
            '{"%s": {"one": {"%s": "%s"}, "one": {"%s": "%s"}}}' % (group, field, token, field, token),
            '{"version": 1, "version": 1, "%s": {}}' % group,
        ]
        for body in bodies:
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                self.minimal_repo(root)
                lock = root / LOCK_RELATIVE
                lock.write_text(body + "\n", encoding="utf-8")
                failures = scan_repository(root, terms=[])
                self.assertTrue(any(item.endswith(": duplicate key") for item in failures), failures)

    def test_lock_hash_shape_rejects_uppercase_and_other_lengths(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.minimal_repo(root)
            folder = root / ".agents" / "skills" / "demo"
            folder.mkdir(parents=True)
            lock = root / LOCK_RELATIVE
            for value in ("A1" * 32, "a1" * 31 + "b", "a1" * 32 + "c"):
                self.assertIn(len(value), (63, 64, 65))
                lock.write_text(json.dumps({
                    LOCK_OBJECT: {"demo": {LOCK_FIELD: value}},
                }), encoding="utf-8")
                self.assertTrue(hex_for_path(lock, root, lock.read_text(encoding="utf-8")), value)

    def test_fraction_of_seven_digits_is_not_exempt(self):
        frac = "2026" + "-07-" + "28T" + "09:" + "30:" + "00." + "123456" + "7Z"
        self.assertEqual(frac.count("."), 1)
        self.assertTrue(hex_findings(frac, allow=frozenset()))

    def test_pin_exemption_rejects_loose_lines_and_other_directories(self):
        sha = "a1" * 20
        self.assertEqual(len(sha), 40)
        good = [
            "uses: actions/checkout@%s" % sha,
            "        uses: actions/checkout@%s # v4.4.0" % sha,
            "- uses: actions/checkout@%s # v1" % sha,
            "      - uses: actions/checkout@%s" % sha,
        ]
        bad = [
            "name: uses: actions/checkout@%s" % sha,
            "echo uses: actions/checkout@%s # v1" % sha,
            "uses: actions/checkout@%s # anything" % sha,
            "uses: actions/checkout@%s # v1 extra" % sha,
        ]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.minimal_repo(root)
            workflow = root / ".github" / "workflows"
            workflow.mkdir(parents=True)
            for index, line in enumerate(good):
                path = workflow / ("ok-%s.yml" % index)
                path.write_text(line + "\n", encoding="utf-8")
                self.assertEqual(hex_for_path(path, root, path.read_text(encoding="utf-8")), [], line)
            for index, line in enumerate(bad):
                path = workflow / ("bad-%s.yml" % index)
                path.write_text(line + "\n", encoding="utf-8")
                self.assertTrue(hex_for_path(path, root, path.read_text(encoding="utf-8")), line)
            for name in ("side.yml", "side.yaml", str(Path(".github") / "side.yml")):
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("uses: actions/checkout@%s # v1\n" % sha, encoding="utf-8")
                self.assertTrue(hex_for_path(path, root, path.read_text(encoding="utf-8")), name)
            direct = workflow / "in.yaml"
            direct.write_text("- uses: actions/checkout@%s # v1\n" % sha, encoding="utf-8")
            self.assertEqual(hex_for_path(direct, root, direct.read_text(encoding="utf-8")), [])
            nested = workflow / "sub" / "x.yml"
            nested.parent.mkdir()
            nested.write_text("- uses: actions/checkout@%s # v1\n" % sha, encoding="utf-8")
            self.assertTrue(hex_for_path(nested, root, nested.read_text(encoding="utf-8")))

    def test_lock_entries_match_skill_folders(self):
        text = (ROOT / LOCK_RELATIVE).read_text(encoding="utf-8")
        self.assertEqual(lock_errors(text, ROOT), [])
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.minimal_repo(root)
            raw = json.dumps({LOCK_OBJECT: {"missing-skill": {LOCK_FIELD: "a1" * 32}}})
            self.assertTrue(any("skill folder" in item for item in lock_errors(raw, root)))

    def test_workflow_pin_is_exempt_only_on_the_uses_line(self):
        sha = "a1" * 20
        self.assertEqual(len(sha), 40)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.minimal_repo(root)
            workflow = root / ".github" / "workflows"
            workflow.mkdir(parents=True)
            pinned = workflow / "docs-checks.yml"
            pinned.write_text(
                "jobs:\n  t:\n    steps:\n      - name: Checkout\n        uses: actions/checkout@%s # v4.4.0\n" % sha,
                encoding="utf-8",
            )
            self.assertEqual(hex_for_path(pinned, root, pinned.read_text(encoding="utf-8")), [])
            bare = workflow / "bare.yml"
            bare.write_text("        uses: actions/checkout@%s\n" % sha, encoding="utf-8")
            self.assertEqual(hex_for_path(bare, root, bare.read_text(encoding="utf-8")), [])
            extra = workflow / "extra.yml"
            extra.write_text(
                "        uses: actions/checkout@%s # v4.4.0\n        run: echo %s\n" % (sha, sha),
                encoding="utf-8",
            )
            self.assertTrue(hex_for_path(extra, root, extra.read_text(encoding="utf-8")))
            other = root / "notes.txt"
            other.write_text("uses: actions/checkout@%s # v4.4.0\n" % sha, encoding="utf-8")
            self.assertTrue(hex_for_path(other, root, other.read_text(encoding="utf-8")))

    def test_findings_name_file_line_and_index_only(self):
        route = _slash("qd", "four")
        term = "synth" + "-" + "token"
        text = "curl https://api.kavara.ai" + SYNTHETIC_PATH + " -o out.json"
        piece = "\n".join(self.piece(text))
        self.assertIn("unpublished route", piece)
        self.assertNotIn(SYNTHETIC_PATH, piece)
        wrapped = "\n".join(self.wrapped("intro\n```\n" + text + "\n```\n"))
        self.assertIn("fixture:2:", wrapped)
        self.assertNotIn(SYNTHETIC_PATH, wrapped)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.minimal_repo(root)
            page = root / "notes.md"
            page.write_text("see " + route + "\n" + term + "\n", encoding="utf-8")
            failures = scan_repository(root, terms=[route, term])
            blob = "\n".join(failures)
            self.assertIn("notes.md:1: term 0", blob)
            self.assertIn("notes.md:2: term 1", blob)
            self.assertNotIn(route, blob)
            self.assertNotIn(term, blob)

    def test_underscore_key_and_more_placements(self):
        common = [
            'BASE_URL = "https://api.kavara.ai"',
            'headers = {"X-Kavara-Key": API_KEY}',
        ]
        samples = [
            common + ['json = {"x_kavara_key": API_KEY}', 'call("GET", "/v1/kirk-api/health")'],
            common + ['data = {"X_KAVARA_KEY": API_KEY}', 'call("GET", "/v1/kirk-api/health")'],
            common + ['params.append(("key", API_KEY))', 'call("GET", "/v1/kirk-api/health")'],
            common + ['params["key"] = API_KEY', 'call("GET", "/v1/kirk-api/health")'],
            common + ['HTTPBasicAuth("user", API_KEY)', 'call("GET", "/v1/kirk-api/health")'],
            common + ['headers = [("Authorization", "Bearer x")]', 'call("GET", "/v1/kirk-api/health")'],
            common + ['client.get(BASE_URL + "/v1/kirk-api/health", **options)'],
            common + ['curl -G --data "key=abc" --url "${BASE_URL}/v1/kirk-api/health" -o out.json'],
            common + ['page = base + "?access_token=abc"', 'call("GET", "/v1/kirk-api/health")'],
            common + ['json = {"api_key": API_KEY}', 'call("GET", "/v1/kirk-api/health")'],
            common + ['data = "key=abc"', 'call("GET", "/v1/kirk-api/health")'],
            common + ['dict(key=API_KEY)', 'call("GET", "/v1/kirk-api/health")'],
        ]
        for sample in samples:
            self.assertTrue(self.piece("\n".join(sample)), sample)

    def test_encoded_term_is_found(self):
        term = "synth" + "token"
        planted = "".join("%%%02X" % ord(char) for char in term)
        self.assertEqual(term_hits(planted, [term]), [(1, 0)])

    def test_root_markdown_plants(self):
        terms = self.synthetic_terms()
        token = "abc" + "def" + "4"
        long_hex = "a1" * 20
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.minimal_repo(root)
            page = root / "README.md"
            page.write_text("\n".join([terms[0], terms[1], token, long_hex]) + "\n", encoding="utf-8")
            failures = scan_repository(root, terms=terms)
            blob = "\n".join(failures)
            self.assertIn("README.md", blob)
            self.assertIn("term 0", blob)
            self.assertIn("term 1", blob)
            self.assertIn(token, blob)
            self.assertIn(long_hex, blob)
            self.assertNotIn(terms[0], blob)
            self.assertNotIn(terms[1], blob)

    def test_toplevel_and_subdirectory_plants(self):
        terms = self.synthetic_terms()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.minimal_repo(root)
            (root / "notes.md").write_text(terms[0] + "\n", encoding="utf-8")
            (root / "PAGE.MD").write_text(terms[2] + "\n", encoding="utf-8")
            nested = root / "benchmarks"
            nested.mkdir()
            (nested / "note.md").write_text(terms[1] + "\n", encoding="utf-8")
            (nested / "extra.markdown").write_text(terms[0] + "\n", encoding="utf-8")
            failures = scan_repository(root, terms=terms)
            blob = "\n".join(failures)
            self.assertIn("notes.md", blob)
            self.assertIn("PAGE.MD", blob)
            self.assertIn("benchmarks/note.md", blob)
            self.assertIn("benchmarks/extra.markdown", blob)
            self.assertNotIn(terms[0], blob)
            self.assertNotIn(terms[1], blob)

    def test_escaping_symlink_fails(self):
        terms = self.synthetic_terms()
        with tempfile.TemporaryDirectory() as outside:
            target = Path(outside) / "outside.md"
            target.write_text("outside\n", encoding="utf-8")
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                docs = self.minimal_repo(root)
                link = docs / "escape.md"
                link.symlink_to(target)
                failures = scan_repository(root, terms=terms)
                self.assertTrue(any("symlink resolves outside" in item for item in failures))

    def test_docs_symlink_outside_docs_fails(self):
        terms = self.synthetic_terms()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            docs = self.minimal_repo(root)
            outside = root / "notes.md"
            outside.write_text("inside the repository\n", encoding="utf-8")
            link = docs / "linked.md"
            link.symlink_to(outside)
            failures = scan_repository(root, terms=terms)
            self.assertTrue(any("outside docs" in item for item in failures))

    def test_symlink_loop_fails_closed(self):
        terms = self.synthetic_terms()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.minimal_repo(root)
            link = root / "docs" / "loop.md"
            link.symlink_to("loop.md")
            failures = scan_repository(root, terms=terms)
            code = 1 if failures else 0
            self.assertNotEqual(code, 0)

    def test_digest_path_is_the_hex_exemption(self):
        token = "a1" * 32
        self.assertTrue(hex_findings(token, allow=frozenset()))
        self.assertEqual(hex_for_path(ROOT / DIGEST_RELATIVE, ROOT, token), [])
        self.assertTrue(hex_for_path(ROOT / "README.md", ROOT, token))

    def test_secret_can_carry_an_extra_entry(self):
        route = "/v1/" + "synthetic-route"
        self.assertEqual([index for _line, index in term_hits("see " + route, [route])], [0])

    def write_mutant(self, directory, document):
        root = Path(directory)
        docs = root / "docs"
        docs.mkdir()
        spec = docs / "customer-rest-api.openapi.json"
        spec.write_text(json.dumps(document), encoding="utf-8")
        digest = root / DIGEST_RELATIVE
        digest.parent.mkdir(parents=True, exist_ok=True)
        original = load_document(OPENAPI_PATH)
        digest.write_text(self.independent_digest(original) + "\n", encoding="utf-8")
        return spec, digest

    def test_mutant_minimum_fails_digest(self):
        document = load_document(OPENAPI_PATH)
        node = document["components"]["schemas"]["CreateRequest"]["properties"]["hyperparameters"]
        node["properties"]["visible_nodes"]["minimum"] = 0
        with tempfile.TemporaryDirectory() as directory:
            spec, digest = self.write_mutant(directory, document)
            self.assertNotEqual(digest_rc(spec, digest), 0)

    def test_mutant_required_dropped_fails_digest(self):
        document = load_document(OPENAPI_PATH)
        document["components"]["schemas"]["CreateRequest"]["required"] = []
        with tempfile.TemporaryDirectory() as directory:
            spec, digest = self.write_mutant(directory, document)
            self.assertNotEqual(digest_rc(spec, digest), 0)

    def test_mutant_type_change_fails_digest(self):
        document = load_document(OPENAPI_PATH)
        document["components"]["schemas"]["CreateRequest"]["properties"]["random_state"]["type"] = "string"
        with tempfile.TemporaryDirectory() as directory:
            spec, digest = self.write_mutant(directory, document)
            self.assertNotEqual(digest_rc(spec, digest), 0)

    def test_mutant_description_fails_digest(self):
        document = load_document(OPENAPI_PATH)
        node = document["components"]["schemas"]["Contract"]["properties"]["max_body_bytes"]
        node["description"] = node.get("description", "") + " extra"
        with tempfile.TemporaryDirectory() as directory:
            spec, digest = self.write_mutant(directory, document)
            self.assertNotEqual(digest_rc(spec, digest), 0)

    def test_banned_term(self):
        term = "synth" + "token"
        self.assertEqual([index for _line, index in term_hits("see " + term, [term])], [0])


def prove_secret():
    """Show that CI loaded the term list, without printing a term."""
    entries, error = terms_from_env()
    if error:
        print(error, file=sys.stderr)
        return 1
    for _kind, term in entries:
        sys.stdout.write("::add-mask::%s\n" % term)
    planted = entries[0][1]
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        docs = root / "docs"
        docs.mkdir()
        shutil.copy(OPENAPI_PATH, docs / "customer-rest-api.openapi.json")
        shutil.copy(ROOT / "docs" / "customer-rest-api.md", docs / "customer-rest-api.md")
        digest = root / DIGEST_RELATIVE
        digest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(ROOT / DIGEST_RELATIVE, digest)
        page = root / "plant.md"
        page.write_text(planted + "\n", encoding="utf-8")
        failures = scan_repository(root, terms=entries)
    blob = "\n".join(failures)
    if planted in blob:
        print("scan leaked a term", file=sys.stderr)
        return 1
    if "plant.md" not in blob or "term 0" not in blob:
        print("secret plant was not detected", file=sys.stderr)
        return 1
    print("secret plant was detected")
    return 0


def main(argv):
    if "--check-digest" in argv:
        failures = check_digest(OPENAPI_PATH)
        if failures:
            for item in failures:
                print(item, file=sys.stderr)
            return 1
        print("vendored spec digest matches")
        return 0
    if "--prove-secret" in argv:
        return prove_secret()
    if "--scan-synthetic" in argv:
        entries, error = terms_from_env("\n".join(synthetic_secret_lines()))
        if error:
            print(error, file=sys.stderr)
            return 1
        failures = scan_repository(ROOT, terms=entries)
        if failures:
            for item in failures:
                print(item, file=sys.stderr)
            print("%d customer-sample check(s) failed" % len(failures), file=sys.stderr)
            return 1
        print("synthetic scan found nothing")
        return 0
    if "--self-test" in argv:
        suite = unittest.defaultTestLoader.loadTestsFromTestCase(CheckerTests)
        result = unittest.TextTestRunner(verbosity=1).run(suite)
        return 0 if result.wasSuccessful() else 1
    failures = scan_repository()
    if failures:
        for item in failures:
            print(item, file=sys.stderr)
        print("%d customer-sample check(s) failed" % len(failures), file=sys.stderr)
        return 1
    print("customer samples match the vendored spec")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
