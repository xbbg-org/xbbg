# CI image for jobs that need Rust + Bloomberg SDK + bindgen (libclang).
# Rebuild and push via .github/workflows/ci-docker.yml when this file changes.
#
# Note: bindgen uses Debian's libclang (LLVM 14 on bookworm). Local Pixi dev uses
# conda-forge libclang (pixi.toml + LIBCLANG_PATH); both are supported for bindgen.

FROM rust:1.89-bookworm

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        clang \
        curl \
        git \
        libclang-dev \
        llvm-14-dev \
        python3 \
        python3-dev \
        pkg-config \
    && rm -rf /var/lib/apt/lists/*

# bindgen: LLVM 14 libdir on Debian bookworm (matches llvm-config-14).
ENV LIBCLANG_PATH=/usr/lib/llvm-14/lib
RUN test -e "${LIBCLANG_PATH}/libclang.so" || test -e "${LIBCLANG_PATH}/libclang.so.1" \
    || (echo "libclang not found under ${LIBCLANG_PATH}" >&2; exit 1)

RUN rustup component add clippy rustfmt
