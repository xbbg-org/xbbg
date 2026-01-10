# Release Instructions

> **For AI Assistants**: This document provides guidance for preparing releases. Read this before creating or assisting with a release.

## Overview

This project uses **CHANGELOG.md as the single source of truth** for release notes. The release workflow (`semantic_version.yml`) extracts notes from the `[Unreleased]` section and uses them for GitHub Releases.

## Pre-Release Checklist

Before triggering a release, ensure:

- [ ] `CHANGELOG.md` `[Unreleased]` section is populated with all changes
- [ ] Changes are categorized correctly (Added, Changed, Deprecated, Removed, Fixed, Security)
- [ ] No placeholder text (TODO, FIXME, WIP, TBD) remains
- [ ] Issue/PR numbers are referenced where applicable
- [ ] Breaking changes are clearly marked

## CHANGELOG.md Format

```markdown
## [Unreleased]

### Added
- New feature description (#PR_NUMBER)

### Changed
- Modified behavior description (#PR_NUMBER)

### Deprecated
- Feature that will be removed in future versions

### Removed
- Feature removed in this release

### Fixed
- Bug fix description (#ISSUE_NUMBER)

### Security
- Security fix description (CVE if applicable)
```

## Writing Good Release Notes

### DO:
- Write from the user's perspective ("Users can now..." not "We added...")
- Be specific about what changed and why it matters
- Link to relevant issues/PRs with `(#123)` format
- Group related changes together
- Mention breaking changes prominently
- Include migration instructions for breaking changes

### DON'T:
- Leave the `[Unreleased]` section empty
- Use vague descriptions ("Various improvements")
- Include internal implementation details users don't need
- Forget to categorize changes
- Leave placeholder text

## Example: Good Release Notes

```markdown
## [Unreleased]

### Added
- Multi-backend support with `Backend` enum (narwhals, pandas, polars, pyarrow, duckdb) (#173)
- Output format control with `Format` enum (long, semi_long, wide)
- `bta()` function for Bloomberg Technical Analysis (#175)
- `get_sdk_info()` as replacement for deprecated `getBlpapiVersion()`

### Changed
- All API functions now accept `backend` and `format` parameters
- Internal pipeline uses PyArrow tables with narwhals transformations
- **BREAKING**: Default output format changed from `wide` to `long`

### Deprecated
- `connect()` / `disconnect()` - engine auto-initializes in v1.0
- `getBlpapiVersion()` - use `get_sdk_info()` instead

### Fixed
- Empty DataFrame handling in helper functions with LONG format output (#180)
- Memory leak in streaming subscriptions (#182)
```

## Example: Bad Release Notes

```markdown
## [Unreleased]

- Various bug fixes
- Performance improvements
- TODO: add more details
- Updated some stuff
```

## Determining Version Bump Type

| Bump Type | When to Use | Example |
|-----------|-------------|---------|
| **major** | Breaking changes, major new features, API redesign | 0.x.x → 1.0.0 |
| **minor** | New features, non-breaking additions | 0.10.x → 0.11.0 |
| **patch** | Bug fixes, documentation, minor improvements | 0.10.3 → 0.10.4 |

### Pre-release Types

| Type | When to Use |
|------|-------------|
| **alpha** | Early testing, API may change significantly |
| **beta** | Feature complete, testing for bugs |
| **rc** | Release candidate, final testing before stable |

## Release Workflow

1. **Update CHANGELOG.md** with all changes under `[Unreleased]`
2. **Commit changes** to main branch
3. **Run workflow**: `.github/workflows/semantic_version.yml`
   - Select bump type (major/minor/patch)
   - Select pre-release type if applicable
4. **Workflow automatically**:
   - Validates `[Unreleased]` is not empty
   - Extracts release notes from `[Unreleased]`
   - Creates GitHub Release with those notes
   - Updates `CHANGELOG.md` (renames section, adds new `[Unreleased]`)
   - Commits the changes
   - Triggers downstream workflows
5. **Manually trigger** `pypi_upload.yml` to publish to PyPI

## For AI Assistants: Release Preparation

When asked to prepare a release:

1. **Review commits since last release**:
   ```bash
   git log v$(git tag --sort=-v:refname | head -1)..HEAD --oneline
   ```

2. **Categorize changes** into Added/Changed/Deprecated/Removed/Fixed/Security

3. **Update CHANGELOG.md** `[Unreleased]` section with:
   - Clear, user-focused descriptions
   - PR/issue references
   - Breaking change warnings if applicable

4. **Suggest version bump type** based on:
   - Breaking changes → major
   - New features → minor  
   - Bug fixes only → patch

5. **Verify** the `[Unreleased]` section:
   - Has meaningful content (not empty)
   - No placeholder text
   - Follows Keep a Changelog format

## Validation

The release workflow validates:

1. **Non-empty**: `[Unreleased]` must have content (workflow fails if empty)
2. **No placeholders**: Warns if TODO/FIXME/WIP/TBD detected
3. **Format check**: Warns if standard categories not found

## Related Files

- `CHANGELOG.md` - The changelog (source of truth)
- `CONTRIBUTING.md` - Contributor guide with changelog section
- `.github/workflows/semantic_version.yml` - Release workflow
- `.github/workflows/pypi_upload.yml` - PyPI publishing (manual trigger)
