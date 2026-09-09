# Repository Guidelines

## Project Structure & Module Organization

This repository is the language-neutral UNET core for Sprinter/DSS. The
frozen ABI lives in `abi/unet_abi.toml`; it is the source of truth for every
constant and its accompanying prose. `tools/gen_bindings.py` renders that ABI
into the checked-in, generated headers in `bindings/asm/`, `bindings/solidc/`,
and `bindings/pascal/`. Do not edit generated bindings directly.

Vendored backend binaries and their checksums are in `dll/`. English API and
loader specifications are in `docs/`; Russian counterparts use the `RU`
suffix. The small `tools/` directory contains Python maintenance and
verification utilities.

## Build, Test, and Development Commands

The project has no dependency installation or standalone build. Use:

```sh
make check                         # validate generated bindings and DLL hashes
make gen                           # regenerate every language binding
tools/gen_bindings.py gen --target asm
tools/gen_bindings.py check        # fail when committed bindings are stale
tools/check_dlls.py                # verify DLL size and SHA-256 manifest
```

For a fuller DLL structural check, use
`LIBMAN_ROOT=../unet_libs_asm/extern/libman tools/check_dlls.py`. Run
`make check` before submitting any change to the ABI, generated bindings, or
vendored artifacts.

## Coding Style & Naming Conventions

Use Python 3 standard-library code only unless the project deliberately gains
a dependency. Follow the existing tools: four-space indentation, descriptive
`snake_case` functions and variables, `Path` for repository paths, and simple
command-line interfaces via `argparse`. Keep documentation direct and retain
both English and Russian documents when changing shared API prose.

ABI entries retain their established names and numeric values. The ABI is
append-only: add a new reserved slot rather than renumbering or redefining an
existing constant. After modifying `abi/unet_abi.toml`, regenerate bindings
with `make gen`.

## Testing Guidelines

There is no separate unit-test framework. `make check` is the required
regression suite: it detects generated-file drift and validates every DLL
against `dll/manifest.json`. When changing a generator, also run its targeted
`gen` and `check` commands to prove output is deterministic.

## Commit & Pull Request Guidelines

Recent history uses brief imperative subjects, for example `Switch the Pascal
ABI binding...`. Keep commits focused and state the affected ABI, binding,
documentation, or DLL artifact. PRs should explain compatibility impact,
include regenerated files and manifest updates where applicable, and report
the verification commands run. Do not add AI co-author or attribution trailers
to commit messages.

Never add a `Co-Authored-By: Claude ...` (or similar AI attribution) trailer to commit messages in this repository. The user has not authorized AI co-authorship credit on commits here. Commit messages should end with the last line of actual content - no trailer.