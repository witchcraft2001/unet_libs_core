Read this in Russian: [UNETLD-SPECRU.md](UNETLD-SPECRU.md).

# UNETLD - language-neutral loader/selector specification

UNETLD reads the `NET` environment variable, resolves it to a UNET backend
DLL name, loads that DLL through
[libman](https://github.com/witchcraft2001/sprinter-libman), validates its
ABI and capabilities, and gives the caller a thin wrapper around
`libman.l_call` plus a `NETINIT`/`NETDONE` lifecycle.

This document specifies the *behavior* every UNETLD port must reproduce,
independent of language. It is the contract three implementations are
checked against:

- `unet_libs_asm/include/unetld.asm` - the original, reference
  implementation (SjASMPlus `MODULE UNETLD`).
- `unet_libs_pascal/src/UNETLD.PAS` - Turbo Pascal include file.
- `unet_libs_c/solidc/src/UNETLD.C` - Solid C.

See [UNETAPI.md](UNETAPI.md) for the UNET function contract itself
(function numbers, register conventions, error codes, capability bits).
This document only covers the selector/loader layer above it, and the
constants below (`UNETLD_E_*`, `UNETLD_F_*`) are defined in
[abi/unet_abi.toml](../abi/unet_abi.toml) alongside the UNET ones - all
three ports share the same numeric values for them.

Each language port adapts entry-point names and state layout to its own
conventions (see that port's own README/reference doc for the exact
signatures); what must not vary is the algorithm, the error conditions, and
the numeric codes below.

---

## Backend selection (SELECT)

1. Read the `NET` environment variable. Not set, or empty -> `E_NOENV`.
2. Upper-case the value in place, measuring its length as it goes.
3. Length must be 3 or 4 characters -> otherwise `E_BADVALUE`. (The raw,
   upper-cased value is kept available for diagnostics - state field
   `ENV_VALUE`.)
4. Every character must be `[A-Z0-9]` -> otherwise `E_BADVALUE`.
5. Alias lookup: a small table of `{value, tag}` pairs. The one built-in
   entry is `WIFI -> ESP` (`NETUP` publishes `NET=WIFI` for backward
   compatibility; the DLL is `UNETESP.DLL`). No match -> the validated
   value itself is the tag. A tag is at most 4 characters.
6. Build `DLL_NAME = "UNET" + tag + ".DLL"`.
7. On success, clear the last-error state and return the resolved tag and
   DLL name.

A normal new backend that follows the `NET` = DLL-tag convention (e.g.
`NET=RTL` -> `UNETRTL.DLL`) needs no alias table entry at all - only an
exception like `WIFI -> ESP` does.

## Two independent failure planes (CALL)

Every dispatched UNET function (see UNETAPI.md) can fail in two unrelated
ways, and a UNETLD port must expose both, distinctly:

1. **Dispatcher/DSS failure** - the libman call itself could not be made
   (bad handle, DSS/`SETWINn` failure, ...). In the asm reference this is
   the carry flag; a Pascal/C port surfaces it as a boolean/int return
   value of its `CALL` wrapper (false / -1), *not* through the UNET status.
2. **UNET status** - the function's own `NERR_*` result, always returned in
   `A` regardless of the dispatcher outcome. A dispatcher success does not
   imply `NERR_OK`; callers (and UNETLD's own NETSTART, below) must check
   both planes separately.

## Entry-point behavior

### RESET
Zero the entire state block. Always safe to call, including before any
other entry point and repeatedly (e.g. after `UNLOAD`).

### SELECT
See "Backend selection" above.
Out: success -> tag/DLL name resolved, last error cleared.
Failure -> `E_NOENV` or `E_BADVALUE`, raw value kept for messages.

### LOAD(window)
Requires a prior successful `SELECT`. `window` must be 1 (`0x4000`) or 2
(`0x8000`) - **never 3** (`0xC000`; see the window rules in UNETAPI.md).

1. `l_load` the resolved `DLL_NAME` into `window`. Failure -> `E_LOAD` (no
   handle is open; nothing further to clean up).
2. Store the handle, mark it loaded.
3. `l_info` the loaded DLL into a 32-byte header buffer. Failure ->
   `E_INFO`.
4. Validate the DLL's L1 name at header offset 16: it must start with
   `"UNET"` followed by the resolved tag. Only the prefix is checked - the
   version suffix is intentionally not validated here (the DLL's sha256 in
   `dll/manifest.json` is the real build-time identity check). Mismatch ->
   `E_NAME`.
5. Call `GETCAPS` through the CALL wrapper. Dispatcher failure -> `E_CALL`.
   A non-`NERR_OK` UNET status also -> `E_CALL` (the status is kept in
   `LAST_STATUS` either way).
6. Store `CAPS` (capability bitmask) and `ABI` (ABI word) from the result.
7. Compare the ABI word's high byte against the high byte of
   `UNET_ABI_VERSION`. Mismatch -> `E_ABI`.
8. Success: clear the last error; the handle, caps and ABI are available to
   the caller.

**Important:** on any failure from step 3 onward (`E_INFO`, `E_NAME`,
`E_CALL`, `E_ABI`) the DLL handle from step 1 is still open - the caller
(or the port's own error path) must call `UNLOAD` before retrying or
exiting. Only `E_LOAD` itself leaves nothing open.

### CALL(fn, regs)
Dispatch one UNET function on the loaded handle. This is a thin pass
through to libman's own call primitive - see "Two independent failure
planes" above. No UNETLD-level validation beyond having a loaded handle;
the arguments and results follow the UNET ABI in UNETAPI.md.

### NETSTART
Requires a prior successful `LOAD`. Does not bring the network up itself -
that is the backend kit's job (`NETUP`, or `NETCFG`/`IFUP`), done
beforehand; it only gets the *DLL* ready to use that already-published
network.

1. `STATUS` with channel `0xFF` through CALL (this variant is
   intentionally hardware-free - it only checks that the environment is
   present). Dispatcher failure -> `E_CALL`. Store the status in
   `LAST_STATUS`. Accept `NERR_OK` or `NERR_NONET`; anything else ->
   `E_STATUS`.
2. `NETINIT` through CALL. Dispatcher failure -> `E_CALL`. Store the status
   in `LAST_STATUS`. Non-`NERR_OK` -> `E_NETINIT`.
3. Success: set the NETINIT flag, clear the last error.

### REQUIRE(mask)
Pure capability gate: `(CAPS & mask) == mask`. Does **not** touch the last
error - callers report a missing capability themselves, however they see
fit.

### UNLOAD
Idempotent teardown, safe to call on every error path and more than once:

1. If the NETINIT flag is set, best-effort `NETDONE` through CALL (result
   ignored - this is cleanup, not a place to fail).
2. If the loaded flag is set, `l_free` the handle (also best-effort).
3. `RESET` the whole state block.

Always "succeeds" (no failure outcome to report).

## State surface (read-only)

Same meaning in every port; exact identifier spelling follows that
language's own naming convention (see the port's reference doc).

| Field | Size | Meaning |
| --- | --- | --- |
| `HANDLE` | 2 bytes / int | libman handle of the loaded DLL |
| `CAPS` | 2 bytes / int | `GETCAPS` capability bitmask |
| `ABI` | 2 bytes / int | `GETCAPS` ABI word (major\<\<8\|minor) |
| `ERROR` | 1 byte | last `UNETLD_E_*` code |
| `LAST_STATUS` | 1 byte | last `NERR_*` from `STATUS`/`NETINIT` |
| `FLAGS` | 1 byte | `UNETLD_F_*` bits |
| `NET_TAG` | up to 5 bytes | resolved tag, ASCIIZ, up to 4 chars |
| `DLL_NAME` | up to 13 bytes | `"UNETxxxx.DLL"`, ASCIIZ |
| `DLL_INFO` | 32 bytes | libman `l_info` destination |
| `ENV_VALUE` | up to 256 bytes | raw/upper-cased `NET` value |

## Error codes (`UNETLD_E_*`)

Defined in [abi/unet_abi.toml](../abi/unet_abi.toml) (group `unetld_e`);
identical numeric values across every port.

| Constant | Value | Set by |
| --- | --- | --- |
| `UNETLD_E_NOENV` | 1 | `SELECT` - `NET` not set or empty |
| `UNETLD_E_BADVALUE` | 2 | `SELECT` - `NET` not 3-4 chars of `[A-Z0-9]` |
| `UNETLD_E_LOAD` | 3 | `LOAD` - `l_load` failed |
| `UNETLD_E_INFO` | 4 | `LOAD` - `l_info` failed |
| `UNETLD_E_NAME` | 5 | `LOAD` - DLL name mismatch |
| `UNETLD_E_CALL` | 6 | `LOAD`/`NETSTART` - dispatcher failure or bad `GETCAPS` status |
| `UNETLD_E_ABI` | 7 | `LOAD` - unsupported major ABI version |
| `UNETLD_E_STATUS` | 8 | `NETSTART` - unexpected `STATUS(0xFF)` result |
| `UNETLD_E_NETINIT` | 9 | `NETSTART` - `NETINIT` failed |

## State flags (`UNETLD_F_*`)

Defined in [abi/unet_abi.toml](../abi/unet_abi.toml) (group `unetld_f`).

| Constant | Bit | Meaning |
| --- | --- | --- |
| `UNETLD_F_LOADED` | 0 | DLL handle is open |
| `UNETLD_F_NETINIT` | 1 | `NETINIT` succeeded |

## What is intentionally NOT part of this cross-language spec

- **State placement strategy.** `unet_libs_asm/include/unetld.asm` offers
  two placement modes (state embedded in the image vs. an address-only
  `UNETLD_STATE_BASE`); this is an asm/SjASMPlus-specific memory-layout
  concern with no Pascal/C equivalent. Pascal and C ports simply keep their
  state as an ordinary global record/struct.
- **Register-level calling convention** of the entry points themselves
  (`JR`/`JP` range, which registers hold which argument) - each port
  follows its own language's normal calling convention instead; only the
  UNET function-level ABI (arguments in A/DE/IX/IY, see UNETAPI.md) is
  fixed.
- One invariant every port's state layout must still honour: everything
  it keeps must live in memory the running program owns, below `0xC000`
  (the asm reference asserts this at build time; other ports simply never
  place this state above that line).

## Adding a backend

1. Vendor `dll/UNET<TAG>.DLL` (built against the frozen ABI in
   `abi/unet_abi.toml`) into `unet_libs_core`, and add its entry to
   `dll/manifest.json`.
2. If its `NET` value should differ from its DLL tag (like `WIFI` ->
   `ESP`), add one row to the alias table in *every* port
   (`unetld.asm`'s `ALIAS_TABLE`, and the equivalent in the Pascal/C
   ports). Otherwise nothing else changes - once the new backend's bring-up
   tool publishes `NET=<TAG>` (the way `NETUP` publishes `NET=WIFI` and
   `NETCFG`/`IFUP` publish `NET=RTL` - users never set `NET` by hand),
   everything above just works, in every language.
