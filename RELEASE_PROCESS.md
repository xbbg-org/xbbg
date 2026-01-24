# xbbg Release Process

This document explains the release process for xbbg, intended for AI agents and maintainers.

## Overview

xbbg uses **semantic versioning** (SemVer) and follows the [Keep a Changelog](https://keepachangelog.com/) format. Releases are automated via GitHub Actions workflows.

### Version Format

```
{major}.{minor}.{patch}[-{pre-release}]

Examples:
- 0.11.0        # Stable release
- 0.11.0b1      # Beta pre-release
- 0.11.0a1      # Alpha pre-release
- 0.11.0rc1     # Release candidate
```

## Release Workflow

### Step 1: Update CHANGELOG.md

Before creating a release, ensure all changes are documented under the `[Unreleased]` section:

```markdown
## [Unreleased]

### Added
- New feature description

### Changed
- Modified behavior description

### Fixed
- Bug fix description

### Removed
- Removed feature description

### Deprecated
- Deprecated feature description

### Security
- Security fix description
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
- `0.11.0` → `0.12.0`: bump_type=`minor`, pre_release=`none`
- `0.11.0` → `0.11.1`: bump_type=`patch`, pre_release=`none`
- `0.11.0` → `0.11.1b1`: bump_type=`patch`, pre_release=`beta`, pre_number=`1`
- `0.11.0b3` → `0.11.0b4`: bump_type=`patch`, pre_release=`beta`, pre_number=`4`

### Step 4: What Happens Automatically

1. **Version Calculation**: Computes new version from current tags
2. **Changelog Update**: Renames `[Unreleased]` to `[version] - date`
3. **Git Tag**: Creates `vX.Y.Z` tag
4. **GitHub Release**: Creates release with notes from CHANGELOG
5. **PyPI Publish**: Uploads package via OIDC trusted publishing
6. **Documentation**: Updates README and docs with new version

## CI/CD Workflows

### On Every Push/PR

| Workflow | File | Purpose |
|----------|------|---------|
| Auto CI | `auto_ci.yml` | Run tests on Python 3.10-3.14 |
| Docs | `ci_docs.yml` | Build and verify documentation |
| CodeQL | `codeql-analysis.yml` | Security analysis |
| PyPI Build Test | `pypi_build_test.yml` | Verify package builds |

### On Release

| Workflow | File | Purpose |
|----------|------|---------|
| Upload to PyPI | `pypi_upload.yml` | Publish to PyPI |
| Release Assets | `release_assets.yml` | Attach build artifacts |
| Update README | `update_readme_on_release.yml` | Update version badges |
| Update Index | `update_index_on_release.yml` | Update docs index |
| Publish Docs | `publish_docs.yml` | Deploy to ReadTheDocs |

## Quick Commands

### Check Current Version

```bash
git tag --sort=-version:refname | head -5
```

### View Changelog

```bash
head -100 CHANGELOG.md
```

### Run Tests Before Release

```bash
uv run pytest xbbg/tests/ --tb=short -q
uv run ruff check xbbg/ --fix
uv run ruff format xbbg/
```

### Manual Version Check

```bash
# Check what's on PyPI
pip index versions xbbg

# Check local version
python -c "import xbbg; print(xbbg.__version__)"
```

## Branch Strategy

| Branch | Purpose |
|--------|---------|
| `main` | Production-ready code, all releases tagged here |
| `feat/*` | New features (PRs to main) |
| `fix/*` | Bug fixes (PRs to main) |
| `chore/*` | Maintenance tasks |

### After Merging PRs

1. Delete merged branches (automatic if using `--delete-branch`)
2. Update CHANGELOG.md on main
3. Trigger release workflow when ready

## Troubleshooting

### Release Workflow Failed

1. Check workflow logs in GitHub Actions
2. Common issues:
   - Empty CHANGELOG `[Unreleased]` section
   - Version already exists on PyPI
   - CI tests failing

### Version Already on PyPI

The workflow automatically skips publishing if the version exists. To fix:
1. Increment pre-release number (e.g., `b3` → `b4`)
2. Or fix issues and bump patch version

### CHANGELOG Format Issues

Ensure proper formatting:
```markdown
## [Unreleased]

### Added
- Item with description

## [0.11.0] - 2026-01-24

### Fixed
- Previous release item
```

## For AI Agents

When asked to create a release:

1. **Review pending changes**: Read `CHANGELOG.md` `[Unreleased]` section
2. **Verify tests pass**: Run `uv run pytest xbbg/tests/ -q`
3. **Check for uncommitted changes**: Run `git status`
4. **Determine version bump**:
   - Breaking changes → `major`
   - New features → `minor`
   - Bug fixes only → `patch`
   - Pre-release → add `alpha`/`beta`/`rc`
5. **Guide user to GitHub Actions** to trigger the workflow

**Do NOT manually:**
- Edit version numbers in code (managed by `setuptools_scm`)
- Create git tags directly (workflow handles this)
- Upload to PyPI manually (OIDC trusted publishing only)
