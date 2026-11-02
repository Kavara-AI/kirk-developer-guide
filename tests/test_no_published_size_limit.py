"""The guide publishes no maximum matrix size. Size limits are per deployment and are not published here;
example sizes ("typical sizes are 16 x 16 and 32 x 32") are fine. Fails if a page states a maximum."""
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NUM = r"\d{1,5}(?:,\d{3})*"
GAP = (
    r"(?:(?!\b(?:for\s+an?|request\s+body|response\s+body|payload|[kmgt]i?b|bytes?)\b)"
    r"[^.\n]){0,40}"
)
TARGET = (
    rf"(?:\b{NUM}\s*(?:x|\u00d7)\s*{NUM}\b"
    rf"|\b(?:n|visible[_ ]nodes|matrix\s+size|dimension)\s*(?:=|:|of|is)?\s*{NUM}\b"
    rf"|\b{NUM}\s*visible[_ ]nodes\b)"
)
LIMIT = re.compile(
    rf"(?i)\b(?:max(?:imum)?|largest|up to|at most|no more than|limit(?:ed)? (?:of|to))\b{GAP}{TARGET}"
    rf"|\b(?:n|visible[_ ]nodes|matrix\s+size|dimension)\s*(?:<=|\u2264|<)\s*{NUM}\b"
)


def _normalize_soft_breaks(text):
    return re.sub(r"(?<!\n)\r?\n(?!\r?\n)", " ", text)


def _json_strings(obj):
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, dict):
        for key, value in obj.items():
            if isinstance(key, str):
                yield key
            yield from _json_strings(value)
    elif isinstance(obj, list):
        for item in obj:
            yield from _json_strings(item)


def statements(text, is_json=False):
    chunks = [text]
    if is_json:
        try:
            chunks.append("\n".join(_json_strings(json.loads(text))))
        except ValueError:
            pass
    matches = []
    for chunk in chunks:
        for match in LIMIT.finditer(_normalize_soft_breaks(chunk)):
            value = match.group(0)
            if value not in matches:
                matches.append(value)
    return matches


def test_no_page_states_a_maximum_matrix_size():
    files = [
        f
        for f in subprocess.run(
            ["git", "ls-files", "-z", "*.md", "*.json", "*.ipynb"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=True,
        ).stdout.split("\0")
        if f and not f.startswith("tests/")
    ]
    found = {
        f: statements(
            (ROOT / f).read_text(encoding="utf-8", errors="replace"),
            is_json=Path(f).suffix in {".json", ".ipynb"},
        )
        for f in files
    }
    assert {f: s for f, s in found.items() if s} == {}


def test_control():
    for planted in (
        "The maximum matrix size is 64 x 64.",
        "The maximum matrix size\nis 64 x 64.",
        "Kirk accepts up to 4000 \u00d7 4000.",
        "Kirk accepts up to 1,024 \u00d7 1,024.",
        "Kirk supports up to 64 visible nodes.",
        "Maximum visible nodes: 64",
        "visible_nodes <= 64",
        "visible_nodes <= 8",
        "limited to N = 1024",
    ):
        assert statements(planted), planted
    assert statements(
        '{"description": "Kirk accepts up to 4000 \\u00d7 4000."}',
        is_json=True,
    )
    for fine in (
        "Typical sizes are 16 \u00d7 16 and 32 \u00d7 32.",
        "The maximum request body is 256 KiB.",
        "The maximum request body is 256 KiB for a 16 \u00d7 16 matrix.",
        "a square matrix of side 16 or 32",
    ):
        assert not statements(fine), fine
