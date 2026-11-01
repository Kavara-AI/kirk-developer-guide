#!/usr/bin/env python3
"""Fail closed on customer samples that drift from the vendored spec.

Scans every fenced block (backtick or tilde, tagged or not) and every inline
code span under the customer docs. Unknown fence languages are scanned, not
skipped. The operation allow-list is loaded from
docs/customer-rest-api.openapi.json at runtime. The full document must match
the encoded digest in scripts/customer-spec.digest, which this checker skips
by exact path. The digest is not stored as a hex run.
"""

from __future__ import annotations

import hashlib
import ipaddress
import json
import re
import shlex
import shutil
import sys
import tempfile
import unicodedata
import unittest
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
OPENAPI_PATH = ROOT / "docs" / "customer-rest-api.openapi.json"
DIGEST_PATH = ROOT / "scripts" / "customer-spec.digest"
PUBLIC_API_BASE = "https://api.kavara.ai"
# Exact paths the hex scan must not read. The digest file is encoded, and it
# lives outside docs; the exclusion is here so a wider scan still skips it.
HEX_SKIP_PATHS = frozenset({DIGEST_PATH.resolve()})

BLOCKED_SEGMENTS = frozenset({"mcp", "admin", "internal", "svc", "usage"})
EXCLUDED_EXACT = frozenset({"/v1/engine", "/v1/models", "/v1/score-book"})
HTTP_METHODS = frozenset({"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"})
SKIP_DIRS = {".git", ".agents", "node_modules"}
DOC_ROOTS = ("docs", "examples")
ROOT_MARKDOWN = ("README.md", "START_HERE.md", "CLAUDE.md", "AGENTS.md")
BANNED_TERMS = (
    "vercel.app",
    "cooling_rate",
    "kirk-operating-envelope",
    "KVS_STUDIO_TOKEN",
    "hosted_kirk_raw_hp_admission",
    "kirk_version",
    "engine_sha",
    "agent_sweep_policy",
)
# Digit runs that are not revision ids.
# 8388608 is 8 MiB, the contract max_body_bytes const (8 * 1024 * 1024).
# 20260922 is the example brief calendar date, written as an ISO timestamp.
HEX_ALLOW = frozenset({"8388608", "20260922"})
KEY_LITERAL = re.compile(r"k_[0-9a-fA-F]{32}")
FENCE_RE = re.compile(
    r"(?ms)^(?P<open>`{3,}|~{3,})[ \t]*(?P<info>[^\n]*)\n(?P<body>.*?)^(?P=open)[ \t]*$"
)
INLINE_RE = re.compile(r"(?<!`)`([^`\n]+)`(?!`)")
ROUTE_RE = re.compile(
    r"https?://[^\s'\"`<>)\]]+"
    r"|\$\{[A-Za-z_][A-Za-z0-9_]*\}(/[A-Za-z0-9_./{}~$-]*)"
    r"|(?<![\w$])(/(?:v1|usage|mcp|admin|internal|svc)(?:/[A-Za-z0-9_./{}~$-]*)?)",
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


def encode_digest(hex_digest):
    """Break a hex digest into 4-digit groups so it is not a 7+ hex run.

    Hex has no 'g', and 'g' is not a stripped separator, so the groups stay split.
    """
    return "g".join(hex_digest[index:index + 4] for index in range(0, len(hex_digest), 4))


def decode_digest(text):
    return "".join(text.strip().split("g"))


def stored_digest():
    return decode_digest(DIGEST_PATH.read_text(encoding="utf-8"))


def load_document(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def normalise(path):
    bare = (path or "").split("?", 1)[0].split("#", 1)[0]
    if len(bare) > 1:
        bare = bare.rstrip("/")
    return bare


def blocked(path):
    bare = normalise(path)
    if bare in EXCLUDED_EXACT or bare == "/usage" or bare.startswith("/usage/"):
        return True
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
        failures.append("%s: %s %s is not a published customer operation" % (label, method, bare))
        return failures
    if url is None:
        failures.append("%s: %s %s has no resolvable base URL" % (label, method, bare))
    else:
        reason = bad_base(url, spec.public_base)
        if reason:
            failures.append("%s: %s (%s)" % (label, reason, url))
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


def check_routes(text, spec, label):
    failures = []
    for path, shown in route_hits(text):
        if not path:
            continue
        if blocked(path) or not is_allowed_path(path, spec):
            failures.append("%s: route %s is not published" % (label, shown))
        if shown.startswith(("http://", "https://")):
            reason = bad_base(shown, PUBLIC_API_BASE)
            if reason and not blocked(path):
                failures.append("%s: %s (%s)" % (label, reason, shown))
    return failures


def misplaced_secret(text, label):
    """X-Kavara-Key is a request header. Basic auth and Authorization are not."""
    failures = []
    if re.search(r"(?i)(?:\?|&)X-Kavara-Key\b", text):
        failures.append("%s: X-Kavara-Key must be a request header, not a query string" % label)
    if re.search(r"(?i)--url-query(?:\s+|=)\S*X-Kavara-Key", text):
        failures.append("%s: X-Kavara-Key must be a request header, not --url-query" % label)
    if re.search(r"(?i)params\s*=\s*\{[^}]*X-Kavara-Key", text):
        failures.append("%s: X-Kavara-Key must be a request header, not a params mapping" % label)
    if re.search(r"""(?i)headers\s*\[\s*['"]Authorization['"]\s*\]\s*=""", text):
        failures.append("%s: Authorization is not a security-scheme header" % label)
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
    for kind, info, body, _start, _end in code_pieces(text):
        piece_label = "%s:%s:%s" % (label, kind, info or "untagged")
        failures.extend(check_piece(body, spec, piece_label))
    return failures


def check_digest(path):
    document = load_document(path)
    got = spec_fingerprint(document)
    if got != stored_digest():
        return ["spec digest drifted from the recorded full-document digest"]
    spec = Spec(document)
    failures = []
    if spec.public_base != PUBLIC_API_BASE:
        failures.append("vendored server URL is not the public api base")
    for path_item in spec.allowed_paths:
        if blocked(path_item):
            failures.append("vendored spec publishes blocked path %s" % path_item)
    if not spec.security_headers:
        failures.append("vendored spec has no header security scheme")
    return failures


def hex_findings(text, allow=HEX_ALLOW):
    """7+ hex runs after NFKC, with separators, dashes and zero-width marks removed.

    Digit-only runs count. A letter is not required.
    """
    findings = []
    text = unicodedata.normalize("NFKC", text)
    text = text.translate({ord(char): None for char in "\u200b\u200c\u200d\ufeff\u2060\u180e"})
    separators = set("-_:")
    separators.update("\u2010\u2011\u2012\u2013\u2014\u2015\u2212\ufe58\ufe63\uff0d\u00ad")
    hexdigits = set("0123456789abcdefABCDEF")
    index = 0
    length = len(text)
    while index < length:
        if text[index] not in hexdigits:
            index += 1
            continue
        chars = []
        cursor = index
        while cursor < length:
            char = text[cursor]
            if char in hexdigits:
                chars.append(char)
                cursor += 1
                continue
            if char in separators and cursor + 1 < length and text[cursor + 1] in hexdigits:
                cursor += 1
                continue
            break
        token = "".join(chars)
        if len(token) >= 7 and token.lower() not in allow:
            findings.append(token.lower())
        index = cursor if cursor > index else index + 1
    return findings


def fold_term(text):
    """NFKC, casefold, and drop separators so a banned term cannot hide in punctuation."""
    text = unicodedata.normalize("NFKC", text).casefold()
    text = text.translate({ord(char): None for char in "\u200b\u200c\u200d\ufeff\u2060\u180e"})
    for char in "-_\u2010\u2011\u2012\u2013\u2014\u2015\u2212\ufe58\ufe63\uff0d\u00ad":
        text = text.replace(char, "")
    return text


def banned_findings(text):
    folded = fold_term(text)
    return [term for term in BANNED_TERMS if fold_term(term) in folded]


def in_doc_tree(path, root):
    """True for docs/ and examples/ after resolving to a path relative to root."""
    try:
        relative = path.resolve().relative_to(Path(root).resolve())
    except ValueError:
        return False
    return bool(relative.parts) and relative.parts[0] in DOC_ROOTS


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


def markdown_files(root):
    files = []
    for name in ROOT_MARKDOWN:
        path = root / name
        if path.is_file():
            files.append(path)
    for folder in DOC_ROOTS:
        base = root / folder
        if not base.is_dir():
            continue
        for path in base.rglob("*"):
            if not path.is_file():
                continue
            if any(part in SKIP_DIRS for part in path.relative_to(root).parts):
                continue
            if path.resolve() in HEX_SKIP_PATHS or not in_doc_tree(path, root):
                continue
            files.append(path)
    return files


def scan_repository(root=ROOT):
    failures = check_digest(root / "docs" / "customer-rest-api.openapi.json")
    document = load_document(root / "docs" / "customer-rest-api.openapi.json")
    spec = Spec(document)
    for path in markdown_files(root):
        if path.suffix.lower() not in {".md", ".json", ".txt", ".yml", ".yaml"}:
            continue
        text = path.read_text(encoding="utf-8")
        label = str(path.relative_to(root))
        if path.suffix.lower() == ".md":
            failures.extend(scan_text(text, spec, label))
        if in_doc_tree(path, root):
            for token in hex_findings(text):
                failures.append("%s: hex run %s" % (label, token))
            for term in banned_findings(text):
                failures.append("%s: banned term %s" % (label, term))
    # docs/ and examples/ include json such as the brief and the vendored spec.
    for folder in DOC_ROOTS:
        base = root / folder
        if not base.is_dir():
            continue
        for path in base.rglob("*"):
            if not path.is_file() or path.suffix.lower() == ".md":
                continue
            if any(part in SKIP_DIRS for part in path.relative_to(root).parts):
                continue
            text = path.read_text(encoding="utf-8")
            label = str(path.relative_to(root))
            for token in hex_findings(text):
                failures.append("%s: hex run %s" % (label, token))
            for term in banned_findings(text):
                failures.append("%s: banned term %s" % (label, term))
    quick = (root / "docs" / "customer-rest-api.md").read_text(encoding="utf-8")
    python_calls_found, curl_calls_found = quickstart_calls(quick, spec)
    if python_calls_found != list(QUICKSTART_CALLS):
        failures.append("quickstart python calls are %s" % (python_calls_found,))
    if curl_calls_found != list(QUICKSTART_CALLS):
        failures.append("quickstart curl calls are %s" % (curl_calls_found,))
    return failures


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
        got = self.independent_digest(document)
        self.assertEqual(got, decode_digest(DIGEST_PATH.read_text(encoding="utf-8")))
        self.assertEqual(spec_fingerprint(document), got)
        self.assertEqual(check_digest(OPENAPI_PATH), [])

    def test_schema_edit_changes_digest(self):
        document = load_document(OPENAPI_PATH)
        original = self.independent_digest(document)
        edited = json.loads(json.dumps(document))
        node = edited["components"]["schemas"]["CreateRequest"]["properties"]["hyperparameters"]
        node["properties"]["visible_nodes"]["minimum"] = 0
        self.assertNotEqual(self.independent_digest(edited), original)
        self.assertNotEqual(spec_fingerprint(edited), spec_fingerprint(document))

    def test_full_url(self):
        text = "```bash\ncurl https://api.kavara.ai/v1/engine -o out.json\n```\n"
        self.assertTrue(self.wrapped(text))

    def test_var_path(self):
        text = "```bash\nBASE_URL=\"https://api.kavara.ai\"\ncurl --url \"${BASE_URL}/v1/engine\" -o out.json\n```\n"
        self.assertTrue(self.wrapped(text))

    def test_untagged_fence(self):
        text = "```\nhttps://api.kavara.ai/v1/engine\n```\n"
        self.assertTrue(self.wrapped(text))

    def test_console_fence(self):
        text = "```console\ncurl https://api.kavara.ai/v1/engine\n```\n"
        self.assertTrue(self.wrapped(text))

    def test_js_fence(self):
        text = "```js\nfetch(\"https://api.kavara.ai/v1/engine\")\n```\n"
        self.assertTrue(self.wrapped(text))

    def test_tilde_fence(self):
        text = "~~~\ncurl https://api.kavara.ai/v1/engine\n~~~\n"
        self.assertTrue(self.wrapped(text))

    def test_json_body(self):
        text = "```json\n{\"path\": \"/v1/engine\"}\n```\n"
        self.assertTrue(self.wrapped(text))

    def test_inline_curl(self):
        text = "Run `curl https://api.kavara.ai/v1/engine` now.\n"
        self.assertTrue(self.wrapped(text))

    def test_unknown_fence_type(self):
        text = "```not-a-language\nGET https://api.kavara.ai/v1/engine\n```\n"
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

    def test_usage_segment(self):
        self.assertTrue(self.piece("curl https://api.kavara.ai/usage/me -o out.json"))

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
        self.assertTrue(any("sample base is not" in item for item in self.piece(text)))

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
        self.assertTrue(hex_findings("token abcdef0", allow=frozenset()))
        self.assertTrue(hex_findings("token abcd-ef0", allow=frozenset()))
        self.assertTrue(hex_findings("count 1234567", allow=frozenset()))
        self.assertTrue(hex_findings("count 1234\u2013567", allow=frozenset()))
        self.assertTrue(hex_findings("count 1234\u200b567", allow=frozenset()))
        self.assertTrue(hex_findings("count \uff11\uff12\uff13\uff14\uff15\uff16\uff17", allow=frozenset()))
        self.assertFalse(hex_findings("label example-revision"))
        self.assertFalse(hex_findings("body cap 8388608"))

    def test_banned_term_folding(self):
        planted = "Cooling" + "\u2013" + "Rate"
        host = "VERCEL" + ".APP"
        self.assertEqual(fold_term("\n".join(banned_findings(planted))), fold_term("cooling" + "_" + "rate"))
        self.assertEqual(fold_term("\n".join(banned_findings(host))), fold_term(host))

    def test_markdown_scan_catches_planted_leaks(self):
        """The real repository scan must see Markdown under docs/, not skip it."""
        tuning = "cooling" + "_" + "rate"
        host = "vercel" + "." + "app"
        token = "abc" + "de" + "f2"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            docs = root / "docs"
            docs.mkdir()
            shutil.copy(OPENAPI_PATH, docs / "customer-rest-api.openapi.json")
            shutil.copy(ROOT / "docs" / "customer-rest-api.md", docs / "customer-rest-api.md")
            clean = scan_repository(root)
            self.assertFalse(any("planted-leak" in item for item in clean), clean)
            page = docs / "planted-leak.md"
            page.write_text(tuning + "\n" + host + "\n" + token + "\n", encoding="utf-8")
            dirty = scan_repository(root)
            blob = "\n".join(dirty).casefold()
            self.assertIn("planted-leak.md", blob)
            self.assertIn(fold_term(tuning), fold_term(blob))
            self.assertIn(fold_term(host), fold_term(blob))
            self.assertIn(token, blob)

    def test_banned_term(self):
        self.assertEqual(banned_findings("see vercel.app today"), ["vercel.app"])


def main(argv):
    if "--print-digest" in argv:
        print(encode_digest(spec_fingerprint(load_document(OPENAPI_PATH))))
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
