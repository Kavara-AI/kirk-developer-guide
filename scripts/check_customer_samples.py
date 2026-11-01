#!/usr/bin/env python3
"""Fail closed on customer samples that drift from the vendored spec.

Scans every Markdown file. Unknown fence languages are scanned, not skipped.
The operation allow-list is loaded from docs/customer-rest-api.openapi.json
at runtime. Term matching uses KDG_BANNED_TERMS and refuses to run when that
list is missing.
"""

from __future__ import annotations

import hashlib
import html
import ipaddress
import json
import os
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

def _route(*parts):
    return "/" + "/".join(parts)

BLOCKED_SEGMENTS = frozenset({"mcp", "admin", "internal", "svc", "usage"})
EXCLUDED_EXACT = frozenset({
    _route("v1", "engine"),
    _route("v1", "models"),
    _route("v1", "score-book"),
})
HTTP_METHODS = frozenset({"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"})
SKIP_DIRS = {".git", ".agents", "node_modules"}
# Digit runs that are not revision ids.
# 8388608 is 8 MiB, the contract max_body_bytes const (8 * 1024 * 1024).
# 20260728 is the decision-record date 28 July 2026.
# 20260922 is the example brief calendar date, written as an ISO timestamp.
HEX_ALLOW = frozenset({"8388608", "20260728", "20260922"})
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
    roots = {"v1", "usage", "mcp", "admin", "internal", "svc"}
    return bool(parts) and parts[0].lower() in roots


def check_routes(text, spec, label):
    failures = []
    for path, shown in route_hits(text):
        if not path:
            continue
        if not customer_sample_target(path, shown):
            continue
        if blocked(path) or not is_allowed_path(path, spec):
            failures.append("%s: route %s is not published" % (label, shown))
        if shown.startswith(("http://", "https://")):
            reason = bad_base(shown, PUBLIC_API_BASE)
            if reason and not blocked(path):
                failures.append("%s: %s (%s)" % (label, reason, shown))
    return failures


def misplaced_secret(text, label):
    """The customer key belongs only in the request header."""
    failures = []
    if re.search(r"(?i)(?:\?|&)(?:key|x-kavara-key)=", text):
        failures.append("%s: key must be a request header, not a query string" % label)
    if re.search(r"(?i)--url-query(?:\s+|=)\S*(?:key|x-kavara-key)\b", text):
        failures.append("%s: key must be a request header, not --url-query" % label)
    if re.search(r"(?i)(?:^|\s)-G\b", text) and re.search(r"(?i)--data-urlencode\b", text):
        failures.append("%s: key must not be moved into the query with -G --data-urlencode" % label)
    if re.search(r"(?i)--oauth2-bearer\b", text):
        failures.append("%s: oauth2 bearer is not the security scheme" % label)
    if re.search(r"(?i)params\s*=\s*\{[^}]*(?:X-Kavara-Key|\bkey\b)", text):
        failures.append("%s: key must be a request header, not a params mapping" % label)
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
    for kind, info, body, _start, _end in code_pieces(text):
        piece_label = "%s:%s:%s" % (label, kind, info or "untagged")
        failures.extend(check_piece(body, spec, piece_label))
    return failures


def check_digest(path):
    """Hash the vendored spec. Missing input is an error, not a traceback."""
    path = Path(path)
    if not path.is_file():
        return ["vendored spec is missing"]
    try:
        raw = path.read_text(encoding="utf-8")
        document = json.loads(raw)
    except (OSError, ValueError):
        return ["vendored spec is not valid JSON"]
    if not isinstance(document, dict):
        return ["vendored spec is not a JSON object"]
    try:
        spec_fingerprint(document)
        spec = Spec(document)
    except Exception:
        return ["vendored spec digest could not be computed"]
    failures = []
    if spec.public_base != PUBLIC_API_BASE:
        failures.append("vendored server URL is not the public api base")
    for path_item in spec.allowed_paths:
        if blocked(path_item):
            failures.append("vendored spec publishes a blocked path")
    if not spec.security_headers:
        failures.append("vendored spec has no header security scheme")
    return failures


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


def terms_from_env():
    raw = os.environ.get(SECRET_NAME)
    if raw is None or not raw.strip():
        return None, MISSING_SECRET
    terms = [line.strip() for line in raw.splitlines() if line.strip()]
    if not terms:
        return None, MISSING_SECRET
    return terms, None


def term_on_line(folded, needle):
    if len(needle) >= 6:
        return needle in folded
    return re.search("(?<![0-9a-z])" + re.escape(needle) + "(?![0-9a-z])", folded) is not None


def term_hits(text, terms):
    """Return (line, index) pairs. The term text is not returned."""
    hits = []
    lines = text.splitlines() or [text]
    folded_lines = [normalize_text(line) for line in lines]
    whole = normalize_text(text)
    for index, term in enumerate(terms):
        needle = normalize_text(term)
        if not needle:
            continue
        matched = False
        for line_no, folded in enumerate(folded_lines, 1):
            if term_on_line(folded, needle):
                hits.append((line_no, index))
                matched = True
        if not matched and term_on_line(whole, needle):
            hits.append((1, index))
    return hits


def _gap_kind(gap, hexdigits, dashes):
    """soft whitespace, hard punctuation, or one repeated non-hex letter."""
    if not gap:
        return None
    letters = []
    hard = False
    for char in gap:
        if char in hexdigits:
            return None
        if char.isspace():
            continue
        if char == "." or char in dashes:
            hard = True
            continue
        if "a" <= char <= "z":
            letters.append(char)
            continue
        return None
    if letters:
        if hard or any(char.isspace() for char in gap):
            return None
        if len(set(letters)) != 1:
            return None
        return "letter"
    return "hard" if hard else "soft"


def _join_ok(kind, left, right):
    if kind == "hard":
        return left >= 2 and right >= 2
    if kind in ("soft", "letter"):
        return left >= 3 and right >= 3
    return False


def _word_char(text, index):
    """A non-hex letter outside a separator gap keeps the run inside a word."""
    if index < 0 or index >= len(text):
        return False
    char = text[index]
    return "a" <= char <= "z" and char not in "0123456789abcdef"


def hex_findings(text, allow=HEX_ALLOW):
    """7+ hex runs. Dot, whitespace and repeated separators join groups."""
    findings = []
    text = normalize_text(text)
    hexdigits = set("0123456789abcdef")
    dashes = set("-_:\u2010\u2011\u2012\u2013\u2014\u2015\u2212\ufe58\ufe63\uff0d")
    index = 0
    length = len(text)
    while index < length:
        if text[index] not in hexdigits:
            index += 1
            continue
        chars = [text[index]]
        group = 1
        cursor = index + 1
        while cursor < length:
            if text[cursor] in hexdigits:
                chars.append(text[cursor])
                group += 1
                cursor += 1
                continue
            probe = cursor
            while probe < length and text[probe] not in hexdigits:
                probe += 1
            kind = _gap_kind(text[cursor:probe], hexdigits, dashes) if probe < length else None
            nxt = 0
            if kind:
                while probe + nxt < length and text[probe + nxt] in hexdigits:
                    nxt += 1
            if (
                kind
                and _join_ok(kind, group, nxt)
                and not _word_char(text, cursor - group - 1)
                and not _word_char(text, probe + nxt)
            ):
                chars.append(text[probe])
                cursor = probe + 1
                group = 1
                continue
            break
        token = "".join(chars)
        if len(token) >= 7 and token not in allow:
            findings.append(token)
        index = cursor if cursor > index else index + 1
    return findings


def is_inside(path, parent):
    try:
        Path(path).resolve().relative_to(Path(parent).resolve())
        return True
    except ValueError:
        return False


def symlink_failure(path, root):
    """None when a link stays inside the tree. A docs link must stay under docs."""
    root = Path(root)
    try:
        relative = path.relative_to(root)
    except ValueError:
        return "%s: symlink resolves outside the repository" % path
    try:
        target = path.resolve(strict=False)
    except OSError:
        return "%s: symlink cannot be resolved" % relative.as_posix()
    if not is_inside(target, root):
        return "%s: symlink resolves outside the repository" % relative.as_posix()
    if relative.parts and relative.parts[0] == "docs" and not is_inside(target, root / "docs"):
        return "%s: symlink resolves outside docs" % relative.as_posix()
    return None


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
            if not name.lower().endswith(".md"):
                continue
            candidate = current / name
            if candidate.is_symlink():
                problem = symlink_failure(candidate, root)
                if problem:
                    failures.append(problem)
                    continue
            files.append(candidate)
    return files, failures


def scan_repository(root=ROOT, terms=None):
    if terms is None:
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
    pages, link_errors = iter_markdown(root)
    failures.extend(link_errors)
    for path in pages:
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            failures.append("%s: markdown file is not readable" % path)
            continue
        try:
            label = path.resolve().relative_to(root.resolve()).as_posix()
        except ValueError:
            failures.append("%s: symlink resolves outside the repository" % path)
            continue
        failures.extend(scan_text(text, spec, label))
        for token in hex_findings(text):
            failures.append("%s: hex run %s" % (label, token))
        for line_no, index in term_hits(text, terms):
            failures.append("%s:%s: term %s" % (label, line_no, index))
    for folder_name in ("docs", "examples"):
        base = root / folder_name
        if not base.is_dir():
            continue
        for path in base.rglob("*"):
            if not path.is_file() or path.suffix.lower() == ".md" or path.is_symlink():
                continue
            try:
                relative = path.relative_to(root)
            except ValueError:
                failures.append("%s: symlink resolves outside the repository" % path)
                continue
            if any(part in SKIP_DIRS for part in relative.parts):
                continue
            if path.suffix.lower() not in {".json", ".txt", ".yml", ".yaml"}:
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except OSError:
                failures.append("%s: file is not readable" % relative.as_posix())
                continue
            label = relative.as_posix()
            for token in hex_findings(text):
                failures.append("%s: hex run %s" % (label, token))
            for line_no, index in term_hits(text, terms):
                failures.append("%s:%s: term %s" % (label, line_no, index))
    quick_path = root / "docs" / "customer-rest-api.md"
    if not quick_path.is_file():
        failures.append("quickstart is missing")
    else:
        quick = quick_path.read_text(encoding="utf-8")
        python_found, curl_found = quickstart_calls(quick, spec)
        if python_found != list(QUICKSTART_CALLS):
            failures.append("quickstart python calls are %s" % (python_found,))
        if curl_found != list(QUICKSTART_CALLS):
            failures.append("quickstart curl calls are %s" % (curl_found,))
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
        self.assertTrue(hex_findings("token abc.def0", allow=frozenset()))
        self.assertTrue(hex_findings("token abc def0", allow=frozenset()))
        self.assertTrue(hex_findings("token abcgdef0", allow=frozenset()))
        self.assertTrue(hex_findings("token abcxdef0", allow=frozenset()))
        self.assertTrue(hex_findings("token abczdef0", allow=frozenset()))
        self.assertTrue(hex_findings("token abc--def0", allow=frozenset()))
        self.assertTrue(hex_findings("token 12:34:56.78", allow=frozenset()))
        self.assertFalse(hex_findings("label example-revision"))
        self.assertFalse(hex_findings("body cap 8388608"))
        self.assertFalse(hex_findings("workload added under 6 W"))
        self.assertFalse(hex_findings("for T in 1 2 4 8 16 32 64; do"))
        self.assertFalse(hex_findings("09:00:00Z,22.1,0.12"))
        self.assertFalse(hex_findings("variance\n- effect size"))
        self.assertTrue(hex_findings("token ce-effec0", allow=frozenset()))

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
        return docs

    def test_missing_secret_fails_closed(self):
        previous = os.environ.pop(SECRET_NAME, None)
        try:
            self.assertEqual(scan_repository(ROOT), [MISSING_SECRET])
        finally:
            if previous is not None:
                os.environ[SECRET_NAME] = previous

    def test_short_term_needs_a_boundary(self):
        short_term = "zz"
        self.assertEqual(term_hits("prefix " + short_term + " suffix", [short_term]), [(1, 0)])
        self.assertEqual(term_hits("aa" + short_term + "bb", [short_term]), [])

    def test_encoded_term_is_found(self):
        term = "synth" + "token"
        planted = "".join("%%%02X" % ord(char) for char in term)
        self.assertEqual(term_hits(planted, [term]), [(1, 0)])

    def test_root_markdown_plants(self):
        terms = self.synthetic_terms()
        token = "abc" + "def" + "4"
        long_hex = "ab" * 20
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
            failures = scan_repository(root, terms=terms)
            blob = "\n".join(failures)
            self.assertIn("notes.md", blob)
            self.assertIn("PAGE.MD", blob)
            self.assertIn("benchmarks/note.md", blob)
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

    def test_banned_term(self):
        term = "synth" + "token"
        self.assertEqual([index for _line, index in term_hits("see " + term, [term])], [0])


def prove_secret():
    """Show that CI loaded the term list, without printing a term."""
    terms, error = terms_from_env()
    if error:
        print(error, file=sys.stderr)
        return 1
    for term in terms:
        sys.stdout.write("::add-mask::%s\n" % term)
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        docs = root / "docs"
        docs.mkdir()
        shutil.copy(OPENAPI_PATH, docs / "customer-rest-api.openapi.json")
        shutil.copy(ROOT / "docs" / "customer-rest-api.md", docs / "customer-rest-api.md")
        page = root / "plant.md"
        page.write_text(terms[0] + "\n", encoding="utf-8")
        failures = scan_repository(root, terms=terms)
    blob = "\n".join(failures)
    if terms[0] in blob:
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
        print("vendored spec digest computed")
        return 0
    if "--prove-secret" in argv:
        return prove_secret()
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
