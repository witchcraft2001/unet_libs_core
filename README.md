# sprinter_unet_libs_core

Language-neutral core of the UNET network stack for Sprinter (Z80 / DSS):
the frozen ABI, the vendored backend DLLs, and the prose API reference. It
has **no git submodules** and pulls in nothing beyond the Python standard
library, so any consumer can vendor it without dragging in dependencies it
does not need.

This repo is not meant to be used standalone - it is the shared foundation
three language-specific repos build on:

| Repo | Language | What it adds on top of this one |
| --- | --- | --- |
| [sprinter_unet_libs_asm](https://github.com/witchcraft2001/sprinter_unet_libs_asm) | Z80 asm (SjASMPlus) | `unetld.asm` loader, runnable examples |
| [sprinter_unet_libs_pascal](https://github.com/witchcraft2001/sprinter_unet_libs_pascal) | Turbo Pascal | `UNETLD.PAS` loader, examples |
| [sprinter_unet_libs_c](https://github.com/witchcraft2001/sprinter_unet_libs_c) | Solid C (SDCC later) | `UNETLD.C` loader, examples |

Each of those vendors this repo as a git submodule at `extern/core` instead
of copying the DLLs, the ABI header or the API docs - so all three always
agree on the ABI, and re-vendoring a new backend DLL or fixing a doc typo
happens in exactly one place.

Every document here exists in both languages - Russian versions carry an
`RU` suffix: [READMERU.md](READMERU.md), [docs/UNETAPIRU.md](docs/UNETAPIRU.md),
[docs/UNETLD-SPECRU.md](docs/UNETLD-SPECRU.md).

## What's in here

```
abi/unet_abi.toml          single source of truth for the UNET ABI and the
                            UNETLD_E_*/UNETLD_F_* loader codes
bindings/asm/unet.inc       generated - SjASMPlus EQU header
bindings/solidc/UNET.H      generated - K&R-safe #define header
bindings/pascal/UNET.PUI    generated - TP3-style const-only unit
dll/UNETESP.DLL             prebuilt WiFi/ESP8266 backend
dll/UNETRTL.DLL             prebuilt ISA RTL8019A backend
dll/manifest.json           size/sha256/version/provenance for both DLLs
docs/UNETAPI.md             UNET function contract (prose reference)
docs/UNETLD-SPEC.md         UNETLD loader/selector behavior (language-neutral)
tools/gen_bindings.py       renders bindings/ from abi/unet_abi.toml
tools/check_dlls.py         verifies the vendored DLLs against the manifest
tools/update_dlls.sh        maintainer tool: re-vendor fresh DLLs
tools/udp_echo.py           host-side UDP echo helper for the UDPECHO example
```

## Using this as a submodule

Only language repos are expected to depend on this directly:

```sh
git submodule add https://github.com/witchcraft2001/sprinter_unet_libs_core.git extern/core
```

Nothing else needs to be recursive - this repo has no submodules of its
own.

## The ABI source of truth

[abi/unet_abi.toml](abi/unet_abi.toml) is the single place every UNET
function number, error code, capability bit, GETINFO field id, SETOPT id
and UNETLD loader code (`UNETLD_E_*`/`UNETLD_F_*`) is defined, together
with its documentation prose. It is **frozen**: existing name/value pairs
never change, only new reserved slots get used.

[tools/gen_bindings.py](tools/gen_bindings.py) renders it into
`bindings/<target>/`:

```sh
tools/gen_bindings.py gen                  # regenerate every target
tools/gen_bindings.py gen --target asm     # just one
tools/gen_bindings.py check                # verify bindings/ matches the TOML (nonzero exit on drift)
tools/gen_bindings.py compare --inc FILE   # diff a legacy "NAME EQU value" file's
                                            # name->value map against the TOML
```

Generated files carry a `GENERATED - DO NOT EDIT` banner - edit the TOML
and re-run `gen`, never hand-edit anything under `bindings/`. `make check`
runs both `gen_bindings.py check` and `check_dlls.py`.

Because the generated `bindings/asm/unet.inc` is not byte-identical to the
original hand-written `include/unet.inc` it replaced (different banner,
regenerated comment formatting), byte-for-byte diffing is not how drift is
caught here. Two checks stand in for it: `gen_bindings.py compare`
proves the *name -> value* map matches an external file exactly (used both
as a one-time migration proof and as the upstream tripwire in
`update_dlls.sh`, below), and each consumer repo's own example EXEs must
byte-for-byte match their pre-migration builds (constant values are
identical, so the assembled code is too).

## Maintaining the vendored DLLs

```sh
tools/update_dlls.sh
```

Copies fresh `UNETESP.DLL`/`UNETRTL.DLL` from sibling backend-project
checkouts (override with the `UNETESP_SRC`/`UNETRTL_SRC` environment
variables), updates `dll/manifest.json`'s size/sha256 (bump the `version`
field by hand), re-verifies, and warns if the frozen ABI in
`abi/unet_abi.toml` has drifted from the upstream `unet.inc` it was
vendored from (via `gen_bindings.py compare`, not a byte `cmp` - see
above).

`tools/check_dlls.py` verifies size and sha256 against the manifest on its
own - no dependencies beyond this repo. It can additionally run
`sprinter_mkdll verify` (a stronger structural check) if you point
`LIBMAN_ROOT` at a libman checkout, e.g. the one vendored by
`unet_libs_asm`:

```sh
LIBMAN_ROOT=../unet_libs_asm/extern/libman tools/check_dlls.py
```

Without `LIBMAN_ROOT` that step is skipped with a note (still exit 0 as
long as size/sha256 match); `--require-mkdll` turns a missing
`LIBMAN_ROOT` into a hard failure. `update_dlls.sh` defaults `LIBMAN_ROOT`
to the sibling `unet_libs_asm/extern/libman` checkout when present, and
always requires it.

The DLL's L1 name is checked only by prefix at load time (`UNET` + the
`NET` tag) - the version suffix is intentionally not pinned there. The
`sha256` in `dll/manifest.json` is the real build-time identity.

## Environment variables

`NET` selects the backend: its value (3-4 characters, `[A-Z0-9]`, case
insensitive) becomes the DLL name directly - `NET=RTL` loads
`UNETRTL.DLL`, `NET=WIZ` would load `UNETWIZ.DLL`, and so on. `WIFI` is the
one built-in exception, aliased to `UNETESP.DLL` for compatibility with
existing tooling. See [docs/UNETLD-SPEC.md](docs/UNETLD-SPEC.md#adding-a-backend)
for how a new backend fits into this scheme.

`NET` is *published by the backend's bring-up tool*, together with the
rest of that backend's configuration - it is not something users (or
consumer programs) set by hand. If it is missing, the right fix is always
"run the bring-up tool", never `SET NET=...`:

| Backend | Bring-up tool | Publishes |
| --- | --- | --- |
| WiFi (`UNETESP.DLL`) | `NETUP` | `NET=WIFI`, `NET_ESP_*`, `NET_IP`/`NET_MASK`/`NET_GW`/`NET_MAC`/... |
| RTL8019A (`UNETRTL.DLL`) | `NETCFG -i` then `IFUP` | `NET=RTL`, `NET_RTL_*`, `NET_IP`/`NET_MASK`/`NET_GW`/`NET_MAC`/... |

Get the bring-up tools from your backend's own distribution: `NETUP` comes
with the WiFi kit ([sprinter_net](https://github.com/witchcraft2001/sprinter_net)),
`NETCFG`/`IFUP` with the RTL kit
([sprinter-rtl8019a](https://github.com/witchcraft2001/sprinter-rtl8019a)).
`UNET_FN_STATUS` called with `A=0xFF` checks that this environment was
published without touching any hardware - useful for a friendly "run
NETUP/IFUP first" message. See [docs/UNETAPI.md](docs/UNETAPI.md) for the
full variable list and the UNET function reference.

## Memory-map rules

These come from the UNET ABI itself (see `abi/unet_abi.toml`) and from DSS:

- Load a DLL into window 1 (`0x4000`) or window 2 (`0x8000`) only - **never
  window 3** (`0xC000`); the ESP backend maps hardware there during every
  call.
- Every buffer you pass to a UNET function (host/port strings, send/recv
  payloads, `GETINFO` destinations) must live below `0xC000` and entirely
  outside the DLL's own window.
- Host strings are limited to 128 bytes, port strings to 15 bytes.
- Keep at least ~256 bytes of free stack across a UNET call.
- UNET is not reentrant - one call at a time.

## License

BSD 3-Clause, see [LICENSE](LICENSE). The vendored DLLs remain subject to
their own upstream projects' licenses - see `dll/manifest.json` for
provenance.
