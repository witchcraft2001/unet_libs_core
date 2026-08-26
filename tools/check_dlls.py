#!/usr/bin/env python3
"""Verify vendored UNET*.DLL binaries against dll/manifest.json.

Checks that every DLL listed in the manifest exists and matches the
recorded size and SHA-256. That check alone needs nothing beyond this
repo, so it always runs.

The stronger `sprinter_mkdll verify` check additionally needs a checkout
of the libman sources (this repo has no submodules - see
../unet_libs_asm/extern/libman for a consumer that vendors it). Point
LIBMAN_ROOT at such a checkout to enable it:

    LIBMAN_ROOT=../unet_libs_asm/extern/libman tools/check_dlls.py

Without LIBMAN_ROOT, mkdll verify is skipped with a note (exit 0 as long
as size/sha256 match). Pass --require-mkdll to make a missing LIBMAN_ROOT
a hard failure - update_dlls.sh does this, defaulting LIBMAN_ROOT to the
sibling unet_libs_asm/extern/libman checkout if present.

With --update, recomputes size/sha256 in place instead of checking them
(version/source/tag/caps are left untouched).
"""
import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DLL_DIR = REPO_ROOT / "dll"
MANIFEST_PATH = DLL_DIR / "manifest.json"


def sha256_of(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def run_mkdll_verify(dll_path, libman_root, require):
    if libman_root is None:
        msg = f"note: {dll_path.name}: skipping sprinter_mkdll verify (LIBMAN_ROOT not set)"
        if require:
            print(f"error: --require-mkdll set but LIBMAN_ROOT is not set", file=sys.stderr)
            return False
        print(msg)
        return True

    libman_src = Path(libman_root) / "src"
    if not libman_src.is_dir():
        print(f"error: {libman_src} not found (from LIBMAN_ROOT={libman_root})", file=sys.stderr)
        return False

    full_env = dict(os.environ)
    full_env["PYTHONPATH"] = str(libman_src)
    proc = subprocess.run(
        [sys.executable, "-m", "sprinter_mkdll.cli", "verify", str(dll_path), "--target", "1.3"],
        env=full_env,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        print(f"error: sprinter_mkdll verify failed for {dll_path.name}:", file=sys.stderr)
        print(proc.stdout, file=sys.stderr)
        print(proc.stderr, file=sys.stderr)
        return False
    print(proc.stdout.strip())
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--update", action="store_true", help="recompute size/sha256 in the manifest instead of checking them"
    )
    parser.add_argument(
        "--require-mkdll", action="store_true", help="fail if LIBMAN_ROOT is not set, instead of skipping mkdll verify"
    )
    args = parser.parse_args()

    libman_root = os.environ.get("LIBMAN_ROOT")

    if not MANIFEST_PATH.is_file():
        print(f"error: manifest not found at {MANIFEST_PATH}", file=sys.stderr)
        return 1

    manifest = json.loads(MANIFEST_PATH.read_text())
    ok = True

    for name, entry in manifest.items():
        dll_path = DLL_DIR / name
        if not dll_path.is_file():
            print(f"error: {name} missing at {dll_path}", file=sys.stderr)
            ok = False
            continue

        size = dll_path.stat().st_size
        digest = sha256_of(dll_path)

        if args.update:
            entry["size"] = size
            entry["sha256"] = digest
            print(f"{name}: updated size={size} sha256={digest}")
            continue

        if size != entry["size"]:
            print(
                f"error: {name} size mismatch: manifest={entry['size']} actual={size}",
                file=sys.stderr,
            )
            ok = False
        if digest != entry["sha256"]:
            print(
                f"error: {name} sha256 mismatch:\n  manifest={entry['sha256']}\n  actual  ={digest}",
                file=sys.stderr,
            )
            ok = False
        if size == entry["size"] and digest == entry["sha256"]:
            print(f"{name}: size and sha256 match manifest")

        if not run_mkdll_verify(dll_path, libman_root, args.require_mkdll):
            ok = False

    if args.update:
        MANIFEST_PATH.write_text(json.dumps(manifest, indent=2) + "\n")
        print(f"manifest updated: {MANIFEST_PATH}")

    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
