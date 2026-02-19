FROM rust:1-bookworm

ARG BLPAPI_VERSION=3.25.12.1

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

RUN CLANG_LIB=$(find /usr/lib -name 'libclang*.so*' -print -quit) \
    && test -n "$CLANG_LIB" \
    && ln -sf "$CLANG_LIB" /usr/lib/libclang.so

RUN mkdir -p /opt/blpapi \
    && curl -sSL "https://blpapi.bloomberg.com/download/releases/raw/files/blpapi_cpp_${BLPAPI_VERSION}-linux.tar.gz" \
        | tar -xz -C /opt/blpapi --strip-components=1 \
    && ln -sf /opt/blpapi/Linux /opt/blpapi/lib \
    && ln -sf /opt/blpapi/lib/libblpapi3_64.so /opt/blpapi/lib/libblpapi3.so

ENV BLPAPI_ROOT=/opt/blpapi
ENV LD_LIBRARY_PATH=/opt/blpapi/lib:${LD_LIBRARY_PATH}

RUN rustup component add clippy rustfmt
