# xbbg Release Process

This document explains the release process for xbbg, intended for AI agents and maintainers.

## Overview

xbbg uses **semantic versioning** (SemVer) with versions **automatically derived from git tags** via `setuptools_scm`. The build system is `setuptools` + `setuptools-rust` + `setuptools_scm`.

### Version Format

```
{major}.{minor}.{patch}[-{pre-release}]

Examples:
- 0.12.1        # Stable release
- 0.12.1b1      # Beta pre-release
- 0.12.1a1      # Alpha pre-release
- 0.12.1rc1     # Release candidate
```

Dev builds (untagged commits) automatically get versions like `0.12.1.dev268+g84acdcf.d20260219`.

### Build System

| Component | Package | Purpose |
|-----------|---------|---------|
| Build backend | `setuptools` | Python packaging |
| Rust extension | `setuptools-rust` | Compiles PyO3 extension (`xbbg._core`) |
| Version | `setuptools_scm` | Derives version from git tags |
| Build tool | `uv` | Fast package manager and build frontend |

## Release Workflow

### Step 1: Update CHANGELOG.md

Ensure all changes are documented under the `[Unreleased]` section:

```markdown
## [Unreleased]

### Added
- New feature description

### Changed
- Modified behavior description

### Fixed
- Bug fix description
```

**Categories** (use only what applies):
- `Added` - New features
- `Changed` - Changes in existing functionality
- `Deprecated` - Soon-to-be removed features
- `Removed` - Removed features
- `Fixed` - Bug fixes
- `Security` - Vulnerability fixes

### Step 2: Commit CHANGELOG Updates

```bash
git add CHANGELOG.md
git commit -m "docs(CHANGELOG): prepare for vX.Y.Z release"
git push
```

### Step 3: Trigger Release Workflow

Go to **GitHub Actions** > **Bump Version and Create Release** > **Run workflow**

**Parameters:**
| Parameter | Description | Options |
|-----------|-------------|---------|
| `bump_type` | Version increment | `major`, `minor`, `patch` |
| `pre_release` | Pre-release type | `none`, `alpha`, `beta`, `rc` |
| `pre_number` | Pre-release number | `1`, `2`, `3`, etc. |
| `create_release` | Create GitHub release | `true`, `false` |

**Examples:**
- `0.12.1` → `0.13.0`: bump_type=`minor`, pre_release=`none`
- `0.12.1` → `0.12.2`: bump_type=`patch`, pre_release=`none`
- `0.12.1` → `0.12.2b1`: bump_type=`patch`, pre_release=`beta`, pre_number=`1`

### Step 4: What Happens Automatically

1. **Version Calculation**: Computes new version from current tags
2. **Changelog Update**: Renames `[Unreleased]` to `[version] - date`
3. **README Release Sync**: Updates the `README.md` latest-release marker block to the new version/tag
4. **Git Tag**: Creates `vX.Y.Z` tag and pushes it
5. **GitHub Release**: Creates release with notes from CHANGELOG
6. **PyPI Publish**: Tag push triggers `pypi_upload.yml` — builds wheels and publishes via OIDC trusted publishing
7. **Release Assets**: Wheels and sdist are attached to the GitHub release

## CI/CD Workflows

### On Every Push/PR

| Workflow | File | Purpose |
|----------|------|---------|
| CI | `ci-rust.yml` | Rust lint, clippy, build, test (Linux + Windows) |
| Docker | `ci-docker.yml` | Build CI Docker image |

### On Release (tag push `v*`)

| Workflow | File | Purpose |
|----------|------|---------|
| Release | `pypi_upload.yml` | Build wheels (Linux + Windows × Python 3.10–3.14), sdist, publish to PyPI, attach to GitHub release |

### Manual Trigger

| Workflow | File | Purpose |
|----------|------|---------|
| Bump Version | `semantic_version.yml` | Calculate version, update CHANGELOG and README release marker, create tag + GitHub release |

## Local Development

### Build Locally

```bash
# Set Bloomberg SDK path (required for wheel builds)
# Windows PowerShell:
$env:BLPAPI_ROOT = "$PWD\vendor\blpapi-sdk\3.25.12.1"
# Linux/macOS:
export BLPAPI_ROOT=$PWD/vendor/blpapi-sdk/3.25.12.1

# Build wheel (includes Rust extension)
uv build

# Build sdist only (no Rust compilation)
uv build --sdist
```

### Check Current Version

```bash
# Latest release tags
git tag --sort=-version:refname | head -5

# Local dev version (from setuptools_scm)
python -c "from setuptools_scm import get_version; print(get_version())"

# Installed package version
python -c "import xbbg; print(xbbg.__version__)"
```

### Check What's on PyPI

```bash
pip index versions xbbg
```

## Branch Strategy

| Branch | Purpose |
|--------|---------|
| `main` | v1.x development (Rust-backed beta line) |
| `release/0.x` | v0.x maintenance releases (pure-Python stable line) |
| `feat/*` | New features (PRs to main) |
| `fix/*` | Bug fixes (PRs to main or release/0.x) |
| `chore/*` | Maintenance tasks |

> **Note:** When releasing from `release/0.x`, the downstream `update-readme` and `update-index` workflows will target `main` by default. Review and revert any unintended changes to `main` after a `release/0.x` release.

### After Merging PRs

1. Delete merged branches
2. Update CHANGELOG.md on main
3. Trigger release workflow when ready

## Troubleshooting

### Release Workflow Failed

1. Check workflow logs in GitHub Actions
2. Common issues:
   - Empty CHANGELOG `[Unreleased]` section (blocked by validation)
   - Version already exists on PyPI
   - Bloomberg SDK download URL changed
   - Rust compilation error

### Version Already on PyPI

PyPI rejects duplicate versions. To fix:
1. Increment pre-release number (e.g., `b3` → `b4`)
2. Or fix issues and bump patch version

### Local Build Fails

1. Ensure `BLPAPI_ROOT` points to the Bloomberg SDK directory (must contain `include/` and `lib/`)
2. Ensure Rust toolchain is installed (`rustup show`)
3. For bindgen issues, set `LIBCLANG_PATH` (see `.cargo/config.toml` comments)
4. CI uses pregenerated bindings (`BLPAPI_PREGENERATED_BINDINGS`) to skip bindgen entirely

## For AI Agents

When asked to create a release:

1. **Review pending changes**: Read `CHANGELOG.md` `[Unreleased]` section
2. **Check for uncommitted changes**: Run `git status`
3. **Determine version bump**:
   - Breaking changes → `major`
   - New features → `minor`
   - Bug fixes only → `patch`
   - Pre-release → add `alpha`/`beta`/`rc`
4. **Guide user to GitHub Actions** to trigger the `semantic_version.yml` workflow

**Do NOT manually:**
- Edit version numbers in code (managed by `setuptools_scm` from git tags)
- Create git tags directly (workflow handles this)
- Upload to PyPI manually (OIDC trusted publishing only)
