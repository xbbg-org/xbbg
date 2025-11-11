# Versioning Policy

We follow Semantic Versioning (SemVer) 2.0.0: MAJOR.MINOR.PATCH.

- MAJOR: Incompatible API changes
- MINOR: Backward-compatible functionality
- PATCH: Backward-compatible bug fixes

Pre-releases use standard identifiers:

- Alpha: `0.8.0a1`, `0.8.0a2` (unstable, early testing)
- Beta: `0.8.0b1`, `0.8.0b2` (feature-complete, stabilization)
- Release Candidate: `0.8.0rc1`, `0.8.0rc2` (final checks)

Tag examples accepted by tooling (setuptools_scm):

- `v0.8.0a1`, `0.8.0b1`, `0.8.0rc1`, `0.8.0`

## Rust Backend Migration Plan

- Target version line: `0.8.x`
- Initial pre-release: tag `0.8.0a1` once the Rust backend scaffold lands
- Progress through `aN` → `bN` → `rcN`, then stable `0.8.0`
- If any backward-incompatible API changes are introduced, bump to `1.0.0`

## Changelog

We maintain a human-readable changelog per Keep a Changelog style in `CHANGELOG.md`. Each release entry includes: Added, Changed, Deprecated, Removed, Fixed, Security.


