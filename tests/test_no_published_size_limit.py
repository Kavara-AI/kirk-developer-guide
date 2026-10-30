"""The guide publishes no maximum matrix size. Size limits are per deployment and are not published here;
example sizes ("typical sizes are 16 x 16 and 32 x 32") are fine. Fails if a page states a maximum."""
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LIMIT = re.compile(
    r"(?i)\b(max(imum)?|largest|up to|at most|no more than|limit(ed)? (of|to))\b[^.\n]{0,40}"
    r"(\b\d{2,5}\s*(x|×)\s*\d{2,5}\b|\b(n|visible[_ ]nodes|matrix size|dimension)\s*(=|of|is)?\s*\d{2,5}\b)"
    r"|\b(n|visible[_ ]nodes|matrix size|dimension)\s*(<=|≤|<)\s*\d{2,5}\b")


def statements(text):
    return [m.group(0) for m in LIMIT.finditer(text)]


def test_no_page_states_a_maximum_matrix_size():
    files = subprocess.run(["git", "ls-files", "*.md", "*.json", "*.ipynb"], cwd=ROOT,
                           capture_output=True, text=True, check=True).stdout.split()
    found = {f: statements((ROOT / f).read_text(errors="replace")) for f in files if not f.startswith("tests/")}
    assert {f: s for f, s in found.items() if s} == {}


def test_control():
    for planted in ("The maximum matrix size is 64 x 64.", "Kirk accepts up to 4000 × 4000.",
                    "visible_nodes <= 64", "limited to N = 1024"):
        assert statements(planted), planted
    for fine in ("Typical sizes are 16 × 16 and 32 × 32.", "The maximum request body is 256 KiB.",
                 "a square matrix of side 16 or 32"):
        assert not statements(fine), fine
