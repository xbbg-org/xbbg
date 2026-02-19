FROM rust:1-bookworm

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        clang \
        curl \
        git \
        libclang-dev \
        python3 \
        python3-dev \
        pkg-config \
    && rm -rf /var/lib/apt/lists/*

RUN ln -sf /usr/lib/llvm-14/lib/libclang.so /usr/lib/libclang.so
ENV LIBCLANG_PATH=/usr/lib

RUN rustup component add clippy rustfmt
