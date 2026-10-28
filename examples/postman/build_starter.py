#!/usr/bin/env python3
"""Build examples/postman/Kirk-Engineer-Starter.zip from starter/.

The zip member bytes match the loose files. Timestamps and permissions are
fixed so a second run writes the same archive.
"""

import io
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "starter"
ZIP_PATH = ROOT / "Kirk-Engineer-Starter.zip"
EPOCH = (1980, 1, 1, 0, 0, 0)


def loose_files():
    files = sorted(
        path for path in SOURCE.iterdir() if path.is_file() and not path.name.startswith(".")
    )
    if not files:
        raise SystemExit("no files in examples/postman/starter")
    return files


def archive_bytes(files):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in files:
            info = zipfile.ZipInfo(filename=path.name, date_time=EPOCH)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            info.external_attr = (0o644 & 0xFFFF) << 16
            archive.writestr(info, path.read_bytes())
    return buffer.getvalue()


def check():
    files = loose_files()
    expected_names = [path.name for path in files]
    with zipfile.ZipFile(ZIP_PATH) as archive:
        if archive.namelist() != expected_names:
            print("zip member list does not match examples/postman/starter", file=sys.stderr)
            return 1
        for path in files:
            if archive.read(path.name) != path.read_bytes():
                print(f"{path.name} in the zip differs from starter/{path.name}", file=sys.stderr)
                return 1
    if archive_bytes(files) != ZIP_PATH.read_bytes():
        print("rebuilt zip bytes differ from the committed zip", file=sys.stderr)
        return 1
    print("starter zip matches starter/ byte for byte")
    return 0


def main():
    files = loose_files()
    payload = archive_bytes(files)
    if len(sys.argv) > 1 and sys.argv[1:] == ["--check"]:
        return check()
    if len(sys.argv) > 1:
        raise SystemExit("usage: build_starter.py [--check]")
    ZIP_PATH.write_bytes(payload)
    print(f"wrote {ZIP_PATH.relative_to(ROOT.parent.parent)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
