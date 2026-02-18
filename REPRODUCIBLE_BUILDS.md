# Reproducible Builds

This project supports **bitwise deterministic builds** when built inside the provided Nix development shell.

## Quick Start

```bash
# Enter the Nix development shell
nix develop

# Build the project
make build

# Verify the build
sha256sum dist/protonfetcher.pyz
cat dist/protonfetcher.pyz.sha256sum
```

## Why Use `nix develop`?

The Nix shell provides:

1. **Pinned Python version** - Always uses Python 3.13 (matching `.python-version`)
2. **Pinned build tools** - `zip`, `rsync`, `sed`, `sha256sum` versions are consistent
3. **Reproducible environment** - Same dependencies regardless of host system
4. **Automatic `SOURCE_DATE_EPOCH`** - The Makefile sets this for deterministic timestamps

## Build Outputs

After running `make build`, the `dist/` directory contains:

```
dist/
├── protonfetcher.pyz           # The executable zipapp
└── protonfetcher.pyz.sha256sum # SHA256 checksum for verification
```

## Verifying Determinism

Build twice and compare:

```bash
nix develop --command bash -c 'make clean && make build'
cp dist/protonfetcher.pyz /tmp/build1.pyz

nix develop --command bash -c 'make clean && make build'
cp dist/protonfetcher.pyz /tmp/build2.pyz

# These should be identical
diff /tmp/build1.pyz /tmp/build2.pyz && echo "✓ Bitwise identical!"
sha256sum /tmp/build1.pyz /tmp/build2.pyz
```

Or verify using the checksum file:

```bash
cd dist && sha256sum -c protonfetcher.pyz.sha256sum
```

## How Determinism Is Achieved

1. **Staging directory** - Sources are copied to a clean staging area
2. **Excluded `__pycache__`** - Python bytecode (with timestamps) is not included
3. **Sorted file ordering** - Files are added to the archive in sorted order (`LC_ALL=C sort`)
4. **Normalized timestamps** - All files are touched with `SOURCE_DATE_EPOCH` (2015-10-21 00:00:00 UTC)
5. **Stripped metadata** - `zip -X` removes extra file attributes (uid/gid/xattrs)
6. **Fixed shebang** - Uses `#!/usr/bin/env python3` for portability

## Building Without Nix

You can build outside the Nix shell, but bitwise reproducibility is **not guaranteed** due to:

- Different Python versions
- Different tool versions (`zip`, `rsync`, etc.)
- System-specific file attributes

```bash
# Works, but may not be reproducible across machines
make clean && make build
```

## Requirements

- **Nix** with flakes enabled
- Or system packages: `python3.13`, `zip`, `rsync`, `gnused`, `coreutils`, `gnutar`
