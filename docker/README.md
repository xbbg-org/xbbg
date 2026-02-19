# CI Container Images

This directory contains container images used by CI:

- `docker/ci/Dockerfile`: Rust CI image with toolchain + `libclang`
- `docker/manylinux/Dockerfile`: manylinux wheel image with `clang-devel`

Bloomberg SDK files are intentionally **not** baked into container images.
CI downloads the SDK at runtime to avoid redistributing the SDK in a public image registry.

## Local usage with Podman

The Dockerfiles are OCI-compatible, so you can build and run them with Podman.

### Build both images

```bash
podman build -f docker/ci/Dockerfile -t xbbg-ci:local .
podman build -f docker/manylinux/Dockerfile -t xbbg-manylinux:local .
```

### Generate `blpapi-sys` bindings artifact locally

```bash
mkdir -p target/ci-bindings

podman run --rm \
  -v "$PWD:/work" \
  -w /work \
  -e BLPAPI_BINDINGS_EXPORT_PATH=/work/target/ci-bindings/bindings.rs \
  xbbg-ci:local \
  bash -lc '
    BLPAPI_VERSION=3.25.12.1
    mkdir -p /tmp/blpapi
    curl -sSL "https://blpapi.bloomberg.com/download/releases/raw/files/blpapi_cpp_${BLPAPI_VERSION}-linux.tar.gz" \
      | tar -xz -C /tmp/blpapi --strip-components=1
    ln -sf /tmp/blpapi/Linux /tmp/blpapi/lib
    ln -sf /tmp/blpapi/lib/libblpapi3_64.so /tmp/blpapi/lib/libblpapi3.so
    export BLPAPI_ROOT=/tmp/blpapi
    export LD_LIBRARY_PATH=/tmp/blpapi/lib:$LD_LIBRARY_PATH
    cargo build -p blpapi-sys
  '
```

### Validate clippy in the CI image

```bash
podman run --rm \
  -v "$PWD:/work" \
  -w /work \
  xbbg-ci:local \
  bash -lc '
    BLPAPI_VERSION=3.25.12.1
    mkdir -p /tmp/blpapi
    curl -sSL "https://blpapi.bloomberg.com/download/releases/raw/files/blpapi_cpp_${BLPAPI_VERSION}-linux.tar.gz" \
      | tar -xz -C /tmp/blpapi --strip-components=1
    ln -sf /tmp/blpapi/Linux /tmp/blpapi/lib
    ln -sf /tmp/blpapi/lib/libblpapi3_64.so /tmp/blpapi/lib/libblpapi3.so
    export BLPAPI_ROOT=/tmp/blpapi
    export LD_LIBRARY_PATH=/tmp/blpapi/lib:$LD_LIBRARY_PATH
    cargo clippy --workspace --all-targets --exclude datamock --exclude datamock-sys -- -D warnings
  '
```

## Notes

- CI publishes images to `ghcr.io/<owner>/xbbg-ci` and `ghcr.io/<owner>/xbbg-manylinux`.
- The workflow in `.github/workflows/ci-rust.yml` consumes `ghcr.io/<owner>/xbbg-ci:latest` and `ghcr.io/<owner>/xbbg-manylinux:latest`.
- Bloomberg SDK is downloaded in CI job steps (runtime), not stored in container layers.
- Windows jobs still run on native `windows-latest` runners and consume the generated bindings artifact.
