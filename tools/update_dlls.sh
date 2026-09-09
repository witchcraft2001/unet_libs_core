#!/usr/bin/env bash
# Maintainer tool: refresh vendored UNET*.DLL binaries from sibling backend
# checkouts, update dll/manifest.json, and re-run verification.
#
# Usage: tools/update_dlls.sh
# Env overrides:
#   UNETESP_SRC  path to UNETESP.DLL              (default: sibling sprinter_wifi/network checkout)
#   UNETRTL_SRC  path to UNETRTL.DLL               (default: sibling sprinter-rtl8019a checkout)
#   LIBMAN_ROOT  path to a libman checkout, for sprinter_mkdll verify
#                (default: sibling unet_libs_asm/extern/libman, if present)
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

UNETESP_SRC="${UNETESP_SRC:-$repo_root/../../../sprinter_wifi/network/UNETESP.DLL}"
UNETRTL_SRC="${UNETRTL_SRC:-$repo_root/../../../sprinter-rtl8019a/UNETRTL.DLL}"
default_libman_root="$repo_root/../unet_libs_asm/extern/libman"
if [[ -z "${LIBMAN_ROOT:-}" && -d "$default_libman_root/src" ]]; then
    LIBMAN_ROOT="$default_libman_root"
fi
export LIBMAN_ROOT="${LIBMAN_ROOT:-}"

esp_version_file="$(dirname "$UNETESP_SRC")/UNETESP_VERSION"
rtl_version_inc="$(dirname "$UNETRTL_SRC")/src/include/version.inc"

if [[ ! -f "$UNETESP_SRC" ]]; then
    echo "error: UNETESP.DLL source not found at $UNETESP_SRC (set UNETESP_SRC)" >&2
    exit 1
fi
if [[ ! -f "$UNETRTL_SRC" ]]; then
    echo "error: UNETRTL.DLL source not found at $UNETRTL_SRC (set UNETRTL_SRC)" >&2
    exit 1
fi

cp "$UNETESP_SRC" "$repo_root/dll/UNETESP.DLL"
cp "$UNETRTL_SRC" "$repo_root/dll/UNETRTL.DLL"

esp_version="unknown"
if [[ -f "$esp_version_file" ]]; then
    esp_version="$(cat "$esp_version_file")"
fi
rtl_version="unknown"
if [[ -f "$rtl_version_inc" ]]; then
    rtl_version="$(grep -oE 'PACKAGE_VERSION "[^"]+"' "$rtl_version_inc" | sed -E 's/.*"([^"]+)"/\1/')"
fi

echo "UNETESP.DLL source version: $esp_version"
echo "UNETRTL.DLL source version: $rtl_version"
echo "Update dll/manifest.json \"version\" fields by hand if they changed."

python3 "$repo_root/tools/check_dlls.py" --update

echo
echo "Re-verifying updated DLLs..."
if [[ -n "$LIBMAN_ROOT" ]]; then
    python3 "$repo_root/tools/check_dlls.py" --require-mkdll
else
    python3 "$repo_root/tools/check_dlls.py"
fi

# Freeze tripwire: warn if the frozen ABI has changed upstream. Semantic
# comparison (name -> value), not byte-for-byte: bindings/asm/unet.inc is
# generated from abi/unet_abi.toml and carries its own banner/formatting,
# so it is never byte-identical to upstream's include/unet.inc even when
# every constant agrees.
esp_unet_inc="$(dirname "$UNETESP_SRC")/src/include/unet.inc"
if [[ -f "$esp_unet_inc" ]]; then
    if ! python3 "$repo_root/tools/gen_bindings.py" compare --inc "$esp_unet_inc"; then
        echo
        echo "WARNING: abi/unet_abi.toml differs from $esp_unet_inc" >&2
        echo "The frozen UNET ABI may have changed upstream - review before re-vendoring." >&2
    fi
fi
