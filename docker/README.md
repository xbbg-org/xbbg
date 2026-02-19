# CI Container Images

This directory contains container images used by CI:

- `docker/ci/Dockerfile`: Rust CI image with `libclang` + Bloomberg SDK
- `docker/manylinux/Dockerfile`: manylinux wheel image with `clang-devel` + Bloomberg SDK

## Local usage with Podman

The Dockerfiles are OCI-compatible, so you can build and run them with Podman.

### Build both images

```bash
BLPAPI_VERSION=3.25.12.1

podman build -f docker/ci/Dockerfile \
  --build-arg BLPAPI_VERSION="$BLPAPI_VERSION" \
  -t xbbg-ci:local .

podman build -f docker/manylinux/Dockerfile \
  --build-arg BLPAPI_VERSION="$BLPAPI_VERSION" \
  -t xbbg-manylinux:local .
```

### Generate `blpapi-sys` bindings artifact locally

```bash
mkdir -p target/ci-bindings

podman run --rm \
  -v "$PWD:/work" \
  -w /work \
  -e BLPAPI_BINDINGS_EXPORT_PATH=/work/target/ci-bindings/bindings.rs \
  xbbg-ci:local \
  bash -lc "cargo build -p blpapi-sys"
```

### Validate clippy in the CI image

```bash
podman run --rm \
  -v "$PWD:/work" \
  -w /work \
  xbbg-ci:local \
  bash -lc "cargo clippy --workspace --all-targets -- -D warnings"
```

## Notes

- CI publishes images to `ghcr.io/<owner>/xbbg-ci` and `ghcr.io/<owner>/xbbg-manylinux`.
- The workflow in `.github/workflows/ci-rust.yml` consumes `ghcr.io/<owner>/xbbg-ci:latest` and `ghcr.io/<owner>/xbbg-manylinux:latest`.
- Windows jobs still run on native `windows-latest` runners and consume the generated bindings artifact.
