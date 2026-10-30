#!/usr/bin/env python3
"""Release helpers, used by .github/workflows/release.yml and for a release by hand.

    python tools/release.py version
    python tools/release.py check [vX.Y.Z]
    python tools/release.py pack vX.Y.Z <dist dir> <notes.md>

version: prints VERSION from installer/build_installer.py.
check: the version in installer/build_installer.py (VERSION), installer/setup.rc and
installer/app.manifest is the same, and equals the tag if one is given (a suffix such as
-rc.1 is allowed).
pack: <dist dir> must hold crt-emu-setup-X.Y.Z.exe (build_installer.py --out). Adds
crt-emu-X.Y.Z.zip with the setup's payload in the layout of the game folder, as a new install
writes it (ddraw.ini and the texts with CRLF; no section for "Heroes3 HD.exe"), SHA256SUMS.txt,
and writes the release text from .github/release-notes.md and the X.Y.Z section of CHANGELOG.md.
"""
import hashlib
import os
import re
import subprocess
import sys
import time
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "installer"))
from build_installer import PAYLOAD, VERSION  # noqa: E402  (one list of files for the setup and the zip)


def read(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as f:
        return f.read()


def version_errors(tag=None):
    errs = []
    if not re.fullmatch(r"\d+\.\d+\.\d+", VERSION):
        return [f"build_installer.py: VERSION {VERSION!r} is not X.Y.Z"]
    nums = ",".join(VERSION.split(".")) + ",0"
    rc = read("installer/setup.rc")
    found = {
        "setup.rc FILEVERSION": (re.search(r"^FILEVERSION\s+([\d,]+)", rc, re.M), nums),
        "setup.rc PRODUCTVERSION": (re.search(r"^PRODUCTVERSION\s+([\d,]+)", rc, re.M), nums),
        "setup.rc FileVersion": (re.search(r'"FileVersion",\s*"([^"]*)"', rc), VERSION + ".0"),
        "setup.rc ProductVersion": (re.search(r'"ProductVersion",\s*"([^"]*)"', rc), VERSION),
        "app.manifest": (re.search(r'name="crt-emu\.Setup"\s+version="([^"]*)"', read("installer/app.manifest")),
                         VERSION + ".0"),
    }
    for where, (m, want) in found.items():
        if not m:
            errs.append(f"{where}: not found")
        elif m.group(1) != want:
            errs.append(f"{where}: {m.group(1)}, expected {want}")
    if tag is not None and (not tag.startswith("v") or tag[1:].split("-")[0] != VERSION):
        errs.append(f"tag {tag}: expected v{VERSION}")
    return errs


def check(tag=None):
    errs = version_errors(tag)
    for e in errs:
        print("FAIL", e)
    if not errs:
        print(f"version {VERSION} OK" + (f", tag {tag}" if tag else ""))
    return 1 if errs else 0


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def changes(version):
    m = re.search(rf"^## {re.escape(version)}\s*\n(.*?)(?=^## |\Z)", read("CHANGELOG.md"), re.M | re.S)
    return m.group(1).strip() if m else ""


def pack(tag, dist, notes_path):
    if check(tag):
        return 1
    name = tag[1:]
    setup = os.path.join(dist, f"crt-emu-setup-{name}.exe")
    if not os.path.exists(setup):
        print("FAIL no", setup)
        return 1
    text = changes(VERSION)
    if not text:
        print(f"FAIL CHANGELOG.md has no section ## {VERSION}")
        return 1

    zpath = os.path.join(dist, f"crt-emu-{name}.zip")
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        for src, dst, kind in PAYLOAD:
            with open(os.path.join(ROOT, src), "rb") as f:
                data = f.read()
            if kind in ("P_INI", "P_DOC"):  # as the setup writes them (crtemu_to_crlf in installer/logic.c)
                data = re.sub(rb"(?<!\r)\n", b"\r\n", data)
            z.writestr(zipfile.ZipInfo(dst.replace("\\", "/"), date_time=time.localtime()[:6]), data,
                       zipfile.ZIP_DEFLATED)
    sums = {os.path.basename(p): sha256(p) for p in (setup, zpath)}
    with open(os.path.join(dist, "SHA256SUMS.txt"), "w", newline="\n") as f:
        f.writelines(f"{h}  {n}\n" for n, h in sums.items())

    fork = subprocess.run(["git", "-C", os.path.join(ROOT, "third_party", "cnc-ddraw"), "rev-parse", "--short=7", "HEAD"],
                          capture_output=True, text=True).stdout.strip()
    notes = read(".github/release-notes.md")
    built_by = "GitHub Actions" if os.environ.get("GITHUB_ACTIONS") == "true" else "hand"
    for key, value in {"{built_by}": f"Built by {built_by} from tag `{tag}`.",
                       "{version}": name, "{changes}": text, "{fork}": fork or "unknown",
                       "{sha_setup}": sums[os.path.basename(setup)], "{sha_zip}": sums[os.path.basename(zpath)]}.items():
        notes = notes.replace(key, value)
    with open(notes_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(notes)
    for n, h in sums.items():
        print(f"{h}  {n} ({os.path.getsize(os.path.join(dist, n))} bytes)")
    print(f"{len(PAYLOAD)} files in {os.path.basename(zpath)}; release text -> {notes_path}")
    return 0


def main():
    a = sys.argv[1:]
    if a == ["version"]:
        print(VERSION)
        return 0
    if a[:1] == ["check"] and len(a) <= 2:
        return check(a[1] if len(a) == 2 else None)
    if a[:1] == ["pack"] and len(a) == 4:
        return pack(a[1], a[2], a[3])
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main())
