#!/usr/bin/env python3
"""Generate per-language UNET ABI bindings from abi/unet_abi.toml.

abi/unet_abi.toml is the single source of truth for the UNET ABI (function
numbers, error codes, capability bits, ...) and for the UNETLD loader's
error/flag codes, which are part of the same cross-language contract. This
tool renders it into bindings/<target>/... for each consumer language.
Never hand-edit a file under bindings/ - edit the TOML and regenerate.

Modes:
  gen [--target asm|solidc|pascal|all]   write bindings/<target>/...
                                          (default target: all)
  check                                   regenerate into a temp dir and
                                           diff against the committed
                                           bindings/; nonzero exit on drift
  compare --inc FILE                      parse a legacy sjasmplus
                                           "NAME EQU value" style file and
                                           diff its name->value map against
                                           the TOML. Used (a) once, to prove
                                           the TOML migration lost nothing
                                           from the original include/unet.inc,
                                           and (b) as an upstream tripwire in
                                           update_dlls.sh.
"""
import argparse
import filecmp
import re
import shutil
import sys
import tempfile
import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
ABI_TOML = REPO_ROOT / "abi" / "unet_abi.toml"
BINDINGS_DIR = REPO_ROOT / "bindings"

BANNER_ASM = """; ==========================================================================
; GENERATED FILE - DO NOT EDIT.
; Source: abi/unet_abi.toml in unet_libs_core. Regenerate with
; tools/gen_bindings.py gen --target asm.
; ==========================================================================
"""

BANNER_C = """/* ==========================================================================
 * GENERATED FILE - DO NOT EDIT.
 * Source: abi/unet_abi.toml in unet_libs_core. Regenerate with
 * tools/gen_bindings.py gen --target solidc.
 * ========================================================================== */
"""

BANNER_PAS = """{ ==========================================================================
  GENERATED FILE - DO NOT EDIT.
  Source: abi/unet_abi.toml in unet_libs_core. Regenerate with
  tools/gen_bindings.py gen --target pascal.

  This is a bare $I-include (const declarations only), NOT a unit: the
  DSS Turbo Pascal dialect's compiler does not allow a `uses` clause to
  coexist with an $I-included declaration in the same program, so a
  unit/uses wrapper cannot be used by an $I-only consumer such as
  unet_libs_pascal/src/UNETLD.PAS. Include this file with $I, directly
  after DSSCORE.INC/DSSSYS.INC/LIBMAN.INC.
  ========================================================================== }
"""


def load_abi():
    data = tomllib.loads(ABI_TOML.read_text())
    groups = {g["id"]: g for g in data.get("group", [])}
    consts = data.get("const", [])
    prose = {p["id"]: p for p in data.get("prose", [])}
    return data, groups, consts, prose


def consts_by_group(consts):
    by_group = {}
    for c in consts:
        by_group.setdefault(c["group"], []).append(c)
    return by_group


def pascal_name_of(const):
    if "pascal_name" in const:
        return const["pascal_name"]
    return "".join(part.capitalize() for part in const["name"].split("_"))


def c_name_of(const):
    return const.get("c_name", const["name"])


def fmt_asm_value(const):
    fmt = const.get("format", "dec")
    v = const["value"]
    if fmt == "hex4":
        return f"0x{v:04X}"
    if fmt == "hex2":
        return f"0x{v:02X}"
    if fmt == "bin8":
        return f"{v:08b}b"
    return str(v)


def fmt_c_value(const):
    fmt = const.get("format", "dec")
    v = const["value"]
    if fmt in ("hex4",):
        return f"0x{v:04X}"
    if fmt in ("hex2", "bin8"):
        return f"0x{v:02X}"
    return str(v)


def fmt_pascal_value(const):
    fmt = const.get("format", "dec")
    v = const["value"]
    if fmt == "hex4":
        return f"${v:04X}"
    if fmt in ("hex2", "bin8"):
        return f"${v:02X}"
    return str(v)


# ---------------------------------------------------------------------
# asm target
# ---------------------------------------------------------------------
def render_asm(groups, consts, prose):
    lines = [BANNER_ASM.rstrip("\n")]
    header = prose.get("header")
    if header:
        lines.append(";")
        for ln in header["en"].splitlines():
            lines.append(f"; {ln}".rstrip())
        lines.append("; ======================================================")
    lines.append("")
    lines.append("\tIFNDEF\t_UNET_INC")
    lines.append("\tDEFINE\t_UNET_INC")
    lines.append("")

    by_group = consts_by_group(consts)
    for gid, group in groups.items():
        gconsts = by_group.get(gid, [])
        if not gconsts:
            continue
        lines.append("; ------------------------------------------------------")
        lines.append(f"; {group['title_en']}")
        lines.append("; ------------------------------------------------------")
        for c in gconsts:
            value = fmt_asm_value(c)
            comment_lines = c["comment_en"].splitlines() if c.get("comment_en") else []
            first = f"; {comment_lines[0]}" if comment_lines else ""
            lines.append(f"{c['name']}\t\tEQU {value}\t{first}".rstrip())
            for extra in comment_lines[1:]:
                lines.append(f"\t\t\t\t; {extra}")
        note = group.get("note_en")
        if note:
            lines.append("")
            for ln in note.splitlines():
                lines.append(f"; {ln}")
        lines.append("")

    lines.append("\tENDIF")
    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------
# solidc target (K&R-safe #define header)
# ---------------------------------------------------------------------
def render_c(groups, consts, prose):
    lines = [BANNER_C.rstrip("\n"), ""]
    header = prose.get("header")
    if header:
        lines.append("/*")
        for ln in header["en"].splitlines():
            lines.append(f" * {ln}".rstrip())
        lines.append(" */")
    lines.append("")
    lines.append("#ifndef _UNET_H_")
    lines.append("#define _UNET_H_")
    lines.append("")

    by_group = consts_by_group(consts)
    for gid, group in groups.items():
        gconsts = by_group.get(gid, [])
        if not gconsts:
            continue
        lines.append(f"/* {group['title_en']} */")
        for c in gconsts:
            value = fmt_c_value(c)
            comment_lines = c["comment_en"].splitlines() if c.get("comment_en") else []
            name = c_name_of(c)
            if len(comment_lines) <= 1:
                trailer = f" /* {comment_lines[0]} */" if comment_lines else ""
                lines.append(f"#define {name} {value}{trailer}")
            else:
                lines.append("/*")
                for ln in comment_lines:
                    lines.append(f" * {ln}".rstrip())
                lines.append(" */")
                lines.append(f"#define {name} {value}")
        note = group.get("note_en")
        if note:
            lines.append("/*")
            for ln in note.splitlines():
                lines.append(f" * {ln}")
            lines.append(" */")
        lines.append("")

    lines.append("#endif /* _UNET_H_ */")
    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------
# pascal target - bare $I-include const declarations, TP3 "legacy .INC"
# style (NOT a unit: this dialect's compiler does not allow a `uses`
# clause to coexist with an `{$I}`-included declaration in the same
# program - see docs/UNETLD-PAS.md in unet_libs_pascal for how this was
# discovered - so the ABI bindings for Pascal must be $I-able source
# text, not a unit/uses PUI wrapper. Include this file (via $I) before
# UNETLD.PAS.
# ---------------------------------------------------------------------
def render_pascal(groups, consts, prose):
    lines = [BANNER_PAS.rstrip("\n"), ""]
    header = prose.get("header")
    if header:
        lines.append("{")
        for ln in header["en"].splitlines():
            lines.append(f"  {ln}".rstrip())
        lines.append("}")
        lines.append("")
    lines.append("const")

    by_group = consts_by_group(consts)
    for gid, group in groups.items():
        gconsts = by_group.get(gid, [])
        if not gconsts:
            continue
        lines.append(f"  {{ {group['title_en']} }}")
        for c in gconsts:
            value = fmt_pascal_value(c)
            name = pascal_name_of(c)
            comment = c.get("comment_en", "")
            if comment:
                lines.append(f"  {name} = {value};  {{ {comment} }}")
            else:
                lines.append(f"  {name} = {value};")
        note = group.get("note_en")
        if note:
            lines.append(f"  {{ {note} }}")
        lines.append("")

    return "\n".join(lines)


TARGETS = {
    "asm": ("bindings/asm/unet.inc", render_asm),
    "solidc": ("bindings/solidc/UNET.H", render_c),
    "pascal": ("bindings/pascal/UNET.INC", render_pascal),
}


def gen(out_root, targets):
    _, groups, consts, prose = load_abi()
    for t in targets:
        rel_path, render = TARGETS[t]
        text = render(groups, consts, prose)
        dest = out_root / rel_path
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(text)
        print(f"wrote {dest.relative_to(out_root) if out_root != REPO_ROOT else rel_path}")


def cmd_gen(args):
    targets = list(TARGETS.keys()) if args.target in (None, "all") else [args.target]
    gen(REPO_ROOT, targets)
    return 0


def cmd_check(args):
    targets = list(TARGETS.keys())
    with tempfile.TemporaryDirectory() as tmp:
        tmp_root = Path(tmp)
        gen(tmp_root, targets)
        drift = False
        for t in targets:
            rel_path, _ = TARGETS[t]
            committed = REPO_ROOT / rel_path
            fresh = tmp_root / rel_path
            if not committed.is_file():
                print(f"error: {rel_path} does not exist - run 'gen_bindings.py gen'", file=sys.stderr)
                drift = True
                continue
            if not filecmp.cmp(committed, fresh, shallow=False):
                print(f"error: {rel_path} is out of date - run 'gen_bindings.py gen'", file=sys.stderr)
                drift = True
        if drift:
            return 1
        print("bindings/ is up to date with abi/unet_abi.toml")
        return 0


EQU_RE = re.compile(
    r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s+EQU\s+([0-9A-Fa-fXxbB][0-9A-Fa-fXxHhbB]*)",
)


def parse_value(raw):
    raw = raw.strip()
    if raw.lower().startswith("0x"):
        return int(raw, 16)
    if raw.endswith(("b", "B")) and re.fullmatch(r"[01]+[bB]", raw):
        return int(raw[:-1], 2)
    if raw.endswith(("h", "H")):
        return int(raw[:-1], 16)
    return int(raw, 10)


def parse_equ_file(path):
    result = {}
    for line in path.read_text().splitlines():
        m = EQU_RE.match(line)
        if not m:
            continue
        name, raw_value = m.group(1), m.group(2)
        try:
            result[name] = parse_value(raw_value)
        except ValueError:
            continue
    return result


def cmd_compare(args):
    _, _groups, consts, _prose = load_abi()
    toml_map = {c["name"]: c["value"] for c in consts}
    file_map = parse_equ_file(Path(args.inc))

    ok = True
    for name, value in sorted(file_map.items()):
        if name not in toml_map:
            print(f"error: {name} (value {value}) is in {args.inc} but not in abi/unet_abi.toml", file=sys.stderr)
            ok = False
            continue
        if toml_map[name] != value:
            print(
                f"error: {name} value mismatch: {args.inc}={value} toml={toml_map[name]}",
                file=sys.stderr,
            )
            ok = False

    extra = sorted(set(toml_map) - set(file_map))
    if extra:
        print(f"note: abi/unet_abi.toml defines {len(extra)} name(s) not present in {args.inc}: {', '.join(extra)}")

    if ok:
        print(f"{args.inc}: all shared names match abi/unet_abi.toml")
    return 0 if ok else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="mode", required=True)

    p_gen = sub.add_parser("gen", help="write bindings/<target>/...")
    p_gen.add_argument("--target", choices=["asm", "solidc", "pascal", "all"], default="all")
    p_gen.set_defaults(func=cmd_gen)

    p_check = sub.add_parser("check", help="verify bindings/ matches the TOML")
    p_check.set_defaults(func=cmd_check)

    p_compare = sub.add_parser("compare", help="diff a legacy EQU file against the TOML")
    p_compare.add_argument("--inc", required=True, help="path to a sjasmplus 'NAME EQU value' file")
    p_compare.set_defaults(func=cmd_compare)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
