# Build environment for xbbg with Bloomberg C++ SDK
#
# This image includes:
# - Rust stable toolchain with clippy and rustfmt
# - Python 3.12 with pip
# - Bloomberg C++ SDK
# - Build tools (gcc, make, clang for bindgen)

FROM rust:bookworm

ARG BLPAPI_VERSION=3.24.12.2

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    python3-pip \
    python3-venv \
    curl \
    ca-certificates \
    build-essential \
    pkg-config \
    libssl-dev \
    clang \
    libclang-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Rust components
RUN rustup component add clippy rustfmt

# Download and install Bloomberg C++ SDK
RUN mkdir -p /opt/blpapi \
    && curl -sSL "https://blpapi.bloomberg.com/download/releases/raw/files/blpapi_cpp_${BLPAPI_VERSION}-linux.tar.gz" \
    | tar -xz -C /opt/blpapi --strip-components=1

# Set Bloomberg SDK environment variables
ENV BLPAPI_ROOT=/opt/blpapi
ENV LD_LIBRARY_PATH=/opt/blpapi/lib:$LD_LIBRARY_PATH

# Install Python tools
RUN pip3 install --break-system-packages \
    ruff \
    maturin \
    pytest \
    pytest-cov \
    pyarrow \
    pandas \
    numpy

# Create workspace directory
WORKDIR /workspace

# Labels
LABEL org.opencontainers.image.source="https://github.com/alpha-xone/xbbg"
LABEL org.opencontainers.image.description="Build environment for xbbg with Bloomberg SDK"
